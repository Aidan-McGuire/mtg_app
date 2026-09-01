---
id: 034
title: Fix empty colors field for double-faced/transform cards
priority: medium
status: queued
branch:
created: 2026-08-31
---

## Problem

`importer.py`'s `import_cards()` reads the card's color via
`sort_colors(card.get("colors"))` (line ~121). Scryfall omits the top-level
`colors` field on double-faced/transform/modal-DFC cards (`card_faces`
present) — each face carries its own `colors` list instead. Since the
importer never falls back to the faces, every such card gets stored with an
empty `colors` string in the `cards` table.

This affects the "Exact Colors" filter (and anything else that reads
`colors`) for approximately 895 cards. Note: `color_identity` is unaffected
— Scryfall always provides `color_identity` at the top level even for DFCs,
so only `colors` needs a fix.

`extract_image_uri()` (line 45) and `extract_pt()` (line 57) already
implement the same top-level-then-faces fallback pattern for other fields —
follow the same shape for colors.

## Approach

1. In `importer.py`, add a new helper alongside `extract_image_uri` /
   `extract_pt`:

   ```python
   def extract_colors(card):
       """Return the card's color list: the top-level Scryfall `colors` field,
       or the union of `card_faces[*].colors` when absent (DFC/transform/MDFC
       cards omit the top-level field)."""
       if "colors" in card:
           return card.get("colors")
       colors = set()
       for face in card.get("card_faces", []):
           colors.update(face.get("colors") or [])
       return sorted(colors) if colors else None
   ```

2. In `import_cards()`, replace `sort_colors(card.get("colors"))` with
   `sort_colors(extract_colors(card))` (both the INSERT and UPDATE value
   tuples use the same `values` tuple, so this is a single change).
3. Re-run `python importer.py` against the existing `mtg.db` to backfill —
   this is an UPDATE-only run for already-imported oracle_ids (the importer
   already handles insert-vs-update via the `existing` set), so no data is
   lost.
4. Spot-check a handful of previously-affected DFC cards (e.g. search
   Scryfall bulk data or the DB for a known transform card) to confirm
   `colors` is now populated and matches the union of both faces' colors.

## Acceptance criteria

- [ ] `extract_colors()` added to `importer.py`, following the existing
      `extract_image_uri`/`extract_pt` fallback pattern.
- [ ] `import_cards()` uses `extract_colors(card)` instead of
      `card.get("colors")` when computing the stored `colors` value.
- [ ] After re-running `python importer.py`, previously-empty `colors` values
      for DFC/transform/MDFC cards are populated with the union of both
      faces' colors, sorted (e.g. a card with a blue front face and a red
      back face stores `"UR"`).
- [ ] The "Exact Colors" filter now correctly includes these ~895 previously
      excluded cards when their actual colors match the filter.
- [ ] Non-DFC cards' `colors` values are unchanged (no regression for the
      common case where `card.get("colors")` was already present).
