---
id: 032
title: Deck list-view arrow-key navigation scrolls with a buffer instead of pinning rows to the viewport edge
priority: medium
status: in-progress
branch: item/32-deck-list-view-arrow-key-navigation-scrolls-with-a-buffer-instead-of-pinning-rows-to-the-viewport-edge
created: 2026-08-27
---

## Problem

Arrow-key navigation in the deck's list (text) view uses `focusDeckTile`
(`static/app.js:2352-2357`), which calls
`el.scrollIntoView({ block: 'nearest' })`. `block: 'nearest'` scrolls the
minimum distance needed to bring the element into view, so a newly-focused
row lands flush against the scroll container's edge — navigating down pins
the highlighted row right at the bottom of the visible area, making it hard
to see what's below and awkward to keep arrowing through the list.

Investigating this also surfaced a related issue: `#deck-content-search`
(`static/style.css:766-769`) is `position: sticky; top: 0` inside the same
scroll container (`.deck-content-col`), but nothing accounts for its height
when scrolling — so arrow-**up** navigation can tuck a row underneath the
sticky search box instead of stopping below it.

## Approach

Both are fixed with the same native CSS mechanism, no JS changes:
`scroll-margin-top`/`scroll-margin-bottom` are respected by
`Element.scrollIntoView()` directly, so `focusDeckTile`'s existing call
needs no changes.

Add to `.deck-text-row` in `static/style.css` (its existing rule block,
`static/style.css:925-934`):

```css
.deck-text-row {
  ...
  scroll-margin-top: 48px;     /* clears the sticky #deck-content-search box (~44px incl. its margin) */
  scroll-margin-bottom: 40px;  /* buffer so the row isn't pinned flush to the bottom edge */
}
```

Because the browser can never scroll a container past its actual max scroll
position, a row near the true end of the list simply lands as far down as
the container can go — there's no artificial gap forced below it when
there's genuinely nothing left to show, which already satisfies "unless
there is nothing else below the current selection" with no extra logic.

**Out of scope:** the deck grid view (`.deck-card-tile`) and the Cards
browser page grid share the same `scrollIntoView({ block: 'nearest' })`
pattern (`static/app.js:835`) but weren't reported as broken and aren't part
of this fix — the raw report was specific to list view.

## Acceptance criteria

- [ ] In the deck's list (text) view, arrow-key-navigating down through rows
      keeps a visible gap below the highlighted row (roughly one row's
      height) instead of pinning it flush to the bottom of the visible
      area, as long as there are more rows below it.
- [ ] Arrow-key-navigating to the last row(s) in the list scrolls as far as
      the container allows and does not error or leave dead space beyond
      the actual content.
- [ ] Arrow-key-navigating up through rows keeps the highlighted row fully
      visible below the sticky `#deck-content-search` box, never partially
      hidden underneath it.
- [ ] Deck grid view and the Cards browser page's scroll-into-view behavior
      are unchanged.
