---
id: 011
title: Deck grid view tile size matches Collection view
priority: medium
status: in-review
branch: item/11-deck-grid-view-tile-size-matches-collection-view
created: 2026-08-23
---

## Problem

Item 008 (accepted 2026-08-22) deliberately enlarged deck grid view's
tiles to `minmax(280px, 1fr)` — bigger than every other card grid in the
app, which shares `minmax(240px, 1fr)` (`.card-grid`, style.css:125, and
the generic `.group-body`, style.css:1203, both used by Collection view).
That was intentional at the time, using space freed by hiding the deck
preview panel in grid view.

The user still wants deck grid tiles the same size as Collection view's,
overriding that part of 008's outcome (confirmed explicitly — this isn't a
stale/forgotten note; 008's size bump is the one being undone here). The
preview-panel-hidden part of 008 is not being touched.

## Approach

Revert the two CSS overrides item 008 introduced, both in
`static/style.css`:

1. `.deck-grid-view` (line ~769-775): change
   `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));`
   back to
   `grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));`
   (matches `.card-grid`, style.css:125).

2. Remove the `#deck-grid-view .group-body` override (line ~1210-1212)
   entirely:
   ```css
   #deck-grid-view .group-body {
     grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
   }
   ```
   Removing it lets the shared `.group-body` rule (style.css:1201-1207,
   already `minmax(240px, 1fr)`) apply to deck grid view's grouped mode,
   same as it already does for Collection's grouped view.

CSS-only change — no JS changes, no HTML changes.

### Out of scope

- The preview-panel-hidden-in-grid-view part of item 008 stays as-is; only
  the tile-size bump is reverted.
- No changes to deck list/text view, which has its own sizing untouched by
  008.
- No changes to `.card-grid`/`.group-body`'s shared 240px value itself.

## Acceptance criteria

- [x] Deck grid view (ungrouped, `groupBy: 'none'`) renders tiles at the
      same minimum width (240px) and column count as Collection view, for
      the same window width.
- [x] Deck grid view in grouped mode (type / collection-tag / deck-tag)
      also renders tiles at 240px minimum width, matching Collection's
      grouped view.
- [x] Deck preview panel remains hidden in grid view (unaffected by this
      change) and still shows in list/text view.
- [x] Collection view and Cards page tile sizing are unchanged.
