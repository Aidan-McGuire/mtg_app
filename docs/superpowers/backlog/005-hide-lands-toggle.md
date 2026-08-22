---
id: 005
title: Type-based "Hide lands" toggle on Collection and Deck pages
priority: medium
status: in-progress
branch: item/005-hide-lands-toggle
created: 2026-08-21
---

## Problem

There's no quick way to hide land cards on the Collection or Deck pages.
The existing "Types" filter (`TYPE_OPTIONS`, `static/app.js` line 177-178,
rendered in the Filters panel by `buildFilterControls` lines 436-454) is an
*allow-list*: checking "Land" narrows the view to *only* lands; there's no
single click to exclude them, and doing so today would require checking
every other type (Creature, Instant, Sorcery, Enchantment, Artifact,
Planeswalker, Battle) one at a time.

A tag-based approach (e.g. hiding a "Land"/"land" category in a grouped
view, as originally proposed for item 004) doesn't fully solve this either:
`groupCards` (`static/app.js` line 1364) puts a card in every tag group it
belongs to, so a land that also happens to have some other tag would still
show up under that other tag's category even if the "Land" category itself
were hidden. Hiding lands needs to be independent of tags entirely, based on
the card's actual type.

## Approach

Add a dedicated, type-based `hideLands` boolean to the shared filter model
(`makeFilterModel`, `static/app.js` line 188), enforced in `applyFilters`
(line 240) exactly like the existing type-substring checks elsewhere in the
codebase (`groupCardsByType` line 1435, `typeRank` line 200, the existing
`model.types` check at line 263) — i.e. `type_line.includes('Land')`. This
substring match also naturally catches MDFC/split lands (e.g. "Jwari
Disruption // Jwari Ruins" is stored as `type_line: "Instant // Land"`,
"Blightstep Pathway // Searstep Pathway" as `"Land // Land"`) since the
stored `type_line` already concatenates both faces with `" // "`.

### 1. Filter model + enforcement

In `makeFilterModel` (line 188-196), add `hideLands: false` to the returned
object (base default: lands shown — see per-page defaults below for how
each page overrides this at construction time).

In `applyFilters` (line 240-285), add, anywhere among the other early
`return false` checks (e.g. right after the existing `model.types` block at
line 261-264):

```js
if (model.hideLands && (c.type_line || '').includes('Land')) return false;
```

Do **not** add `hideLands` to `activeFilterCount` (line 288) or
`modelToParams` (line 301) — it's a standalone toggle outside the Filters
panel (see below), not one of the panel's own facets, and it's irrelevant to
`modelToParams` regardless since that function only serializes `state.filter`
for the Cards-browse page's server-side search (`loadCards`, line 700-708) —
this feature is intentionally not added to the Cards browse page at all (see
Out of scope).

### 2. Per-page defaults

- Collection page: `collectionState.filter` (`static/app.js` ~line 1348) stays
  `makeFilterModel()` with no override — lands **shown** by default (the base
  default is already `false`).
- Deck page: change both places `deckState.filter` is constructed to default
  it **hidden**:
  - Top-level state init (`deckState` object, ~line 1790):
    `filter: makeFilterModel({ hideLands: true }),`
  - `selectDeck`'s per-deck-load reset (~line 1880, currently
    `deckState.filter = makeFilterModel();`): change to
    `deckState.filter = makeFilterModel({ hideLands: true });` so every
    freshly loaded/switched deck defaults to lands hidden again.
- Cards browse page's `state.filter` is untouched (feature not present there;
  base default `false` is inert since no UI ever flips it).

### 3. "Clear" button preserves it

The Filters panel's "Clear" button handler (`static/app.js` ~line 496-502)
currently does:

```js
const keepText = model.text;
Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText }));
```

Add `hideLands: model.hideLands` to that overrides object, so clicking
Clear — which resets only the *panel's own* facets (colors, types, cmc,
power, toughness, tags) — leaves the standalone Hide Lands toggle exactly
as the user currently has it set, the same way it already preserves
`sort`/`dir`/`text`.

