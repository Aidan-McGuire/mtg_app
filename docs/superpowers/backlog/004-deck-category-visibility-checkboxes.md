---
id: 004
title: Deck page category visibility checkboxes, replacing click-to-collapse
priority: medium
status: in-progress
branch: item/4-deck-page-category-visibility-checkboxes-replacing-click-to-collapse
created: 2026-08-21
---

## Problem

On the deck page, when `deckState.groupBy` is `'type'`, `'collection-tag'`,
or `'deck-tag'`, each category (a `.group-section` built by
`renderGroupSection`, `static/app.js` ~line 1458) can be individually
collapsed by clicking its header. This is driven by a single shared Set,
`deckGroupCollapsed` (`static/app.js` line 1352, seeded with `'Considering'`
by `resetDeckGroupCollapsed()` at line 1354), passed into `renderGroupedGrid`
(line 1501) at both deck grouped-mode call sites (`renderDeckGrid` line 1987,
`renderDeckText` line 2107). Collapsing a category keeps its header visible,
hides its body, and reorders it to the end via `sortGroupsByCollapsed`
(line 1451).

This has two problems:

1. There's no bulk way to manage which categories are shown — only one
   click-per-header at a time, and the state resets on every `groupBy`
   change (`resetDeckGroupCollapsed()` is called from the `deck-group-by`
   change listener, line 2559) and every deck load (`selectDeck`, line 1883).
   There's no toolbar-level overview of what's hidden.
2. `deckGroupCollapsed` is a single Set keyed only by label text, shared
   across all three grouped modes. A label that happens to match between
   modes (e.g. `'Commander'`, which appears both in type mode's own bucket
   and via `extractCommanderGroup` in tag modes) would leak collapsed state
   between otherwise-unrelated groupings if collapsed near-simultaneously —
   the same class of bug flagged and fixed for `extractCommanderGroup` itself
   in item 001's review.

## Approach

