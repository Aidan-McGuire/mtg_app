---
id: 006
title: Auto-refresh card database from Scryfall in the background on server startup
priority: low
status: in-progress
branch: item/6-auto-refresh-card-database-from-scryfall-in-the-background-on-server-startup
created: 2026-08-21
---

## Problem

`importer.py`'s `import_cards()` (line 88) already upserts by `oracle_id` —
re-running it is always safe and picks up new/changed Scryfall card data —
but nothing ever triggers it automatically. The user has to remember to run
`python importer.py` manually to keep the ~34k-card database current.

## Approach

Kick off a background refresh from `app.py`'s FastAPI startup hook,
non-blocking, gated by a minimum interval so it doesn't fire on every dev
`--reload` bounce.

### 1. Track last-refresh time

In `main.py`'s `migrate_database()` (line 85), add a new migration step:

```python
if version < 6:
    cur.execute("ALTER TABLE schema_version ADD COLUMN cards_last_refreshed TEXT;")
    cur.execute("UPDATE schema_version SET version = 6;")
```

(`cards_last_refreshed` is a nullable ISO-8601 UTC timestamp string; NULL
means "never refreshed".)

### 2. Make `import_cards()` report what it did

In `importer.py`'s `import_cards()` (line 88-135ish), add `inserted = 0` and
`updated = 0` counters next to the existing `batch`/`processed` counters,
incrementing `updated` in the existing `if oracle_id in existing:` branch
(line 126) and `inserted` in its `else:` branch. Change the function to
`return {"inserted": inserted, "updated": updated, "processed": processed}`
at the end (currently it just prints and returns nothing). Keep the existing
`print(...)` calls as-is for the CLI (`if __name__ == "__main__":`) case;
optionally print the returned summary there too.

### 3. Background refresh on startup

In `app.py`, after `migrate_database()` runs and `app = FastAPI()` is
created (~lines 159-161), add:

```python
import threading
from datetime import datetime, timedelta, timezone
from importer import import_cards

REFRESH_INTERVAL = timedelta(days=7)
REFRESH_LOG_PATH = Path("card_refresh.log")

def _should_refresh_cards():
    with get_connection() as conn:
        row = conn.execute("SELECT cards_last_refreshed FROM schema_version LIMIT 1").fetchone()
    last = row[0] if row else None
    if not last:
        return True
    return datetime.now(timezone.utc) - datetime.fromisoformat(last) > REFRESH_INTERVAL

def _run_card_refresh():
    started = datetime.now(timezone.utc)
    try:
        result = import_cards()
        with get_connection() as conn:
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

@app.on_event("startup")
def _maybe_refresh_cards():
    if _should_refresh_cards():
        threading.Thread(target=_run_card_refresh, daemon=True).start()
```

(Use whichever startup-hook mechanism matches this `app.py`'s actual
installed FastAPI version — `@app.on_event("startup")` if still supported,
or a `lifespan` context manager passed to `FastAPI(...)` otherwise; either
is fine as long as it fires once per process start and doesn't block it.)

A failed run does **not** update `cards_last_refreshed`, so the next server
start retries rather than waiting out the full week.

### 4. Gitignore the log

Add to `.gitignore` (matching the existing `.claude/stage2.log` entry):

```
# Card DB auto-refresh log
card_refresh.log
```

### Out of scope

- No UI indicator/notification in the app itself — check `card_refresh.log`
  to see if/when it last ran, same spirit as checking `.claude/stage2.log`
  for the backlog worker.
- No change to how `python importer.py` is invoked manually / from the CLI
  — this only adds an *additional*, automatic trigger path.
- No configurable interval — 7 days is a fixed constant
  (`REFRESH_INTERVAL`); not exposed as a setting.
- No retry/backoff scheduling beyond "try again on the next server start" —
  same simplicity precedent as the existing async backlog workflow's own
  Stage 2 job (per its design spec's "Out of scope" section).

## Acceptance criteria

- [ ] Starting the app for the first time ever (fresh `mtg.db` with
      `cards_last_refreshed` NULL) triggers a background refresh; the
      server accepts requests immediately without waiting for it to finish.
- [ ] `card_refresh.log` gets one new line after the background refresh
      completes, with a timestamp and counts of inserted/updated/processed
      cards.
- [ ] After a successful refresh, restarting the app immediately again does
      **not** trigger another refresh (last-refreshed timestamp is recent).
- [ ] Manually setting `cards_last_refreshed` to a timestamp more than 7
      days in the past and restarting the app triggers a new background
      refresh.
- [ ] If `import_cards()` raises partway through, the failure (with the
      exception message) is logged to `card_refresh.log` and
      `cards_last_refreshed` is left unchanged (not updated), so the next
      startup retries.
- [ ] Running `python importer.py` directly from the CLI (unrelated to the
      app server) continues to work exactly as before.
- [ ] The full test suite (pytest + JS tests) still passes; `migrate_database()`
      is idempotent (running it twice in a row doesn't error and leaves
      `schema_version.version` at 6).
