# Collection "Group: Type" Option Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Group: Type" option to the Collection page's group-by select, so the collection grid can be organized into Creature/Instant/Sorcery/Enchantment/Artifact/Planeswalker/Land/Other sections, alongside the existing "Group: None" / "Group: Tag" options.

**Architecture:** Reuse the existing `groupCardsByType` pure function (already used by the Deck page, already unit-tested) as-is. Add the `<option>` to the HTML select, extend `renderCollectionGrid`'s binary group-by branch into a 3-way dispatch, and widen the `collectionState.groupBy` state comment. No new functions, no changes to `groupCardsByType` itself.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), static HTML (`static/index.html`). Frontend unit tests are plain Node scripts under `tests/js/` that extract sentinel-comment-delimited pure functions out of `static/app.js` via string slicing + `new Function(...)` and run under plain `node` (see `tests/js/group-cards-by-type.test.mjs`, which already fully covers `groupCardsByType` — commander-bucket behavior, empty-group omission, missing/blank `type_line`). `renderCollectionGrid` is DOM-wiring (reads `collectionState`, mutates the live DOM), not a pure function, and has no sentinel-comment block — consistent with the rest of `static/app.js`'s render functions, it has no unit test coverage. Verification for this plan is: (a) `node --check static/app.js` for syntax, (b) the full existing `tests/js/*.test.mjs` + `pytest` suites staying green (regression check — nothing in this plan touches `groupCardsByType` itself, only its new caller), and (c) a live browser check via `mcp__claude-in-chrome__*` tools against the running `uvicorn` dev server, walking every acceptance criterion in the spec.

**Spec:** `docs/superpowers/backlog/007-collection-type-grouping.md`

## Global Constraints

