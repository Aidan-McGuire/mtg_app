---
id: 007
title: Add "Group: Type" option to the Collection page
priority: medium
status: in-progress
branch: item/7-add-group-type-option-to-the-collection-page
created: 2026-08-21
---

## Problem

The Deck page supports grouping by card type (`Group: Card type`,
`static/index.html` line 70; `groupCardsByType`, `static/app.js` line 1423),
but the Collection page (`#collection-group-by`, `static/index.html` line
41-43) only offers `Group: None` / `Group: Tag`. There's no way to see the
collection organized by card type (Creature/Instant/Sorcery/etc.).

## Approach

Reuse `groupCardsByType` (`static/app.js` line 1423-1443) as-is for the
Collection page. It only branches on `card.is_commander`
(line 1427) to build a leading Commander bucket; collection card objects
(from `API.getCollection()`) never have an `is_commander` field, so that
check is always falsy for them — the Commander bucket stays empty and is
filtered out before being returned (`if (buckets[label].length) ...`, line
1440), so no empty "Commander" section ever appears on the Collection page.
No changes needed to `groupCardsByType` itself.

### 1. Add the option

In `static/index.html`, inside the `#collection-group-by` select (line
41-43):

```html
<select id="collection-group-by" class="group-by-select">
  <option value="none">Group: None</option>
  <option value="type">Group: Type</option>
  <option value="collection-tag">Group: Tag</option>
</select>
```

### 2. Update state comment

`collectionState.groupBy` (`static/app.js` ~line 1347): update the comment
from `// 'none' | 'collection-tag'` to `// 'none' | 'type' | 'collection-tag'`.

### 3. Branch in `renderCollectionGrid`

`renderCollectionGrid` (`static/app.js` line 1563-1595) currently has a
binary `if (collectionState.groupBy !== 'none')` branch (line 1586) that
assumes the only grouped mode is tag-based. Change it to a 3-way dispatch:

```js
if (collectionState.groupBy === 'type') {
  const groups = groupCardsByType(filtered);
  for (const g of groups) g.cards.sort(cmp);
  renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), collectionGroupCollapsed);
} else if (collectionState.groupBy === 'collection-tag') {
  const groups = groupCards(filtered, 'collection_tags');
  for (const g of groups) g.cards.sort(cmp);
  renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), collectionGroupCollapsed);
} else {
  const frag = document.createDocumentFragment();
  for (const card of [...filtered].sort(cmp)) frag.appendChild(buildCardTile(card, { showOwnedBadge: false }));
  grid.appendChild(frag);
}
```

(Adjust the exact `renderGroupedGrid` call signature to match whatever it
is at implementation time — item 004, if already landed, changes its last
parameter from a bare `collapsedState` Set to an options object; either
way, both grouped branches above should pass `collectionGroupCollapsed`
through however that item's call sites do, matching the existing
`collection-tag` branch's own pattern exactly.)

### Out of scope

- `collectionGroupCollapsed` (`static/app.js` line 1351) remains a single
  Set shared across both grouped modes, keyed only by label text — a
  category folded in one mode (e.g. a `type` bucket named "Land") stays
  folded if you switch to `collection-tag` mode and it happens to have a
  same-named tag category, and vice versa. This is a pre-existing pattern
  (not introduced by this item), just newly *reachable* now that Collection
  has two real grouped modes instead of one. Not fixing it here — if it
  becomes a real annoyance, that's its own follow-up item (mirroring how
  item 004 fixed the equivalent issue for the Deck page).
- No changes to the Deck page's own `Group: Card type` option or behavior.
- No changes to `groupCardsByType` itself.

## Acceptance criteria

- [ ] The Collection page's group-by select shows "Group: None", "Group:
      Type", and "Group: Tag" in that order.
- [ ] Selecting "Group: Type" groups the collection grid into
      Creature/Instant/Sorcery/Enchantment/Artifact/Planeswalker/Land/Other
      sections (only non-empty ones shown), in that fixed order — no
      "Commander" section ever appears.
- [ ] Cards within each type section are sorted according to the current
      sort control, same as within tag-mode sections today.
- [ ] Clicking a section header still collapses/expands it exactly like tag
      mode does today.
- [ ] Switching between "Group: Type", "Group: Tag", and "Group: None"
      re-renders correctly with no leftover sections from the previous mode.
- [ ] The Deck page's own type-grouping option and behavior are unaffected.
- [ ] Full test suite (pytest + JS) still passes.
