# Auto-refresh Card DB on Startup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Kick off a non-blocking background refresh of the card database from Scryfall on FastAPI server startup, gated by a 7-day minimum interval tracked in `schema_version.cards_last_refreshed`, so the ~34k-card DB stays current without the user having to remember to run `python importer.py` manually.

**Architecture:** A new `schema_version.cards_last_refreshed` column (migration v6) tracks when the card DB was last refreshed. `importer.py`'s `import_cards()` starts returning `{"inserted", "updated", "processed"}` counts instead of just printing. `app.py` gains a FastAPI `lifespan` context manager that checks whether >7 days have elapsed (or refresh has never run) and, if so, spawns a daemon thread that calls `import_cards()`, updates the timestamp on success, and always appends a line to `card_refresh.log`. A failed run does not update the timestamp, so the next startup retries.

**Tech Stack:** Python, FastAPI/Starlette (`lifespan` context manager), sqlite3, pytest + `TestClient`, `threading`.

**Spec:** `docs/superpowers/backlog/006-auto-refresh-card-db-on-startup.md`

## Global Constraints

- `cards_last_refreshed` is a nullable ISO-8601 UTC timestamp string on `schema_version`; NULL means "never refreshed".
- `REFRESH_INTERVAL` is a fixed constant (`timedelta(days=7)`) — not configurable.
- A failed refresh must log the exception to `card_refresh.log` and must **not** update `cards_last_refreshed`.
- The background refresh must never block server startup or request handling.
- `python importer.py` run directly from the CLI must keep working exactly as before.
- The full test suite (pytest + JS) must keep passing, and it must never trigger a real background refresh (no live network calls, no writes to the real `mtg.db`) during a test run.
- `migrate_database()` must remain idempotent — running it twice leaves `schema_version.version` at 6 without erroring.

---

### Task 1: Migration — add `cards_last_refreshed` column

**Files:**
- Modify: `main.py:85-137` (`migrate_database()`)
- Test: `tests/test_migrate.py` (new)

**Interfaces:**
- Produces: `schema_version.cards_last_refreshed` (TEXT, nullable) column, present once `migrate_database()` has run; `schema_version.version == 6` after migration.

- [x] **Step 1: Write the failing tests**

Create `tests/test_migrate.py`:

```python
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
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_migrate.py -v`
Expected: FAIL — `sqlite3.OperationalError: no such column: cards_last_refreshed` (column doesn't exist yet, since `migrate_database()` doesn't add it).

- [x] **Step 3: Implement the migration**

In `main.py`, inside `migrate_database()`, immediately after the existing `if version < 5:` block (before `conn.commit()` / `conn.close()`), add:

```python
    if version < 6:
        cur.execute("ALTER TABLE schema_version ADD COLUMN cards_last_refreshed TEXT;")
        cur.execute("UPDATE schema_version SET version = 6;")
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_migrate.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add main.py tests/test_migrate.py
git commit -m "feat(db): add cards_last_refreshed column via schema migration v6"
```

---

### Task 2: `import_cards()` reports inserted/updated/processed counts

**Files:**
- Modify: `importer.py:88-162` (`import_cards()`)
- Test: `tests/test_importer_idempotent.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `import_cards() -> {"inserted": int, "updated": int, "processed": int}` — Task 4 depends on exactly these three keys.

- [x] **Step 1: Write the failing test**

Append to `tests/test_importer_idempotent.py`:

```python
def test_import_cards_returns_counts(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    monkeypatch.setattr(importer, "DB_PATH", db)
    monkeypatch.setattr(importer, "get_bulk_download_url", lambda: "x")

    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([_card("elf-uuid", "Llanowar Elves")]),
    )
    result = importer.import_cards()
    assert result == {"inserted": 1, "updated": 0, "processed": 1}

    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([
            _card("elf-uuid", "Llanowar Elves"),
            _card("bolt-uuid", "Lightning Bolt", type_line="Instant",
                  oracle_text="Lightning Bolt deals 3 damage to any target.",
                  colors=["R"], color_identity=["R"]),
        ]),
    )
    result = importer.import_cards()
    assert result == {"inserted": 1, "updated": 1, "processed": 2}
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_importer_idempotent.py::test_import_cards_returns_counts -v`
Expected: FAIL — `assert None == {...}` (function currently returns `None`).

- [x] **Step 3: Implement counters and return value**

In `importer.py`, inside `import_cards()`:

1. Next to the existing `batch = 0` / `processed = 0` initialization (around line 97-98), add:

```python
    inserted = 0
    updated = 0
