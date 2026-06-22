# Detail Modal: "In decks" section

## Goal

In the card detail modal, list which decks (if any) the card is included in. Deck
names are shown as clickable links that navigate to the deck.

## Scope

- **In:** a new read-only API endpoint, a new async-loaded modal section, click-to-navigate, minimal CSS.
- **Out:** schema changes, import changes, edits to any existing endpoint, quantity/commander indicators (names only).

## Backend

New endpoint, mirroring the existing `GET /api/cards/{card_id}/printings` style (read-only, in `app.py`):

```
GET /api/cards/{card_id}/decks
→ 200 [{ "id": <int>, "name": <str> }, …]
```

- Joins `deck_cards` → `decks` for the given `card_id`.
- One row per deck (DISTINCT on deck — a card appears once regardless of quantity).
- Ordered by deck `name`.
- Returns `[]` when the card is in no decks (no 404). Matches the lenient behavior of the printings endpoint.

## Frontend (`static/app.js`)

- Add `<div id="modal-decks-section"></div>` in the modal details column, placed under the existing tags section, in `openModal`'s template.
- New async `loadModalDecks(card)`, called from `openModal` alongside `loadPrintings(card)` and `loadModalTags(card, deckContext)`.
  - Fetches `/api/cards/${card.id}/decks`.
  - Guards with `isConnected` after the await (modal may have been closed).
  - **Empty result → render nothing** (section stays empty/hidden).
  - **Non-empty → render** an "In decks" label and the deck **names only**, each a clickable element.
- **Click behavior** (reuses existing navigation primitives):
  1. Close the modal.
  2. Switch nav to the decks view: deactivate all `.view`/`.nav-btn`, activate `view-decks` and its nav button, call `loadDeckList()`.
  3. Call `selectDeck(deckId)`.

## Styling (`static/style.css`)

- Reuse the `modal-tags-label` look for the "In decks" heading.
- Add a small style for the clickable deck-name links/chips.

## Testing

- Endpoint: card in multiple decks returns all of them, sorted by name, distinct; card in zero decks returns `[]`.
- Modal: section hidden when empty; renders deck names when present; clicking a deck closes the modal, switches to the decks view, and opens that deck.
