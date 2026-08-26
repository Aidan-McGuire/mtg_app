---
id: 013
title: Owned indicator on deck text view
priority: medium
status: in-progress
branch: item/13-owned-indicator-on-deck-text-view
created: 2026-08-26
---

## Problem

The deck grid view shows a green checkmark badge (`OWNED_BADGE_HTML`, see
`static/app.js`) over a card's image when the player owns at least one copy
(collection quantity > 0). The deck **text** view (`buildDeckTextRow` in
`static/app.js`, rendered rows in `#deck-text-view`) has no image and shows
no ownership indicator at all — there is currently no way to tell, in text
view, whether a listed card is owned.

## Approach

Text rows have no image to badge, so mirror ownership with a row-level
style instead of a badge element:

- In `buildDeckTextRow(card)` (`static/app.js`), add an `owned` class to the
  row's `className` when `qty(card.id) > 0` (the existing `qty()` helper
  already used by the grid tile and by `applyFilters`).
- In `static/style.css`, add a `.deck-text-row.owned` rule giving the row a
  subtle visual treatment consistent with the existing `.qty-label.owned`
  green-tint convention used elsewhere (e.g. a thin left border or faint
  background tint in the same green as `.card-owned-badge`/`.qty-label.owned`
  — reuse that color rather than inventing a new one). Keep it subtle: this
  is a whole-row treatment, not a badge, so it must not overpower the
  existing `.focused` outline or `.is-commander`/`.is-considering` styling
  that can co-occur on the same row.
- No new DOM element, no changes to `renderDeckText`, no changes to the
  grid view or the owned-badge refresh logic in `refreshQtyInDOM` (that
  function targets `[data-owned-wrap-for]` wrapper elements, which text
  rows don't have and don't need — the `owned` class is derived once per
  render from `qty()`, which is already fresh at render time). If ownership
  changes while a deck is open (e.g. via the collection view in another
  tab — not currently possible in this single-page app, so out of scope),
  no live-update wiring is needed.

## Acceptance criteria

- [x] Opening a deck's text view, cards with collection quantity > 0 are
      visually distinguishable from cards with quantity 0.
- [x] The visual treatment does not visually conflict with `.focused`,
      `.is-commander`, or considering-row styling when combined.
- [x] Grid view's existing owned badge behavior is unchanged.
- [x] No new elements added to the row's DOM structure — verified by
      diffing `buildDeckTextRow`'s template against its current form (only
      a class name changes).
