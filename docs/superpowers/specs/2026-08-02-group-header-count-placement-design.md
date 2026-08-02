# Group header count next to name

## Problem

Notes.md, Deck Page item #5: "move category count next to category name."
`renderGroupSection`'s header markup already renders label, count, then
chevron in that DOM order, but `.group-header-label { flex: 1; ... }`
(`static/style.css:1169-1175`) makes the label consume all remaining flex
space, pushing the count and chevron flush to the header's right edge —
visually far from the name instead of next to it.

This is the one shared header markup used by every collapsible group
across the app (Deck Grid, Deck Text, and the Collection page's grouped
grid), so the fix applies everywhere automatically.

## Fix

Pure CSS, no JS/markup changes:

- Remove `flex: 1` from `.group-header-label` — it no longer needs to grow;
  the existing `.group-header { gap: 8px }` still keeps a small, consistent
  gap between label, count, and chevron.
- Add `margin-left: auto` to `.group-header-chevron` — it's the only
  element that still needs to be pushed to the header's right edge, since
  the label no longer does that job.

Result: "Label  Count" sit adjacent at the left, chevron stays pinned at
the right edge, matching today's collapse/expand click target and visual
balance.

## Out of Scope

- No change to the count's number itself (still `group.cards.length`,
  distinct-card count, not total quantity — unchanged from existing
  behavior).
- No visual restyling (parentheses, color, size) of the count — same
  `.group-header-count` styling as today, just repositioned.

## Testing

No JS test applies (pure CSS). Manual verification in a running browser
(`uvicorn app:app --reload`): open a grouped Deck Grid/Text view and the
Collection page's grouped grid, confirm the count sits immediately next to
each group's name (not flush-right), and the chevron is still pinned to
the right edge and still rotates on collapse/expand as before.
