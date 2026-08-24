import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

import app as app_module


def _make_refresh_db(tmp_path, last_refreshed=None):
    p = tmp_path / "refresh.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, cards_last_refreshed TEXT);")
    conn.execute("INSERT INTO schema_version VALUES (6, ?);", (last_refreshed,))
    conn.commit()
    conn.close()
    return p


def test_should_refresh_when_never_refreshed(tmp_path, monkeypatch):
    db = _make_refresh_db(tmp_path, last_refreshed=None)
    monkeypatch.setattr(app_module, "DB_PATH", db)
    assert app_module._should_refresh_cards() is True


def test_should_not_refresh_when_recent(tmp_path, monkeypatch):
    recent = datetime.now(timezone.utc).isoformat()
    db = _make_refresh_db(tmp_path, last_refreshed=recent)
    monkeypatch.setattr(app_module, "DB_PATH", db)
    assert app_module._should_refresh_cards() is False


def test_should_refresh_when_stale(tmp_path, monkeypatch):
    stale = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    db = _make_refresh_db(tmp_path, last_refreshed=stale)
    monkeypatch.setattr(app_module, "DB_PATH", db)
    assert app_module._should_refresh_cards() is True


def test_run_card_refresh_success_updates_timestamp_and_logs(tmp_path, monkeypatch):
    db = _make_refresh_db(tmp_path, last_refreshed=None)
    monkeypatch.setattr(app_module, "DB_PATH", db)
    log_path = tmp_path / "card_refresh.log"
    monkeypatch.setattr(app_module, "REFRESH_LOG_PATH", log_path)
    monkeypatch.setattr(
        app_module, "import_cards",
        lambda: {"inserted": 3, "updated": 5, "processed": 8},
    )

    app_module._run_card_refresh()

    conn = sqlite3.connect(str(db))
    last = conn.execute("SELECT cards_last_refreshed FROM schema_version").fetchone()[0]
    conn.close()
    assert last is not None

    log_text = log_path.read_text()
    assert "3 new" in log_text
    assert "5 updated" in log_text
    assert "8 processed" in log_text


def test_run_card_refresh_failure_logs_and_preserves_timestamp(tmp_path, monkeypatch):
    db = _make_refresh_db(tmp_path, last_refreshed=None)
    monkeypatch.setattr(app_module, "DB_PATH", db)
    log_path = tmp_path / "card_refresh.log"
    monkeypatch.setattr(app_module, "REFRESH_LOG_PATH", log_path)

    def _boom():
        raise RuntimeError("scryfall unreachable")

    monkeypatch.setattr(app_module, "import_cards", _boom)

    app_module._run_card_refresh()

    conn = sqlite3.connect(str(db))
    last = conn.execute("SELECT cards_last_refreshed FROM schema_version").fetchone()[0]
    conn.close()
    assert last is None  # unchanged, so next startup retries

    log_text = log_path.read_text()
    assert "FAILED" in log_text
    assert "scryfall unreachable" in log_text


def test_startup_spawns_background_thread_without_blocking(tmp_path, monkeypatch):
    """A DB that has never been refreshed must trigger a non-blocking background
    refresh on startup: the server must accept requests immediately, without
    waiting for the refresh to finish."""
    db = _make_refresh_db(tmp_path, last_refreshed=None)
    monkeypatch.setattr(app_module, "DB_PATH", db)

    release = threading.Event()
    started = threading.Event()

    def _slow_refresh():
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(app_module, "_run_card_refresh", _slow_refresh)

    with TestClient(app_module.app) as c:
        assert started.wait(timeout=2)          # refresh was kicked off promptly
        r = c.get("/")                          # server responds immediately,
        assert r.status_code in (200, 404)      # without waiting for the refresh

    release.set()


def test_startup_does_not_refresh_when_recent(tmp_path, monkeypatch):
    db = _make_refresh_db(tmp_path, last_refreshed=datetime.now(timezone.utc).isoformat())
    monkeypatch.setattr(app_module, "DB_PATH", db)

    calls = []
    monkeypatch.setattr(app_module, "_run_card_refresh", lambda: calls.append(1))

    with TestClient(app_module.app):
        pass

    assert calls == []
