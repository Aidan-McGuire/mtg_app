# Collection Bulk Import — Design Spec

**Date:** 2026-04-06

## Overview

Add bulk import support to the collection view, allowing users to populate their collection from a pasted text list or a Moxfield CSV export. Quantities are additive — importing a card you already own increases the count.

## Backend

### New endpoint

`POST /api/collection/import`

Request body:
```json
{ "list": "4x Lightning Bolt\n1 Counterspell\n..." }
```

- Reuses `parse_decklist` to parse the text (handles `4x Name`, `4 Name`, comment lines, section headers)
- Reuses `lookup_card_id` for name matching (exact, MDFC slash normalization, front-face prefix)
- Upserts into `collection`: `ON CONFLICT(card_id) DO UPDATE SET quantity = quantity + excluded.quantity`
- Returns:
```json
{ "imported": 42, "not_found": ["Some Card", "Other Card"] }
```

No new DB schema changes required — the existing `collection` table supports this.

## Frontend

### UI entry point

An "Import" button in the collection view header, same position and style as the deck import button in the decks view header.

### Modal

A modal with two tabs: **Text** and **CSV**.

**Text tab**
- Textarea for pasting a decklist-style card list (`4x Lightning Bolt`, `1 Counterspell`, etc.)
- Same format accepted by the existing deck import

**CSV tab**
- `<input type="file" accept=".csv">` file picker
- On file select, JS reads the file with `FileReader` and parses it in-browser:
  - Splits lines, handles quoted fields (Moxfield wraps all values in double quotes)
  - Reads the header row to locate `Count` and `Name` column indices
  - Converts each data row to `"{count}x {name}"` text format
  - Result is stored as the list string, same as if typed in the Text tab
- Per-printing metadata (edition, condition, foil, purchase price) is ignored

Both tabs share a single Submit button. On submit, the assembled list string is POSTed to `/api/collection/import`.

### Result display

Below the submit button, same pattern as deck import result:
- Success: "X cards imported"
- Not-found cards listed by name (if any)

### Post-import

On successful import, close the modal and reload the collection view (`loadCollectionView()`).

## Error handling

- Empty list → validation error shown in result area, no request sent
- Backend not-found cards → displayed in result, does not block the import of matched cards
- Network/server error → shown in result area

## Out of scope

- Per-printing tracking (foil, condition, edition)
- Replace/overwrite mode (always additive)
- Undo/rollback of an import
