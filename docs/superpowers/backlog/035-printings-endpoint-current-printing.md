---
id: 035
title: Printings endpoint should always include the DB's current printing
priority: low
status: queued
branch:
created: 2026-08-31
---

## Problem

`GET /api/cards/{id}/printings` (`app.py`, `get_printings`, line ~411) does a
live Scryfall search with `unique=art`, which frequently does not include the
exact printing the local DB's bulk import picked for that card's stored
`image_uri` — spot-checked 5 real cards, 4 had no match. This is because the
DB's `image_uri` comes from bulk import's arbitrary first-seen printing pick,
while Scryfall's `unique=art` dedup groups by illustration and may surface a
*different* printing that happens to share the same art.

Effect (`static/app.js` around line 1115 and 1120-1123): the modal's art
strip does
`printings.find(p => p.image_uri === card.image_uri) || printings[0]`
to pick the active printing, then hides the "Set as preferred printing"
button only when `activePrinting.image_uri === card.image_uri`. When the
DB's exact printing is missing from the returned list entirely, this match
always fails, `printings[0]` becomes active instead, and the button
incorrectly shows as clickable even though the DB is already "on" that
printing (there is just no way to select/represent it in the strip).

## Approach

Fix this entirely server-side, in `get_printings()` — the frontend's
existing match/fallback logic (`static/app.js` lines 1115 and 1120-1123)
already does the right thing once the correct entry exists in the list, so no
frontend changes are needed.

1. In `get_printings()`, extend the initial DB query to also select
   `image_uri` (currently only `oracle_id` is selected):
   ```python
   cur.execute("SELECT oracle_id, image_uri FROM cards WHERE id = ?", (card_id,))
   ```
2. After building the `printings` list from the Scryfall response, check
   whether the DB's own `image_uri` is already present:
   ```python
   db_image_uri = row["image_uri"]
   if db_image_uri and not any(p["image_uri"] == db_image_uri for p in printings):
       printings.insert(0, {
           "set_name": "Current printing",
           "artist": None,
           "image_uri": db_image_uri,
       })
   ```
   Insert at index 0 so it also becomes the natural first/default entry in
   the art strip when nothing else has been explicitly selected yet.
3. No changes needed to `static/app.js` — the existing
   `printings.find(p => p.image_uri === card.image_uri)` will now succeed,
   and `updatePreferredBtn()` will correctly hide the button since
   `activePrinting.image_uri === card.image_uri`.

## Acceptance criteria

- [ ] `get_printings()` selects the card's `image_uri` from the DB alongside
      `oracle_id`.
- [ ] When the Scryfall `unique=art` search result does not contain an entry
      matching the DB's stored `image_uri`, the endpoint injects one at the
      front of the returned list, using `"Current printing"` as its
      `set_name` and `artist: null`.
- [ ] When the Scryfall result *does* already contain a matching entry, no
      duplicate is added (the existing entry with real `set_name`/`artist`
      metadata is left in place).
- [ ] For one of the 4 previously-broken spot-checked cards, opening the
      detail modal now shows the "Set as preferred printing" button hidden
      by default (since the DB is already on its current printing), instead
      of incorrectly enabled.
- [ ] Clicking through other printings in the strip and back to the injected
      "Current printing" entry still correctly re-hides the button.
