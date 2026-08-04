# Import failure log

## Problem

`import_collection` (`app.py:481`) and `import_deck` (`app.py:591`) both call
`lookup_card_id()` for every parsed decklist entry, and silently drop
whatever it can't match into a `not_found` list that's returned once in the
HTTP response and rendered in a one-time results panel
(`static/app.js:1709-1725`, `2567-2580`). If that panel is missed, scrolled
past, or the entry is one of many, the failure is gone forever — there is no
record anywhere that a card failed to import. This is exactly what happened
with "Kalakscion, Hunger Tyrant" (timing: card wasn't in `cards` yet at
import time) and "Biophagus_" (typo): both failed silently and were only
found by manually re-running the same import against a scratch DB copy.

## Goal

Every failed match from either import path is durably recorded, independent
of whether anyone read the response panel at the time. Failures can be
reviewed later on a dedicated page and marked resolved once dealt with.

## Approach

### Data model

New table, added as a `main.py` migration (current schema version is 4, per
`migrate_database()`; this becomes version 5):

```sql
CREATE TABLE import_failures (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,               -- 'collection' | 'deck'
    deck_id INTEGER REFERENCES decks(id) ON DELETE CASCADE,
    card_name TEXT NOT NULL,
    requested_qty INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);
```

`deck_id` is NULL for collection-import failures; `ON DELETE CASCADE` means
deleting a deck cleans up its own failure rows too. `resolved_at` NULL means
outstanding; a timestamp means dismissed.

No dedup: re-running an import that fails on the same card again inserts
another row. Keeps the insert path simple (append-only) and matches the
"dismissible" model — resolving is a manual, explicit action per failure,
not something the system infers from a later successful import.

### Backend (`app.py`)

In both `import_collection` and `import_deck`, the existing
`else: not_found.append(name)` branch (lines 499 and 613) additionally
inserts an `import_failures` row in the same transaction as the rest of the
import — both functions already do all their work inside one
`with get_db() as conn` block and a single `conn.commit()` at the end, so
this is just one more `cur.execute()` alongside the existing
`not_found.append(name)`, using `qty` and `name` already in scope. Because
it shares the transaction, a failure record can never exist without the
import that produced it having committed, and vice versa.

New endpoints, colocated with the other collection/deck endpoints:

- `GET /api/import-failures?resolved=<false|true|all>` — returns failure
  rows, newest first, joined to deck name where `deck_id` is set. Omitting
  the param is equivalent to `resolved=false` (outstanding only), which is
  what the history page requests by default. `resolved=true` returns
  resolved-only; `resolved=all` returns everything regardless of state.
- `POST /api/import-failures/{id}/resolve` — sets `resolved_at = datetime('now')`.
  Returns 404 if the id doesn't exist.

### Frontend (`static/app.js`, `index.html`)

New nav entry "Import History" alongside the existing Cards/Collection/Decks
pages. The page lists outstanding failures in a simple table: source badge
(Collection/Deck), deck name link if applicable, card name, requested qty,
timestamp, and a "Resolve" button. A checkbox/toggle "show resolved" re-fetches
with `resolved=true` appended.

This is purely additive — the existing `not_found` panels on the collection-
import and deck-import flows (`app.js:1709-1725`, `2567-2580`) are unchanged,
so the immediate in-the-moment feedback still works exactly as it does today.
The history page is the durable backstop, not a replacement.

### Out of scope

- No dedup/grouping of repeated failures for the same card name.
- No automatic resolution when a later import successfully matches a
  previously-failed name — resolving stays a manual action.
- No retry-from-history action (e.g. "add this card now" button that calls
  the collection/deck add endpoint directly from the history page) — the
  user still adds the card manually elsewhere, then resolves the log entry.

## Testing

Extend `tests/` (backend, following the existing `test_importer_idempotent.py`
/ collection-import test style):

- A failed lookup during `import_collection` inserts an `import_failures`
  row with `source='collection'`, `deck_id IS NULL`, the correct
  `card_name`/`requested_qty`, and `resolved_at IS NULL`.
- A failed lookup during `import_deck` inserts a row with `source='deck'`
  and the correct `deck_id`.
- `GET /api/import-failures` with no `resolved` param returns only
  outstanding rows; `resolved=true` returns only resolved rows.
- `POST /api/import-failures/{id}/resolve` sets `resolved_at` and the row
  no longer appears in the default (outstanding) listing.
- `POST .../resolve` on a nonexistent id returns 404.

Frontend verification is manual in the browser: run a collection or deck
import with at least one deliberately-misspelled card name, confirm it
appears on the Import History page, resolve it, confirm it drops off the
default view and reappears when "show resolved" is toggled on.
