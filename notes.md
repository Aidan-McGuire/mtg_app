# Notes
## Next features
1. set default categories to card types
2. decide how to handle deck and collection tags
3. default tag all lands as land, including mdfc lands



## Issues
1. Keyboard navigation needs work on all pages
  - works decently well on 'Cards' page, needs refinement
  - Ultimately need to be able to navigate the app without using a mouse at all
2. `colors` field is empty for double-faced/transform cards because the importer only reads the top-level Scryfall `colors` field, not `card_faces[*].colors` — affects the Exact Colors filter (and would affect anything else that reads `colors`) for ~895 cards. Fix: update `importer.py` to fall back to the union of face colors, then re-run `python importer.py` to backfill.
3. Collection import can attach quantity to the wrong `oracle_id` when multiple Scryfall entries share a printed name — found via `Clearwater Pathway // Clearwater Pathway` (a non-playable Scryfall `art_series` print) holding 4 tracked copies separately from the real `Clearwater Pathway // Murkwater Pathway` land's 2. Manually merged this one instance (now 6 on the real land) on 2026-08-03, but the underlying name-matching bug in collection import wasn't fixed — other name collisions could still misattribute quantity.
4. (DONE) cdv (card detail view) not showing images — root cause: Scryfall's non-playable `art_series` layout (art-only crossover prints) was being imported like a real card, with placeholder `type_line`/`mana_cost` and, for some, no `image_uri` at all. Fixed by skipping `art_series` in `importer.py` and deleting the 2,194 already-imported art_series rows from the DB (`8026c5f`).