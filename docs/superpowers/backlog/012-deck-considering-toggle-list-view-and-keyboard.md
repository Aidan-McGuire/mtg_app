---
id: 012
title: Add considering-toggle to list view, plus a shared keyboard shortcut
priority: medium
status: in-progress
branch: item/12-add-considering-toggle-to-list-view-plus-a-shared-keyboard-shortcut
created: 2026-08-23
---

## Problem

Grid view's tile (`buildDeckCardTile`, `static/app.js`) has a
considering-toggle button (`.deck-considering-btn`, app.js:2122-2124,
wired at app.js:2148-2149 to `toggleConsidering(card.id)`, app.js:2377) —
hidden for the commander (`card.is_commander ? '' : ...`, since a commander
can't be Considering). List view (`buildDeckTextRow`, app.js:2156) has no
such control, and there's no way to move a card to/from Considering except
by clicking into grid view.

Separately, toggling Considering is mouse/click-only in both views today —
no keyboard shortcut exists for it (confirmed: no binding anywhere in
`static/app.js` besides the click listener).

## Approach

### 1. Add the button to list view

In `buildDeckTextRow` (app.js:2156-2168), add the same
`.deck-considering-btn` markup and click wiring `buildDeckCardTile` already
uses (app.js:2122-2124, 2148-2149), hidden for the commander the same way.
Reuse the existing `.deck-considering-btn` CSS (style.css:850-865) as-is —
no new styles needed.

### 2. Shared keyboard shortcut

In the deck page's arrow-key dispatch block (app.js:1255-1265 — the same
block item 010 adds its `Backspace` binding to), add a `c` binding:

```js
if (!typingInField && (e.key === 'c' || e.key === 'C') && deckState.focusedCardId) {
  const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
  if (card && !card.is_commander) {
    e.preventDefault();
    toggleConsidering(card.id);
  }
}
```

`c` is unused elsewhere in the app (confirmed via search — existing
single-letter bindings are `f` for modal card-flip and `d` for the deck
switcher, both unrelated contexts) and mnemonically matches "Considering."
Guarded the same way the button itself is: a no-op on the commander. Works
in both grid and list view since `deckState.focusedCardId` is shared
between them (same mechanism item 010 uses for its `Backspace` shortcut).

### 3. Visual hint on the focused card

Mirroring item 010's `⌫` badge pattern: in both `buildDeckCardTile` and the
new list-view button, when `card.id === deckState.focusedCardId` and the
card is not the commander, render a small `<kbd>c</kbd>` badge next to the
`.deck-considering-btn`. Hidden for the commander, same as the button it
labels.

### Out of scope

- No change to `toggleConsidering` itself, or to how Considering cards are
  rendered/grouped/counted elsewhere.
- No keyboard shortcut or button added for the commander toggle
  (`.deck-cmd-btn`) — out of scope, not asked for.
- This item assumes whatever list-view action-button layout exists at
  implementation time (item 010 may or may not have landed first, adding
  its own remove button/`⌫` hint to the row) — add the considering button
  alongside whatever's already there rather than assuming a specific prior
  layout.

## Acceptance criteria

- [ ] List view rows show a considering-toggle button, hidden for the
      commander, matching grid view's button (icon, active state, title
      text) and behavior.
- [ ] Clicking the list-view considering button toggles that card between
      the deck and Considering, same as grid view's button.
- [ ] With a non-commander card focused (via mouse hover or arrow-key nav)
      in either deck view, pressing `c` toggles that card's Considering
      state.
- [ ] Pressing `c` while the commander is focused does nothing. Pressing
      `c` while focus is in a text input/textarea/select does not trigger
      the toggle.
- [ ] A `c` badge appears next to the considering-toggle button only on the
      currently focused, non-commander card, in both grid and list view,
      and disappears when focus moves elsewhere or lands on the commander.
- [ ] Toggling Considering via keyboard or the list-view button updates the
      deck card count and re-groups the card into/out of the Considering
      bucket the same way the existing grid button does.