- No changes to `groupCardsByType` itself (`static/app.js:1434-1465`, inside the `// ── groupCardsByType ──` / `// ── end groupCardsByType ──` sentinel block) — it already omits empty groups and never produces a "Commander" bucket for collection cards, since collection card objects never have `is_commander` set.
- No changes to the Deck page's own `Group: Card type` option or behavior.
- `collectionGroupCollapsed` stays a single `Set` shared across both grouped modes (pre-existing pattern, not to be fixed here — see spec's "Out of scope").

---

### Task 1: Add the "Group: Type" option and update state comment

**Files:**
- Modify: `static/index.html:41-44` (`#collection-group-by` select)
- Modify: `static/app.js:1359-1364` (`collectionState` declaration)

**Interfaces:**
- Consumes: none.
- Produces: a `<option value="type">Group: Type</option>` in the DOM, selectable via the existing `#collection-group-by` change-handler wiring (unchanged — it already reads `e.target.value` into `collectionState.groupBy` for any option value). Task 2 depends on `collectionState.groupBy` being settable to `'type'`.

- [ ] **Step 1: Add the option to the select**

In `static/index.html`, change:

```html
<select id="collection-group-by" class="group-by-select">
  <option value="none">Group: None</option>
  <option value="collection-tag">Group: Tag</option>
</select>
```

to:

```html
<select id="collection-group-by" class="group-by-select">
  <option value="none">Group: None</option>
  <option value="type">Group: Type</option>
  <option value="collection-tag">Group: Tag</option>
</select>
```

- [ ] **Step 2: Update the state comment**

In `static/app.js`, change:

```js
const collectionState = {
  cards: [],   // full card objects with .quantity
  query: '',
  groupBy: 'none',   // 'none' | 'collection-tag'
  filter: makeFilterModel(),
};
```

to:

```js
const collectionState = {
  cards: [],   // full card objects with .quantity
  query: '',
  groupBy: 'none',   // 'none' | 'type' | 'collection-tag'
  filter: makeFilterModel(),
};
```

- [ ] **Step 3: Syntax-check and run full suites**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: syntax check passes silently; every `.test.mjs` file prints its all-passing summary; pytest reports all tests passing. (Regression check only — this task adds a reachable but not-yet-handled select value; Task 2 makes it functional.)

- [ ] **Step 4: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat(collection): add Group: Type option to group-by select"
```

---

### Task 2: 3-way dispatch in `renderCollectionGrid`

**Files:**
- Modify: `static/app.js:1611-1618` (inside `renderCollectionGrid`, the group-by branch)

**Interfaces:**
- Consumes: `collectionState.groupBy` (now `'none' | 'type' | 'collection-tag'` from Task 1), `groupCardsByType(cards)` (existing, `static/app.js:1444`, returns `[{label, cards}, ...]`), `groupCards(cards, field)` (existing), `renderGroupedGrid(container, groups, buildTileFn, opts)` (existing, `static/app.js:1525`), `collectionGroupCollapsed` (existing `Set`).
- Produces: selecting "Group: Type" renders the collection grid grouped by `groupCardsByType`'s fixed-order buckets; selecting "Group: Tag" is unchanged; selecting "Group: None" is unchanged. Task 3 verifies this live.

- [ ] **Step 1: Change the binary branch to a 3-way dispatch**

In `static/app.js`, inside `renderCollectionGrid` (starting at line 1588), change:

```js
  if (collectionState.groupBy !== 'none') {
    const groups = groupCards(filtered, 'collection_tags');
    for (const g of groups) g.cards.sort(cmp);
    renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), { collapsedState: collectionGroupCollapsed });
  } else {
```

to:

```js
  if (collectionState.groupBy === 'type') {
    const groups = groupCardsByType(filtered);
    for (const g of groups) g.cards.sort(cmp);
    renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), { collapsedState: collectionGroupCollapsed });
  } else if (collectionState.groupBy === 'collection-tag') {
    const groups = groupCards(filtered, 'collection_tags');
    for (const g of groups) g.cards.sort(cmp);
    renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), { collapsedState: collectionGroupCollapsed });
  } else {
```

Leave the trailing `else { ... }` block (the ungrouped fragment-building code) and the closing brace after it exactly as they are — only the condition chain above them changes.

- [ ] **Step 2: Syntax-check and run full suites**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green — `renderCollectionGrid` has no existing `.test.mjs` coverage (DOM-wiring, consistent with the rest of `static/app.js`'s render functions), so this is a regression check. New-behavior verification happens live in Task 3.

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat(collection): dispatch Group: Type to groupCardsByType in renderCollectionGrid"
```

---

### Task 3: Live browser verification against every acceptance criterion

**Files:** none (verification only; may produce fix commits if a criterion fails)

**Interfaces:**
- Consumes: Task 1 and Task 2's changes.
- Produces: confirmation that every acceptance criterion in `docs/superpowers/backlog/007-collection-type-grouping.md` holds against the running app.

- [ ] **Step 1: Start the dev server if not already running**

`uvicorn app:app --reload` (background it or use a separate terminal).

- [ ] **Step 2: Walk every acceptance criterion using `mcp__claude-in-chrome__*` tools**

Navigate to the local app's Collection page and confirm:

1. The group-by select shows options in this order: "Group: None", "Group: Type", "Group: Tag".
2. Selecting "Group: Type" groups the grid into sections from `Creature, Instant, Sorcery, Enchantment, Artifact, Planeswalker, Land, Other` — only non-empty ones shown, in that fixed order — and no "Commander" section ever appears (collection cards have no `is_commander` field).
3. Within a type section, cards are sorted per the current sort control (e.g. switch sort to a different field/direction and confirm the section's card order updates accordingly, same as tag mode).
4. Clicking a type section's header collapses/expands it, same as a tag section's header does today.
5. Switch "Group: Type" → "Group: Tag" → "Group: None" → back to "Group: Type": each switch re-renders correctly with no leftover sections from the previous mode (no stale DOM nodes from another grouping).
6. Navigate to the Deck page and confirm its own "Group: Card type" option and behavior are unaffected (still groups deck cards, still gives the commander its own leading section there).

If any step fails, fix the underlying code (not the test) and re-run Task 1 Step 3 / Task 2 Step 2 before re-verifying.

- [ ] **Step 3: Run the full suites one final time**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green.

- [ ] **Step 4: Update the backlog item's acceptance criteria checkboxes**

Edit `docs/superpowers/backlog/007-collection-type-grouping.md`, checking off every `- [ ]` under "## Acceptance criteria" that was just verified live in Step 2 (all seven should now be satisfied).

```bash
git add docs/superpowers/backlog/007-collection-type-grouping.md
git commit -m "docs(backlog): check off item 007 acceptance criteria"
```
