---
id: 031
title: Deck mana curve in the list-view preview panel
priority: low
status: in-review
branch: item/31-deck-mana-curve-in-the-list-view-preview-panel
created: 2026-08-27
---

## Problem

The deck page has no way to see a deck's mana curve (card count by mana
value) at a glance — the only per-card CMC info is the `mana_cost` string
shown per card. `#deck-preview-panel` already exists as a sidebar that's
visible only in the deck's list (text) view (`renderDeckContent`,
`static/app.js:2076-2088`, hides the panel entirely in grid view — hovering
a grid tile shows its art directly on the tile instead), currently used
only to preview whichever card is hovered/focused.

## Approach

Add a new `renderDeckManaCurve()` function that computes a small bar-chart
data set from `deckState.deckCards`:

- 8 buckets: CMC 0, 1, 2, 3, 4, 5, 6, and "7+" (any `cmc >= 7`, rounded via
  `Math.round(c.cmc ?? 0)`).
- Excludes, from every bucket: the commander (`c.is_commander`), Considering
  cards (`c.is_considering` — not actually in the deck yet), and lands
  (`(c.type_line || '').includes('Land')`, matching the existing
  `hideLands` filter's own land-detection check at `static/app.js:280`).
- Each remaining card contributes its full `quantity` to its bucket (a 4x
  Lightning Bolt counts as 4), matching how deckbuilding sites conventionally
  compute a curve.
- **Not filtered by the content-search box** — this reflects the whole
  deck's composition regardless of what's currently searched/filtered,
  matching how the deck editor header's own `(${total})` count already
  works (`static/app.js:2067-2069`).

Render as a small CSS bar chart: each bucket is a column with a bar whose
height is `count / max(bucket counts, 1) * 100%`, a count label, and a CMC
label underneath (`0`, `1`, ... `7+`). Style with the app's existing
`--accent`/`--muted` CSS variables to match its current minimalist look —
no new color palette or charting library.

Wire it into `renderDeckPreviewPanel()` (`static/app.js:2045-2062`): prepend
the curve's markup unconditionally, before the existing
card-preview-or-empty-state block, so it's always visible in list view
regardless of whether a card is currently hovered/focused. No changes needed
to the panel's grid-view-hides/list-view-shows logic — it already does the
right thing.

**Out of scope:** no interactivity on the bars (e.g. click-to-filter-by-CMC)
— this is a read-only summary. No curve in grid view — the preview panel
doesn't render there today, and this doesn't change that.

## Acceptance criteria

- [ ] In the deck's list (text) view, the preview panel shows a mana curve
      with 8 buckets (0-6, 7+) reflecting the current deck's non-land,
      non-commander, non-Considering cards, counted by total copies.
- [ ] The curve is visible whether or not a card is currently
      hovered/focused (i.e., it doesn't disappear when the panel shows its
      "Hover or focus a card…" empty state).
- [ ] Typing into the content-search box (filtering the visible card list)
      does not change the curve.
- [ ] Adding/removing cards, changing quantities, toggling a card's
      Considering state, or changing the commander updates the curve on the
      next render (i.e., it reads live from `deckState.deckCards`, not a
      stale snapshot).
- [ ] The curve does not render in the deck's grid view (panel stays
      hidden there, unchanged from today).