```

2. In the `if oracle_id in existing:` branch (around line 126), after its two `cur.execute(...)` calls, add:

```python
                updated += 1
```

3. In the corresponding `else:` branch (around line 138), after its two `cur.execute(...)` calls, add:

```python
                inserted += 1
```

4. Replace the tail of the function (currently):

```python
    conn.commit()
    print("Finished importing cards.")
    conn.close()
```

with:

```python
    conn.commit()
    print(f"Finished importing cards. {inserted} new, {updated} updated, {processed} processed.")
    conn.close()
    return {"inserted": inserted, "updated": updated, "processed": processed}
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_importer_idempotent.py -v`
Expected: PASS (all tests in the file, including the new one and the pre-existing ones — the pre-existing tests don't check the return value so they're unaffected by this change).

- [x] **Step 5: Commit**

```bash
git add importer.py tests/test_importer_idempotent.py
git commit -m "feat(importer): return inserted/updated/processed counts from import_cards"
```

---

### Task 3: Background refresh on server startup

**Files:**
- Modify: `app.py:1-14` (imports), `app.py:159-161` (`migrate_database()` / `app = FastAPI()` region)
- Modify: `tests/conftest.py` (seed `schema_version` with a fresh `cards_last_refreshed` so the shared `client` fixture never triggers a real refresh)
- Test: `tests/test_card_refresh.py` (new)

**Interfaces:**
- Consumes: `import_cards()` from `importer.py` (Task 2) returning `{"inserted", "updated", "processed"}`; `schema_version.cards_last_refreshed` (Task 1).
- Produces: `app._should_refresh_cards() -> bool`, `app._run_card_refresh() -> None` (writes one line to `app.REFRESH_LOG_PATH` and updates `cards_last_refreshed` on success), `app.REFRESH_INTERVAL` (`timedelta`), `app.REFRESH_LOG_PATH` (`Path`), `app.lifespan` (async context manager passed to `FastAPI(lifespan=...)`).

**Why a `lifespan` context manager instead of `@app.on_event("startup")`:** the installed FastAPI/Starlette version treats `on_event` as deprecated in favor of `lifespan`; `app.py` doesn't have a lifespan yet, so this task introduces one. Behavior (fires once per process start, doesn't block it) is equivalent to what the spec's `@app.on_event("startup")` sketch describes.

**Why `tests/conftest.py` needs a change:** `app.py`'s `lifespan` fires on every `with TestClient(app_module.app) as c:` (used by the shared `client` fixture that most existing tests use). If left at its current schema (`schema_version` has no `cards_last_refreshed` column, stuck at version 5), `_should_refresh_cards()` would raise `OperationalError` on every test using that fixture. Seeding the column with a fresh timestamp makes `_should_refresh_cards()` correctly return `False` (matches production behavior for an already-refreshed DB) so no thread spawns and no test ever makes a real Scryfall network call.

- [x] **Step 1: Update `tests/conftest.py`'s schema to include `cards_last_refreshed`**

In `tests/conftest.py`, change the `_SCHEMA` string's `schema_version` table definition and seed row from:

```python
CREATE TABLE schema_version (version INTEGER NOT NULL);
```
```python
INSERT INTO schema_version VALUES (5);
```

to:

```python
CREATE TABLE schema_version (version INTEGER NOT NULL, cards_last_refreshed TEXT);
```
```python
INSERT INTO schema_version VALUES (6, NULL);
```

Then, in the `db_path` fixture, after the loop that executes `_SCHEMA` statements and before `conn.commit()`, add a dynamic `UPDATE` so the seeded timestamp is always "just now" (never hardcode a literal date — a hardcoded past date would eventually cross the 7-day threshold and start making real network calls in test runs):

```python
    conn.execute(
        "UPDATE schema_version SET cards_last_refreshed = ?",
        (datetime.now(timezone.utc).isoformat(),),
    )
