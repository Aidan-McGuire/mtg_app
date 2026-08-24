---
id: 010
title: Scope collection removal off the deck page; add list-view + keyboard deck-card removal
priority: medium
status: queued
branch:
created: 2026-08-23
---

## Problem

Three related gaps around removing cards, all on the deck page
(`static/app.js`):

1. **Modal exposes the wrong "remove" everywhere.** `openModal` (app.js:808)
   always renders a `.modal-collection` +/− stepper (app.js:831-836) wired
   to the global `increment`/`decrement` functions (app.js:539, 554), which
   mutate *collection* (owned-copies) quantity. This happens even when the
   modal is opened from the Deck page (`openModal(card, { deckId:
   deckState.currentDeckId })`, called from both `buildDeckCardTile`
   (app.js:2151) and `buildDeckTextRow` (app.js:2166)). Deck grid tiles
   already have their own, separate deck-quantity +/− and a "×"
   remove-from-deck button (`buildDeckCardTile`, app.js:2131-2137, wired to
   `incDeckCard`/`decDeckCard`/`removeDeckCard`) — so opening a card's modal
   from the deck page surfaces a second, different quantity control (global
   owned count) that's easy to confuse with the deck's own controls sitting
   right behind it on the tile. Collection-quantity editing belongs on Cards
   page and Collection page only, where `buildCardTile` (app.js:630) already
   provides it directly on the tile.
2. **List view has no removal affordance at all.** `buildDeckTextRow`
   (app.js:2156) renders no buttons — clicking a row only opens the modal,
   whose stepper (per #1) doesn't even act on the deck. There is currently
   no way to remove a card from a deck while in list view.
3. **No keyboard-only removal path.** Neither view supports removing the
   currently-focused/highlighted card via a keypress — removal is
   mouse-only today (click the × button), which doesn't fit this app's
   keyboard-first design (per `CLAUDE.md`).

## Approach

### 1. Stop rendering the collection stepper in deck context

In `openModal(card, deckContext = null)` (app.js:808-852), wrap the
`.modal-collection` block (app.js:831-836) and its two listener attachments
(app.js:841-842) in `if (!deckContext) { ... }`. When opened from the Cards
page or Collection page (no `deckContext` passed), behavior is unchanged.
When opened from the Deck page (`deckContext` truthy), the block — and its
`+`/`−` collection buttons — is not rendered at all.

### 2. Add a remove button to list view rows

In `buildDeckTextRow` (app.js:2156-2168), add a `.deck-remove-btn` (×),
matching the grid tile's existing button, wired the same way:

```js
row.querySelector('.deck-remove-btn').addEventListener('click', e => {
  e.stopPropagation(); removeDeckCard(card.id);
});
```

Scope is deliberately minimal — just the remove button, not the grid tile's
full action set (qty +/−, commander toggle, considering toggle). Those stay
grid-only for now; no new ask covers bringing them to list view.

### 3. Keyboard removal shortcut, shared by both views

In the deck page's arrow-key dispatch block (app.js:1255-1265), add a
sibling `Backspace` binding alongside the existing arrow-key handling, using
the same `typingInField` guard:

```js
if (!typingInField && e.key === 'Backspace' && deckState.focusedCardId) {
  e.preventDefault();
  removeDeckCard(deckState.focusedCardId);
  return;
}
```

Because `deckState.focusedCardId` is shared by both `handleDeckGridKey` and
`handleDeckListKey`, this one binding removes the focused card correctly in
either view without any view-specific branching. `Backspace` is chosen
because it's present on every keyboard (unlike forward-`Delete`, absent on
many laptop keyboards) and isn't bound to anything else in the app
(confirmed via search — no existing `'Backspace'` handling).

### 4. Visual hint on the focused card

In both `buildDeckCardTile` (app.js:2106) and `buildDeckTextRow`
(app.js:2156), when `card.id === deckState.focusedCardId`, render a small
`<kbd>⌫</kbd>` badge immediately next to that card's `.deck-remove-btn`
(inside `.deck-actions` for the grid tile). It only appears on the currently
focused card, so the hint shows up exactly where the action is available,
rather than adding a permanent line to a header hint bar (the deck editor
header has no `kbd-hints` bar today, unlike Cards/Collection pages — this
per-card badge is the mechanism instead).

### Out of scope

- No change to Cards page or Collection page modal/tile behavior — their
  collection-quantity controls (tile-level and modal-level) are unaffected.
- No qty +/−, commander, or considering controls added to list view rows —
  remove-only, per the raw ask.
- No change to `incDeckCard`/`decDeckCard`/`removeDeckCard` themselves, or
  to the deck-quantity API.
- No undo for the new keyboard shortcut — same as the existing × button,
  removal is immediate (matches existing behavior/risk level of the mouse
  path this mirrors).

## Acceptance criteria

- [ ] Opening a card's modal from the Deck page (grid or list view) shows
      no collection +/− stepper; the Cards page and Collection page modals
      are unchanged and still show it.
- [ ] Deck list view rows show a × remove button; clicking it removes that
      card from the current deck (same effect as grid view's × button).
- [ ] With a card focused (via mouse hover or arrow-key nav) in either deck
      view, pressing `Backspace` removes that card from the deck.
      `Backspace` while focus is in a text input/textarea/select does not
      trigger removal (normal text editing).
- [ ] A `⌫` badge appears next to the remove button only on the currently
      focused card, in both grid and list view, and disappears when focus
      moves to a different card.
- [ ] Removing a card via keyboard or the list-view × button updates the
      deck card count and preview panel the same way the existing grid ×
      button does.
- [ ] Cards page and Collection page tile-level +/− collection controls are
      unaffected by any of the above.
