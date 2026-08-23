---
id: 009
title: Deck list view arrow navigation crosses categories on Down/Up
priority: medium
status: queued
branch:
created: 2026-08-23
---

## Problem

On the deck page, two keyboard handlers drive arrow-key focus navigation:
`handleDeckGridKey` (grid view) and `handleDeckListKey` (list/text view),
both in `static/app.js`.

Grid view already does the right thing: `handleDeckGridKey` (app.js:2289)
lets Down/Up cross from the last/first row of one category into the
next/previous category when the current row runs out.

List view does not: `handleDeckListKey` (app.js:2255) clamps Up/Down at the
edges of the current category — pressing Down on the last row of a category
does nothing — and instead uses Left/Right to jump entire categories
(`nextG = pos.g + (ArrowRight ? 1 : -1)`, then focuses that category's first
row). That's backwards from how a single-column list should behave: a user
holding Down should be able to walk the whole deck top-to-bottom, not have
to switch to Left/Right at category boundaries.

Separately, "Untagged" cards (cards with no deck tag) already render as a
normal category — `groupCards` (app.js:1385) always emits an "Untagged"
bucket, sorted last, with its own checkbox in the Categories panel like any
other tag — so they're already reachable by arrow nav today. This item adds
an explicit acceptance criterion to confirm that rather than assuming it.

## Approach

Rework `handleDeckListKey` (app.js:2255-2273) to match the category-crossing
pattern `handleDeckGridKey` already uses (app.js:2307-2328):

- **ArrowDown**: if there's a next row in the current category
  (`pos.i + 1 < tiles.length`), focus it. Otherwise, if there's a next group
  (`groups[pos.g + 1]`), focus its first row. Otherwise (last row of the
  last category), do nothing.
- **ArrowUp**: if there's a previous row in the current category
  (`pos.i - 1 >= 0`), focus it. Otherwise, if there's a previous group
  (`groups[pos.g - 1]`), focus its last row. Otherwise (first row of the
  first category), do nothing.
- **ArrowLeft / ArrowRight**: remove this branch entirely — list view is
  single-column, so once Down/Up handle category crossing, Left/Right have
  no remaining meaning. Let them fall through unhandled (no `preventDefault`,
  no-op), same as any other unhandled key in this function.

No changes to `handleDeckGridKey`, `deckNavGroups`, `groupCards`, or any
other grouping/rendering logic — this item touches `handleDeckListKey` only.

### Out of scope

- Grid view keyboard behavior — already correct, not touched.
- The text view's single-column layout itself (a separate, not-yet-refined
  idea: "make text view have two columns") — out of scope here; if that
  ships later, this item's Down/Up-crosses-categories behavior should still
  hold per-column, but reconciling the two is that future item's problem.
- Any change to how categories are computed, hidden, or ordered.

## Acceptance criteria

- [ ] In deck list view, with a deck grouped into 3+ categories (including
      some untagged cards), pressing Down repeatedly from the first card
      walks every card in every visible category, top to bottom, in order,
      including crossing from the last card of one category straight into
      the first card of the next.
- [ ] Pressing Up from the first card of a category (that isn't the first
      category) moves focus to the last card of the previous category.
- [ ] Pressing Down on the very last card of the last category does nothing
      (no error, focus stays put). Pressing Up on the very first card of the
      first category does nothing.
- [ ] Pressing Left or Right in list view does nothing (no focus change, no
      thrown error).
- [ ] Untagged cards appear in an "Untagged" category in list view and are
      reachable via the same Down/Up traversal as any other category.
- [ ] Grid view keyboard navigation (Up/Down/Left/Right) is unchanged —
      manually re-verify it still crosses categories on Down/Up at row
      boundaries and moves within a row on Left/Right.
- [ ] Collapsed categories continue to be skipped by arrow nav in list view
      (existing `deckNavGroups` behavior, unchanged, but re-verify after the
      edit).
