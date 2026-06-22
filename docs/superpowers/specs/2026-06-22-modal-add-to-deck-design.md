# Detail Modal: "Add to deck" control

## Goal

From the card detail modal, let the user add the card to an existing deck via a
type-ahead search. Builds on the existing "In decks" section.

## Scope

- **In:** a type-ahead "Add to deck" control in the modal, always visible; resolve typed text to an existing deck and add one copy; refresh the "In decks" list and show a transient confirmation.
- **Out:** backend changes (the add endpoint already exists), on-the-fly deck creation, quantity selector, commander designation, live-refresh of a deck-builder view open in the background.

## Backend

No changes. The existing endpoint is reused:

```
POST /api/decks/{deck_id}/cards   body: { "card_id": int, "quantity": int }
```

It upserts: `ON CONFLICT(deck_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity`. Each add from the modal sends `quantity: 1`, so re-adding a card increments its count. Returns `201` with `{deck_id, card_id, quantity, is_commander}`. The frontend already wraps this as `API.addCardToDeck(deckId, cardId, quantity = 1)`.

## Frontend (`static/app.js`, `static/style.css`)

The current `loadModalDecks(card)` renders the "In decks" list and hides the
whole section when the card is in no decks. Restructure so the modal deck area
has two parts:

1. **"Add to deck" type-ahead — always shown.** A native pattern matching the
   modal's existing tag inputs: `<input list="deck-suggestions">` plus a
   `<datalist id="deck-suggestions">` of all deck names. The browser filters as
   the user types; no custom dropdown.
2. **"In decks" list — shown only when the card is in ≥1 deck** (unchanged
   behavior, including escaping deck names with `esc()` and click-to-navigate).

### Data flow

- On modal open, `loadModalDecks(card)` fetches in parallel:
  - the card's decks: `GET /api/cards/{card.id}/decks`
  - all decks: `GET /api/decks` (via `API.listDecks()`)
  Guard every render with `section.isConnected` (modal may have closed).
- Render the add control (always) and the "In decks" list (if non-empty).
- **Add action** triggers on `Enter` in the input (matching the existing tag
  input). Choosing a datalist suggestion fills the input; the user then presses
  `Enter` to add. On `Enter`:
  1. Read and trim the input value. Empty → no-op.
  2. Resolve to a deck by **case-insensitive exact name match** against the
     fetched deck list.
  3. No match → show inline hint `No deck named "<value>"`; no API call.
  4. Match → `await API.addCardToDeck(deck.id, card.id)` (quantity defaults to 1),
     clear the input, then re-fetch `GET /api/cards/{card.id}/decks` and
     re-render the "In decks" list, and show a transient note
     `Added to <deck name>` near the input that clears after ~2 seconds.

### Error handling

- Add request failure (network or non-2xx) → transient error note
  (`Could not add to <deck name>`) instead of the success note; do not refresh.
- Whitespace-only input → no-op (no hint, no call).
- `isConnected` guards prevent writing into a closed modal.

### Decomposition

- `loadModalDecks(card)` orchestrates fetch + initial render.
- A small `renderInDecksList(decks)` helper renders the "In decks" sub-list and
  wires click-to-navigate; reused on post-add refresh.
- An add handler closure resolves name → deck, calls the API, refreshes, and
  shows the transient note.

## Styling

- Reuse `modal-tags-label` for the "Add to deck" / "In decks" headings.
- Add small styles for the add-control row, the inline hint, and the transient
  note (success vs error variant).

## Testing

- Backend: unchanged; existing add-to-deck tests cover the upsert/increment.
- Frontend: `node --check static/app.js` for syntax, plus manual click-through
  (no JS test harness):
  - typing a deck name + Enter adds the card; "In decks" updates; note appears.
  - re-adding increments quantity (verify in the deck view).
  - a non-matching name shows the hint and does not call the API.
  - the control is visible for a card in zero decks.
