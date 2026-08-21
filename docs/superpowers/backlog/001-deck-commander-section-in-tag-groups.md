---
id: 001
title: Commander gets exclusive section in deck/collection-tag grouped views
priority: medium
status: in-progress
branch: item/1-commander-gets-exclusive-section-in-deck-collection-tag-grouped-views
created: 2026-08-21
---

## Problem

On the deck page, `groupCardsByType` (used when `deckState.groupBy === 'type'`)
already pulls the commander card out into its own leading `Commander` group,
excluded from the type buckets — see `groupCardsByType` in `static/app.js`
(currently around line 1429).

`groupCards` (the generic tag-grouping function, used when `groupBy` is
`'deck-tag'` or `'collection-tag'`, at `static/app.js` around line 1396) has
no equivalent special case. Today, when grouping the deck by deck-tag or
collection-tag:

- An untagged commander lands in the generic `Untagged` group like any other
  untagged card.
- A tagged commander appears only inside its tag's group(s), mixed in with
  non-commander cards.

There's no way to quickly spot the commander when grouped by tag.

## Approach

Add a helper in `static/app.js` that extracts the commander from a card
array before it's grouped by tag:

```js
function extractCommanderGroup(cards) {
  const commander = cards.find(c => c.is_commander);
  if (!commander) return { commanderGroup: null, rest: cards };
  return { commanderGroup: { label: 'Commander', cards: [commander] }, rest: cards.filter(c => !c.is_commander) };
}
```

In both `renderDeckGrid` and `renderDeckText` (`static/app.js`, the two
call sites that currently do
`groupCards(mainCards, deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags')`,
around lines 1990 and 2112), change the branch so that when `groupBy` is
`'deck-tag'` or `'collection-tag'` (i.e. NOT `'type'`, which already handles
this correctly on its own):

1. Call `extractCommanderGroup(mainCards)` to split out `commanderGroup` and
   `rest`.
2. Call `groupCards(rest, tagField)` instead of `groupCards(mainCards, tagField)`.
3. If `commanderGroup` is non-null, `groups.unshift(commanderGroup)` before
   the existing `Considering` group is appended and before
   `renderGroupedGrid`/the text-view equivalent is called, so `Commander`
   renders first, ahead of the alphabetically-sorted tag groups.

Leave `groupBy === 'type'` and `groupBy === 'none'` untouched — both already
handle the commander correctly (type mode via its own internal bucket,
ungrouped mode by pinning the commander first in the sort comparator).

This only affects the deck page. `groupCards` is also called from the
collection page's grouped-by-tag view (`static/app.js` around line 1593,
`groupCards(filtered, 'collection_tags')`), but that call site is untouched
by this change since we're not modifying `groupCards` itself — only wrapping
its call sites on the deck page. Collection cards don't carry a meaningful
`is_commander` flag in that context, so this is a non-issue either way.

## Acceptance criteria

- [ ] On the deck page grid view, with `groupBy` set to `deck-tag` or
      `collection-tag`, the commander card appears in its own leading
      `Commander` section, regardless of whether it has any deck/collection
      tags.
- [ ] The commander does NOT also appear in any tag-based group it would
      otherwise belong to (exclusive placement, matching how `type` mode
      already excludes it from type buckets).
- [ ] The same behavior applies to the deck page's text view.
- [ ] `groupBy === 'type'` behavior is unchanged (still handled by
      `groupCardsByType`'s existing internal commander bucket).
- [ ] `groupBy === 'none'` behavior is unchanged (commander still pinned
      first via the existing sort comparator).
- [ ] The collection page's grouped-by-tag view is unaffected.
- [ ] A deck with no commander designated renders grouped views exactly as
      it does today (no empty `Commander` section appears).

## Review feedback

Code review on `item/1-commander-gets-exclusive-section-in-deck-collection-tag-grouped-views`
found a data-loss bug in the implementation. Note: this repo's app has no
constraint against multiple `is_commander=true` rows in `deck_cards` (partner
commanders) — `toggleCommander` and `PATCH /api/decks/{id}/cards/{card_id}`
only ever set/clear the flag on the single clicked card — so this is a
reachable, real state, not a hypothetical.

**Blocking bug** — `extractCommanderGroup` (`static/app.js` ~line 1425)
mismatches its own `find` and `filter`:

```js
function extractCommanderGroup(cards) {
  const commander = cards.find(c => c.is_commander);
  if (!commander) return { commanderGroup: null, rest: cards };
  return { commanderGroup: { label: 'Commander', cards: [commander] }, rest: cards.filter(c => !c.is_commander) };
}
```

`cards.find(...)` keeps only the *first* commander-flagged card, but
`cards.filter(c => !c.is_commander)` strips *every* commander-flagged card out
of `rest`. In a deck with two `is_commander` cards, the second one is dropped
from both `commanderGroup.cards` and `rest` — it disappears entirely from the
grid/text view under `groupBy: 'deck-tag'`/`'collection-tag'`, while still
counting toward the deck total. `groupCardsByType` (the existing `type`-mode
handler, unchanged by this item) does not have this bug — it loops and pushes
every `is_commander` card into its `Commander` bucket — so the same deck now
renders inconsistently across group-by modes.

(Note: this exact flawed snippet came from this item's own "Approach"
section above — fix the code to match the fix below rather than the spec as
originally written.)

Fix: collect *all* commander-flagged cards, not just the first:

```js
function extractCommanderGroup(cards) {
  const commanders = cards.filter(c => c.is_commander);
  if (!commanders.length) return { commanderGroup: null, rest: cards };
  return { commanderGroup: { label: 'Commander', cards: commanders }, rest: cards.filter(c => !c.is_commander) };
}
```

Add a regression test in `tests/js/extract-commander-group.test.mjs` covering
a two-commander input (both must land in `commanderGroup.cards`, neither in
`rest`) — the existing tests only cover zero/one commander.

**Also noticed, non-blocking (fix only if time allows; do not let these
block re-finishing this item):**

- The new Commander group's collapse state (`deckGroupCollapsed`, keyed by
  the label `'Commander'`) is shared with `groupCardsByType`'s own Commander
  bucket. Collapsing Commander under `groupBy: 'type'` leaves it
  pre-collapsed after switching to `groupBy: 'deck-tag'`/`'collection-tag'`,
  and vice versa, even though the user never touched it in that mode.
- The commander-extraction `if`/`else` block is duplicated verbatim between
  `renderDeckGrid` and `renderDeckText` rather than factored into one shared
  helper — a future change to the extraction logic has to be applied in both
  places.
