---
id: 015
title: Grid-view categories span full width instead of side-by-side columns
priority: medium
status: in-progress
branch: item/15-grid-view-categories-span-full-width-instead-of-side-by-side-columns
created: 2026-08-26
---

## Problem

When a grid view (card browser `#card-grid`, collection browser
`#collection-grid`, or deck grid view `.deck-grid-view`) is grouped into
categories (by type, tag, etc. via `renderGroupedGrid` in
`static/app.js`), each category renders as a `.group-section`. Because
`.group-section` is a direct child of the outer grid container
(`.card-grid` / `.deck-grid-view`, both `display: grid;
grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))`) and is
**not** given `grid-column: 1 / -1`, each category is placed as a single
item into one of the outer grid's auto-fill columns (~240–400px wide).
The category's own nested grid (`.group-body`, same
`repeat(auto-fill, minmax(240px, 1fr))` rule, defined in `static/style.css`
around line 1208) then only has room for one card per row inside that
narrow track. The net effect: categories sit side by side as columns, each
showing only one full card per row, instead of each category spanning the
full available width with multiple cards per row. This was previously a
deliberate choice (see the comment above `.group-section-full` in
`static/style.css`: "those intentionally render as columns") but is now
considered awkward and should be changed.

Note: `#deck-text-view .group-body` is separately overridden to a fixed
2-column row grid and `.deck-text-view` itself is `display: flex;
flex-direction: column` (not `display: grid`), so text view is unaffected
by this — this item is grid views only.

## Approach

- In `static/style.css`, change the base `.group-section` rule to always
  span the full grid width: add `grid-column: 1 / -1;` directly to
  `.group-section` (currently only `margin-bottom: 20px;`).
- Delete the now-redundant `.group-section-full` rule and its
  `grid-column: 1 / -1` declaration, since every `.group-section` now
  behaves that way unconditionally.
- In `static/app.js`, remove the one place that adds the
  `group-section-full` class (search for `.classList.add('group-section-full')`,
  currently applied to the trailing "Considering" section in the deck grid
  view) — its class list should just use the default `.group-section`
  class, since the full-width behavior is no longer conditional.
- Update the stale comment above the old `.group-section-full` rule (the
  "Do NOT apply to grouped-by-tag sections... those intentionally render
  as columns" comment) — remove it along with the rule; it describes
  behavior this item removes.
- No JS layout logic changes beyond dropping that one class-list addition
  — `renderGroupedGrid`'s structure (`.group-section` > `.group-header` +
  `.group-body`) is unchanged, only which grid track(s) the section
  occupies.

## Acceptance criteria

- [ ] In the card browser, collection browser, and deck grid view, grouping
      by any available category renders each category spanning the full
      grid width, with multiple cards per row inside each category
      (whatever fits at 240px-min tile width), stacked vertically
      category-by-category — not side-by-side single-card columns.
- [ ] The deck grid view's trailing "Considering" section still renders
      correctly (full width, same as every other category now).
- [ ] Deck text view's grouped rendering (2-column row layout) is visually
      unchanged.
- [ ] Collapsing/expanding a category (`.group-header.collapsed` /
      `.group-body.collapsed`) still works the same as before.
- [ ] No remaining references to `.group-section-full` in `static/app.js`
      or `static/style.css`.