```

Add the needed import at the top of `tests/conftest.py`:

```python
from datetime import datetime, timezone
```

- [x] **Step 2: Run the existing suite to confirm this alone doesn't break anything**

Run: `pytest tests/ -v -k "not test_card_refresh"`
Expected: PASS (this step only changes seed data shape; `app.py` doesn't reference `cards_last_refreshed` yet, so nothing consumes it yet — this just confirms the conftest edit itself is safe).

- [x] **Step 3: Write the failing tests for the new behavior**

Create `tests/test_card_refresh.py`:

```python
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
```

- [x] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_card_refresh.py -v`
Expected: FAIL — `AttributeError: module 'app' has no attribute '_should_refresh_cards'` (and similar for the other new names), since none of this exists in `app.py` yet.

- [x] **Step 5: Implement the background refresh in `app.py`**

Add to the import block at the top of `app.py` (after the existing imports, before `DB_PATH = Path("mtg.db")`):

```python
import threading
from datetime import datetime, timedelta, timezone
```

and change:

```python
from contextlib import contextmanager
```

to:

```python
from contextlib import asynccontextmanager, contextmanager
```

and add, alongside the existing `from main import migrate_database`:

```python
from importer import import_cards
```

Then, replace the existing:

```python
migrate_database()

app = FastAPI()
```

(around line 159-161) with:

```python
migrate_database()

REFRESH_INTERVAL = timedelta(days=7)
REFRESH_LOG_PATH = Path("card_refresh.log")


def _should_refresh_cards():
    with get_db() as conn:
        row = conn.execute("SELECT cards_last_refreshed FROM schema_version LIMIT 1").fetchone()
    last = row[0] if row else None
    if not last:
        return True
    return datetime.now(timezone.utc) - datetime.fromisoformat(last) > REFRESH_INTERVAL


def _run_card_refresh():
    started = datetime.now(timezone.utc)
    try:
        result = import_cards()
        with get_db() as conn:
            conn.execute(
                "UPDATE schema_version SET cards_last_refreshed = ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()
        line = (f"{started.isoformat()} refreshed cards: "
                f"{result['inserted']} new, {result['updated']} updated, "
                f"{result['processed']} processed\n")
    except Exception as e:
        line = f"{started.isoformat()} card refresh FAILED: {e}\n"
    with open(REFRESH_LOG_PATH, "a") as f:
        f.write(line)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _should_refresh_cards():
        threading.Thread(target=_run_card_refresh, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)
```

Note: `_should_refresh_cards()` and `_run_card_refresh()` reference `get_db()`, which is defined later in the file (in the "DB helpers" section). This is fine in Python — the name is looked up from the module namespace at *call* time, not at function-definition time, and by the time these functions are actually called (inside `lifespan`, when the app starts) the whole module has finished loading.