Replace the click-to-collapse mechanism for the deck page's grouped views
(NOT the ungrouped view's trailing "Considering" section, and NOT the
Collection page's own grouped-by-tag view — both keep their current
collapse behavior unchanged) with a toolbar checkbox panel that fully
removes unchecked categories from the DOM (no header, no reordering —
they simply aren't rendered).

### 1. Per-mode hidden-category state

Add, near `deckGroupCollapsed` (`static/app.js` line 1352):

```js
const deckHiddenCategories = { type: new Set(), 'collection-tag': new Set(), 'deck-tag': new Set() };

function resetDeckHiddenCategories() {
  for (const key of Object.keys(deckHiddenCategories)) deckHiddenCategories[key].clear();
}
```

`resetDeckHiddenCategories()` is the *default* state: every category starts
visible. (Hiding lands specifically is handled separately and more broadly
by item 005's type-based "Hide lands" toggle, which catches a land
regardless of what tags it has — a tag-category-based default here couldn't
do that, since a land card with an unrelated tag would still show up under
that other tag's category.)

Call `resetDeckHiddenCategories()` once, alongside `resetDeckGroupCollapsed()`,
in `selectDeck` (line 1883) — hidden-category state resets to defaults on
every deck load, same lifecycle as today's collapse state. Do **NOT** call it
from the `deck-group-by` change listener (line 2557-2561) — unlike
`deckGroupCollapsed` today, hidden-category state is intentionally
independent per mode (keyed by `deckState.groupBy`) and should be remembered
across mode switches within the same deck-viewing session, not reset on
every switch. `deckGroupCollapsed` itself is untouched (still reset on every
`groupBy` change as today) since it continues to serve only the ungrouped
view's "Considering" section.

### 2. Filter hidden groups out before rendering

In both `renderDeckGrid` (line 1969) and `renderDeckText` (line 2086), in the
`if (deckState.groupBy !== 'none')` branch, after building `groups` (and
pushing the "Considering" group onto it, if present — Considering is just
another entry in the grouped-mode list and is subject to the same
show/hide checkbox as any other category here, unlike its separate
always-collapsible treatment in the ungrouped branch below it):

```js
const hidden = deckHiddenCategories[deckState.groupBy];
const visibleGroups = groups.filter(g => !hidden.has(g.label));
renderGroupedGrid(el, visibleGroups, buildDeckCardTile, {});   // grid; buildDeckTextRow for text
```

If `visibleGroups` is empty (every category hidden) but `groups` was not,
show a message instead of an empty grid area, e.g.
`<div class="deck-empty-msg">All categories hidden — check a category above to show cards.</div>`
(mirroring the existing `deck-empty-msg` pattern used a few lines above for
the "no cards match" case in each function).

### 3. Make collapse-by-click optional in the shared render helpers

`renderGroupSection`/`renderGroupedGrid` (lines 1458 and 1501) are shared
with the Collection page's grouped-by-tag view (`renderCollectionGrid`,
which passes `collectionGroupCollapsed` at line 1589) — that call site's
click-to-collapse behavior must be unaffected. Change both functions' last
parameter from a bare `collapsedState` Set to an options object:

```js
function renderGroupSection(container, group, buildTileFn, opts = {}, allGroups = [group]) {
  const { collapsedState } = opts;
  const section = document.createElement('div');
  section.className = 'group-section';
  section.dataset.label = group.label;

  const isCollapsed = collapsedState ? collapsedState.has(group.label) : false;
  const header = document.createElement('div');
  header.className = 'group-header' + (isCollapsed ? ' collapsed' : '');
  header.innerHTML = `
    <span class="group-header-label">${esc(group.label)}</span>
    <span class="group-header-count">${group.cards.length}</span>
    ${collapsedState ? '<span class="group-header-chevron">▾</span>' : ''}`;
  if (collapsedState) {
    header.addEventListener('click', () => {
      // ...unchanged body of today's click handler...
    });
  }

  const body = document.createElement('div');
  body.className = 'group-body' + (isCollapsed ? ' collapsed' : '');
  for (const card of group.cards) body.appendChild(buildTileFn(card));

  section.appendChild(header);
  section.appendChild(body);
  container.appendChild(section);
}

function renderGroupedGrid(container, groups, buildTileFn, opts = {}) {
  container.innerHTML = '';
  const ordered = opts.collapsedState ? sortGroupsByCollapsed(groups, opts.collapsedState) : groups;
  for (const group of ordered) renderGroupSection(container, group, buildTileFn, opts, groups);
}
```

Update all four call sites:

- Collection grid (line 1589): `renderGroupedGrid(grid, groups, tileFn, { collapsedState: collectionGroupCollapsed })` — unchanged behavior.
- Deck grid, grouped branch (line 1987): `renderGroupedGrid(el, visibleGroups, buildDeckCardTile, {})` — no chevron, no click-collapse; hidden groups already filtered out per step 2.
- Deck grid, ungrouped branch's trailing Considering (`renderGroupSection` call, line 1998): `renderGroupSection(el, {...}, buildDeckCardTile, { collapsedState: deckGroupCollapsed })` — unchanged behavior.
- Deck text: same two changes mirrored at lines 2107 and 2118-2123.

### 4. Toolbar "Categories" control

In `static/index.html`, inside `.deck-editor-acts` (around line 68, right
after the `#deck-group-by` select and before `#deck-filter-controls`), add:

```html
<div id="deck-category-controls"></div>
```

In `static/app.js`, add a function (called once from `selectDeck`, after
`buildFilterControls`, and again whenever `groupBy` changes or the grouped
data is re-rendered — simplest: call it at the top of `renderDeckContent`,
line 1948, so it's always in sync with the current mode/groups):

```js
function renderDeckCategoryControls() {
  const container = document.getElementById('deck-category-controls');
  if (deckState.groupBy === 'none') { container.innerHTML = ''; return; }

  const mainCards = deckState.deckCards.filter(c => !c.is_considering);
  const groups = groupMainCardsForRender(mainCards, deckState.groupBy);
  if (deckState.deckCards.some(c => c.is_considering)) groups.push({ label: 'Considering', cards: [] });

  const hidden = deckHiddenCategories[deckState.groupBy];
  container.innerHTML = '';

  const btn = document.createElement('button');
  btn.className = 'categories-btn action-btn';
  btn.textContent = 'Categories';
  const panel = document.createElement('div');
  panel.className = 'categories-panel hidden';
  btn.addEventListener('click', () => panel.classList.toggle('hidden'));

  for (const g of groups) {
    const lab = document.createElement('label');
    lab.className = 'check-pill';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = !hidden.has(g.label);
    cb.addEventListener('change', () => {
      if (cb.checked) hidden.delete(g.label); else hidden.add(g.label);
      renderDeckContent();
    });
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(g.label));
    panel.appendChild(lab);
  }

  container.appendChild(btn);
  container.appendChild(panel);
}
```

Call `renderDeckCategoryControls()` from `renderDeckContent` (line 1948,
before or after the grid/text render — order doesn't matter since it reads
`deckState.deckCards` directly, not the rendered DOM). Note this recomputes
the full `groups` list a second time (independent of the filtered/sorted
`mainCards` used for actual rendering) — deliberately using the
*unfiltered-by-search* deck card list, so a category doesn't disappear from
the checkbox panel just because the user typed something into
`#deck-content-search` that happens to hide all of that category's cards.

Reuse the existing `.filter-panel`/`.check-pill` CSS patterns (`static/style.css`,
searchable via `.filter-panel` and `.check-pill`) for `.categories-panel` —
same panel/positioning/checkbox styling, new class names so it doesn't
collide with the Filters panel's own open/close state. Follow the existing
`.filter-panel:not(.hidden)` outside-click-closes-panel handling
(`static/app.js` ~lines 1203 and 1274) by adding `.categories-panel` to
those same querySelectorAll calls.

### Out of scope

- The Collection page's grouped-by-tag view keeps its existing
  click-to-collapse behavior entirely unchanged.
- The ungrouped deck view's trailing "Considering" section keeps its
  existing click-to-collapse behavior (still collapsed by default via
  `deckGroupCollapsed`/`resetDeckGroupCollapsed`) entirely unchanged.
- No localStorage/persistence — hidden-category state (like today's collapse
  state) lives only in memory and resets to defaults on deck (re)load.
- No "show all" / "hide all" bulk toggle in the panel — just per-category
  checkboxes.
- Hiding lands specifically is out of scope here — see item 005's dedicated,
  type-based "Hide lands" toggle, which is tag-independent and catches every
  land regardless of what categories it'd otherwise appear in.
- notes.md idea #3 ("default tag all lands as land, including mdfc lands")
  is separate, unimplemented scope — this item does not touch tagging
  behavior.

## Acceptance criteria

- [ ] On the deck page with `Group: Card type` selected, a "Categories"
      button appears in the toolbar; clicking it opens a panel with one
      checkbox per currently-present type-mode category (Commander,
      Creature, Instant, Sorcery, Enchantment, Artifact, Planeswalker, Land,
      Other, Considering — only ones with cards), all checked (visible) by
      default on a freshly loaded/switched deck.
- [ ] Unchecking a category removes its entire section (header and cards)
      from both the grid and text views immediately, with no reordering
      artifact and no way to still see its header.
- [ ] Re-checking a category restores it to its normal position (order
      matches `groupMainCardsForRender`'s natural output, not "last since it
      was hidden").
- [ ] Switching to `Group: Collection tag` or `Group: Deck tag` shows its
      own independent set of checkboxes (tag names, plus Commander/
      Considering as applicable), all checked by default; hiding a category
      in one mode has no effect on any other mode's checkboxes or
      visibility, including a same-named category (e.g. Commander) in a
      different mode.
- [ ] Hiding every category shows an explanatory empty-state message rather
      than a blank grid/text area.
- [ ] The "Categories" button/panel does not appear when `Group: None` is
      selected.
- [ ] The deck page's ungrouped view still shows its "Considering" section
      collapsed by default with click-to-collapse working exactly as today
      (unaffected by this change).
- [ ] The Collection page's `Group: Tag` view still supports click-to-collapse
      on each category exactly as today (unaffected by this change).
- [ ] Reloading the page or switching to a different deck and back resets
      every mode's hidden-category state back to all-visible — no
      persistence across loads.
- [ ] Switching `groupBy` away and back within the same deck-viewing session
      (without a reload) preserves whatever hide/show choices were made in
      each mode.
