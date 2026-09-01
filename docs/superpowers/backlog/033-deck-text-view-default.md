---
id: 033
title: Make text (list) view the default on the deck page
priority: low
status: in-progress
branch: item/33-make-text-list-view-the-default-on-the-deck-page
created: 2026-08-31
---

## Problem

The deck page's view toggle (`static/index.html`, `.vtoggle-btn` elements
with `data-dview="grid"` / `data-dview="text"`) defaults to grid view: the
initial state is `deckView: 'grid'` in `deckState` (`static/app.js` around
line 2005), and the "Grid" button carries the `active` class by default in
`static/index.html` (around line 79-80). The user wants text (list) view to
be the default instead, every time a deck is opened.

There is no persistence for this setting (no localStorage, no server-side
preference) — it is a plain hardcoded initial value, so this is a pure
default-value flip, not a new preference system.

## Approach

1. In `static/app.js`, change the `deckState` initializer's `deckView` from
   `'grid'` to `'text'`.
2. In `static/index.html`, move the `active` class from the Grid toggle
   button to the Text toggle button so the toggle's visual state matches the
   new default on first paint (before any click fires the existing
   `vtoggle-btn` click handler that manages the `active` class).
3. Do not add persistence (localStorage, DB) — out of scope. This item is
   only about changing the initial/default value.

## Acceptance criteria

- [ ] Opening any deck (fresh page load, or switching decks) shows the text
      (list) view by default, not the grid view.
- [ ] The "Text" toggle button shows as active on initial load; the "Grid"
      button does not.
- [ ] Clicking the "Grid" toggle still switches to grid view and updates the
      active button state as before (existing toggle behavior unchanged).
- [ ] Keyboard navigation and other view-dependent behavior (e.g. column nav
      in grid view) still functions correctly after the default change, since
      it branches on `deckState.deckView === 'grid'` elsewhere in the code.