- [x] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_card_refresh.py -v`
Expected: PASS

- [x] **Step 7: Run the full suite to confirm nothing else broke**

Run: `pytest tests/ -v`
Expected: PASS — in particular, every test using the shared `client` fixture must still pass without hanging or making network calls (the conftest change from Step 1 seeds a fresh `cards_last_refreshed`, so `_should_refresh_cards()` returns `False` for all of them).

- [x] **Step 8: Commit**

```bash
git add app.py tests/conftest.py tests/test_card_refresh.py
git commit -m "feat(app): background-refresh card DB from Scryfall on startup, gated by a 7-day interval"
```

---

### Task 4: Gitignore the refresh log

**Files:**
- Modify: `.gitignore`

**Interfaces:** none (no code dependency).

- [x] **Step 1: Add the entry**

In `.gitignore`, after the existing `.claude/stage2.log` line, add:

```
# Card DB auto-refresh log
card_refresh.log
```

- [x] **Step 2: Verify**

Run: `git status --porcelain` after touching a local `card_refresh.log` (e.g. `touch card_refresh.log`) to confirm it doesn't show as untracked, then remove the manually-created file:

```bash
touch card_refresh.log && git status --porcelain | grep card_refresh.log
```

Expected: no output (file is ignored).

```bash
rm -f card_refresh.log
```

- [x] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore card_refresh.log"
```

---

### Task 5: Final verification

**Files:** none (verification only).

- [x] **Step 1: Run the full Python test suite**

Run: `pytest tests/ -v`
Expected: PASS, no errors, no warnings about unclosed threads/sockets, no network access.

- [x] **Step 2: Run the JS sentinel tests**

Run: `find . -path ./node_modules -prune -o -name "*.test.mjs" -print` to confirm the test files under `tests/js/`, then run them with whatever runner the project uses (check `package.json` / `docs/superpowers/plans/2026-06-*.md` for the established `node --test` invocation used by prior plans). This item touches no JS, so these are a regression check only — expect them to pass unchanged.

- [x] **Step 3: Manual sanity check of the acceptance criteria**

Run these from the plan's working directory (the worktree root) against the *real* `mtg.db` — first back up or note that this mutates real local state, since this is a manual smoke check, not part of the automated suite:

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('mtg.db')
row = conn.execute('SELECT version, cards_last_refreshed FROM schema_version').fetchone()
print(row)
"
```

Confirm `version == 6`. This is enough to validate Task 1 landed correctly against the real DB (which gets migrated automatically the next time `app.py` is imported, e.g. by the test suite). Do not attempt to boot the full `uvicorn` server and wait out a real Scryfall download as part of this plan's verification — that's a multi-minute network operation outside the scope of automated checks; the unit/integration tests in Task 3 already cover the startup-triggering logic with a mocked `import_cards`.

---

## Self-Review Notes

- **Spec coverage:** §1 (timestamp column) → Task 1. §2 (`import_cards()` return value) → Task 2. §3 (background refresh + startup hook) → Task 3. §4 (gitignore) → Task 4. All 7 acceptance criteria are covered: fresh-DB triggers refresh (`test_should_refresh_when_never_refreshed`, `test_startup_spawns_background_thread_without_blocking`), non-blocking startup (same test), one log line with counts (`test_run_card_refresh_success_updates_timestamp_and_logs`), no re-trigger when recent (`test_should_not_refresh_when_recent`, `test_startup_does_not_refresh_when_recent`), stale timestamp re-triggers (`test_should_refresh_when_stale`), failure path leaves timestamp unchanged and logs the exception (`test_run_card_refresh_failure_logs_and_preserves_timestamp`), CLI `python importer.py` unaffected (Task 2 keeps the `if __name__ == "__main__": import_cards()` entrypoint untouched — its return value is simply discarded, exactly as before), full suite passes + `migrate_database()` idempotent (Task 1 Step for idempotency test, Task 3 Step 7).
- **Placeholder scan:** none found — every step has concrete code.
- **Type consistency:** `import_cards()` return shape (`{"inserted", "updated", "processed"}`) matches between Task 2's implementation and Task 3's `_run_card_refresh()` consumption (`result['inserted']`, `result['updated']`, `result['processed']`). `REFRESH_INTERVAL`/`REFRESH_LOG_PATH` names match between Task 3's implementation and its tests (`monkeypatch.setattr(app_module, "REFRESH_LOG_PATH", ...)`).
