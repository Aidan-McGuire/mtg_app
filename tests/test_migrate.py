import sqlite3
import main as main_module


def _make_v5_db(tmp_path):
    p = tmp_path / "mig.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL);")
    conn.execute("INSERT INTO schema_version VALUES (5);")
    conn.commit()
    conn.close()
    return p


def test_migration_adds_cards_last_refreshed_column(tmp_path, monkeypatch):
    db = _make_v5_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()

    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(schema_version)")]
    version, last_refreshed = conn.execute(
        "SELECT version, cards_last_refreshed FROM schema_version"
    ).fetchone()
    conn.close()

    assert "cards_last_refreshed" in cols
    assert version == 6
    assert last_refreshed is None


def test_migration_is_idempotent(tmp_path, monkeypatch):
    db = _make_v5_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()
    main_module.migrate_database()  # must not error, must not re-add the column

    conn = sqlite3.connect(str(db))
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()

    assert version == 6
