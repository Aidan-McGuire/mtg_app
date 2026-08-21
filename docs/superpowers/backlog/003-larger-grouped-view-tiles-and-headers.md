---
id: 003
title: Larger card tiles and more prominent headers in grouped views
priority: medium
status: in-progress
branch: item/3-larger-card-tiles-and-more-prominent-headers-in-grouped-views
created: 2026-08-21
---

## Problem

Grouped/category views (deck page grouped by type/deck-tag/collection-tag,
and the collection page grouped by collection-tag) render card tiles and
category headers too small: card tiles use a `140px` grid minimum
(`.group-body` in `static/style.css`, currently around line 1198) and
category headers use `11px` text (`.group-header-label` /
`.group-header-count`, currently around lines 1177-1187), making both hard
to scan.

## Approach

In `static/style.css`, apply these changes. `.group-body` and
`.group-header*` are shared classes used by both the deck page's grouped
view and the collection page's grouped-by-tag view, so this intentionally
affects both — there's no collection-only or deck-only scoping here.

1. `.group-body` grid tile minimum, currently:
   ```css
   .group-body {
     display: grid;
     grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
     gap: 10px;
   }
   ```
   Change `minmax(140px, 1fr)` to `minmax(170px, 1fr)`.

2. `.group-header-label` font-size: `11px` → `13px` (keep `font-weight: 700`,
   `text-transform: uppercase`, `letter-spacing: 0.5px`, `color: var(--accent)`
   unchanged).

3. `.group-header-count` font-size: `11px` → `12px` (keep `color: var(--muted)`
   unchanged).

4. `.group-header` padding: `6px 4px` → `8px 4px`, and `margin-bottom: 10px`
   → `12px` (keep `border-bottom`, `color: var(--muted)`, flex/gap/cursor
   properties unchanged).

Do not change `.deck-grid-view`'s own `minmax(140px, 1fr)` (around line
768) — that's the ungrouped deck grid, out of scope here. Do not change
`#deck-text-view .group-body` (the text-view override, around line 888) —
it uses `display: flex`, not the grid, so it's unaffected by the
`.group-body` grid-template-columns change regardless.

## Acceptance criteria

- [ ] Card tiles in the deck page's grouped view (any of type/deck-tag/
      collection-tag grouping) render with a minimum width of 170px instead
      of 140px.
- [ ] Card tiles in the collection page's grouped-by-collection-tag view
      also render with the 170px minimum.
- [ ] Category header labels render at 13px, counts at 12px, both visibly
      larger than before.
- [ ] The deck page's ungrouped grid view (`.deck-grid-view`) is unaffected
      — still 140px minimum tiles.
- [ ] The deck page's text view is unaffected (no grid tiles there to
      resize; row layout unchanged).
- [ ] No horizontal overflow introduced at typical desktop window widths.
