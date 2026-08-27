---
id: 027
title: Enter opens the detail modal for the keyboard-focused deck card
priority: medium
status: in-review
branch: item/27-enter-opens-the-detail-modal-for-the-keyboard-focused-deck-card
created: 2026-08-27
---

## Problem

On the Cards browser page, pressing `Enter` opens the detail modal for the
currently focused card (`static/app.js:1352`, `if (browserActive && e.key
=== 'Enter' && ...) { ... openModal(c); }`). The deck page has the same
"currently focused card" concept (`deckState.focusedCardId`, set by
`setDeckFocus` on hover or arrow-key navigation, already wired for
`Backspace` and `c` shortcuts at `static/app.js:1320-1343`), but no `Enter`
handler — the only way to open a deck card's modal today is to click it
directly with the mouse.

## Approach

Add an `Enter` case to the existing deck-page keydown block
(`static/app.js:1320-1343`), mirroring the existing `Backspace`/`c` handlers:

```js
if (!typingInField && e.key === 'Enter' && deckState.focusedCardId) {
  e.preventDefault();
  const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
  if (card) openModal(card, { deckId: deckState.currentDeckId });
}
```

This works identically in both grid and list view since both share the same
`deckState.focusedCardId` / `setDeckFocus` mechanism, and reuses the same
`openModal(card, { deckId })` call already used by the existing mouse click
handlers on the grid tile and text row.

**Out of scope:** no change to `openModal` itself, no change to how focus is
set (hover/arrow-nav already cover that).

## Acceptance criteria

- [ ] With a card keyboard-focused in the deck grid view, pressing `Enter`
      opens that card's detail modal (deck-context variant — no editable
      quantity stepper, per existing behavior).
- [ ] Same behavior in the deck list (text) view.
- [ ] Pressing `Enter` while typing in any input/textarea/select (e.g. the
      content search box, an open tag input) does not open the modal.
- [ ] Pressing `Enter` when no card is focused (`deckState.focusedCardId` is
      null) does nothing, matching existing Backspace/`c` guard behavior.