### 4. Toolbar toggle button

In `buildFilterControls` (`static/app.js` line 382-510), accept a new
optional `config.showHideLandsToggle` (boolean). When true, build and append
a standalone toggle button — reusing the pressed/active visual pattern
already used elsewhere (e.g. `.vtoggle-btn.active`, `.color-btn.active`) —
immediately before the existing `filterBtn` (so the toolbar order becomes:
sort select, direction button, **Hide Lands toggle**, Filters button, panel):

```js
if (config.showHideLandsToggle) {
  const landsBtn = document.createElement('button');
  landsBtn.className = 'hide-lands-btn action-btn' + (model.hideLands ? ' active' : '');
  landsBtn.textContent = 'Hide Lands';
  landsBtn.addEventListener('click', () => {
    model.hideLands = !model.hideLands;
    landsBtn.classList.toggle('active', model.hideLands);
    onChange();
  });
  container.appendChild(landsBtn);
}
```

(Insert this block, and the corresponding `container.appendChild(landsBtn)`
ordering, so the button lands before `container.appendChild(filterBtn)` at
the bottom of the function — adjust the existing sequence of `appendChild`
calls at lines 506-509 accordingly.)

Add a `.hide-lands-btn.active` CSS rule (`static/style.css`) matching the
existing active-state pattern used for `.vtoggle-btn.active`/`.color-btn.active`
(e.g. accent-colored border/background) so it's visually obvious when lands
are hidden.

Update the three `buildFilterControls` call sites:

- Cards browse (line 1327): no change — `showHideLandsToggle` omitted
  (falsy), so no button renders there.
- Collection (line 1515): add `showHideLandsToggle: true` to the config
  object.
- Deck (line 1893, inside `selectDeck`): add `showHideLandsToggle: true` to
  the config object.

### Out of scope

- Not added to the Cards browse page (`view-browser`) — scoped to Collection
  and Deck pages only, per the raw idea.
- No persistence — like every other filter field, `hideLands` resets to its
  page's default (Deck: hidden: Collection: shown) on page reload; within a
  single Deck-viewing session it does **not** reset when switching `groupBy`
  mode (nothing already resets `deckState.filter` on a groupBy change today,
  and this doesn't add that), only when switching to a different deck
  (`selectDeck`) or reloading the page.
- Does not touch item 004 (deck category visibility checkboxes) — that item
  no longer defaults any category hidden; this item is the sole mechanism
  for hiding lands, and it works whether or not item 004 has shipped yet.
- notes.md idea #3 ("default tag all lands as land, including mdfc lands")
  is separate, unimplemented scope — this item filters by `type_line`
  directly, not by tags, so it doesn't depend on or interact with that idea.

## Acceptance criteria

- [x] On the Deck page, a "Hide Lands" toggle button appears in the toolbar
      (next to the existing Filters button) and is active/pressed by
      default when a deck is freshly loaded or switched to.
- [x] With Hide Lands active on the Deck page, every card whose `type_line`
      contains "Land" is absent from both the grid and text views —
      including an MDFC land like "Jwari Disruption // Jwari Ruins" (stored
      type_line `"Instant // Land"`) — regardless of what deck/collection
      tags that card has or what `groupBy` mode is active.
- [x] Clicking the toggle off immediately shows lands again (still subject
      to any other active filters); clicking it back on hides them again.
- [x] On the Collection page, the same toggle button appears in its toolbar
      but starts inactive (lands shown) by default.
- [x] The toggle's current state is unaffected by clicking the Filters
      panel's "Clear" button on either page.
- [x] The toggle does not appear anywhere on the Cards browse page.
- [x] Reloading the page resets the Deck page's toggle back to active (hidden)
      and the Collection page's back to inactive (shown) — no persistence.
- [x] The existing allow-list "Types" filter inside the Filters panel
      (checking "Land" to show only lands) continues to work unchanged and
      independently of this new toggle.
