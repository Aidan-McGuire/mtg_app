---
id: 009
title: Deck list view uses a two-column grid with column-aware arrow nav
priority: medium
status: queued
branch:
created: 2026-08-23
---

## Problem

Deck list/text view (`#deck-text-view`) renders one card per row in a single
vertical column (`#deck-text-view .group-body { display: flex;
flex-direction: column; }`, style.css:893) — wasted horizontal space on
anything wider than a narrow column, and inconsistent with grid view's
denser layout.

Arrow-key navigation is also inconsistent between the two deck views today.
`handleDeckGridKey` (app.js:2289) already does full 2D grid navigation:
Left/Right move within a row, Down/Up cross into the next/previous category
when they run off the top/bottom row. `handleDeckListKey` (app.js:2255) is
simpler because list view is currently single-column: Up/Down move within
the current category only (clamped, never crossing), and Left/Right jump
whole categories instead.

This item supersedes a prior draft of item 009 that only fixed
`handleDeckListKey`'s Up/Down-doesn't-cross-categories gap for a
single-column layout. That fix would have had to be partially undone by
this item once list view goes multi-column, so it was rolled into this one
item instead of shipping and then reworking it.

## Approach

### 1. CSS: two-column grid

In `static/style.css`, change `#deck-text-view .group-body` (line 893) from

```css
#deck-text-view .group-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
```

to a 2-column grid, row-major fill (same visual model as the tile grid —
item 1 fills top-left, item 2 top-right, item 3 second row left, etc.):

```css
#deck-text-view .group-body {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2px 8px;
}
```

`.deck-text-view` itself (style.css:884, the outer container of group
sections) is unaffected — it stays a vertical flex column of group
sections; only the row layout *within* a group changes.

### 2. JS: share grid-aware nav between both deck views

Generalize `handleDeckGridKey` (app.js:2289-2329) into a container-agnostic
function, e.g.:

```js
function handleDeckColumnNavKey(e, containerId) {
  const groups = deckNavGroups(document.getElementById(containerId));
  // ...exact existing body of handleDeckGridKey, unchanged otherwise...
}
```

Delete `handleDeckListKey` (app.js:2255-2273) entirely — its job (category
crossing, row navigation) is now handled by the shared function. Update the
two call sites:

- The single dispatch point in the global keydown handler (app.js:1262):
  ```js
  if (deckState.deckView === 'grid') handleDeckColumnNavKey(e, 'deck-grid-view');
  else handleDeckColumnNavKey(e, 'deck-text-view');
  ```
- `handleDeckGridKey` itself either becomes a thin wrapper calling
  `handleDeckColumnNavKey(e, 'deck-grid-view')`, or is removed and the
  dispatch site calls `handleDeckColumnNavKey` directly with the right id
  for both branches — either is fine, pick whichever keeps the dispatch
  site simplest.

No changes needed to `deckNavGroups`, `groupColumnCount`, or `findTileIndex`
— all already container/tile-shape agnostic and already used by grid view.
`groupColumnCount` measures column count from actual rendered layout
(`getBoundingClientRect`), so it will correctly detect 2 columns for list
view's rows without any special-casing.

### Out of scope

- No change to how categories are computed, hidden, sorted, or collapsed.
- No change to grid view's own visual layout or column count — only list
  view's CSS changes.
- Not a configurable column count — fixed at 2, matching the raw ask.
- Untagged-card reachability — already correct today (a normal category
  like any other); this item doesn't change that, just re-verifies it in
  acceptance criteria.

## Acceptance criteria

- [ ] In deck list view, cards within a category render in a 2-column grid
      (row-major: item 1 top-left, item 2 top-right, item 3 wraps to the
      next row left, etc.), for categories with both even and odd card
      counts.
- [ ] In list view, ArrowRight/ArrowLeft move focus between the two columns
      of the same row; at the right/left edge they do nothing (no wrap).
- [ ] In list view, ArrowDown/ArrowUp move focus down/up a column, and
      crossing off the last/first row of a category moves into the
      next/previous category (landing in the same column, clamped to that
      category's own column count) — mirroring grid view's existing
      behavior exactly.
- [ ] Grid view keyboard navigation is unchanged after the refactor —
      manually re-verify all four arrow keys still behave as before.
- [ ] Untagged cards still appear in an "Untagged" category in list view
      and are reachable via the same column-aware nav as any other
      category.
- [ ] Collapsed categories continue to be skipped by arrow nav in both
      views (existing `deckNavGroups` behavior, unchanged, but re-verify
      after the refactor).
- [ ] `handleDeckListKey` no longer exists in `static/app.js`; both deck
      views' arrow-key handling goes through the shared column-nav
      function.
