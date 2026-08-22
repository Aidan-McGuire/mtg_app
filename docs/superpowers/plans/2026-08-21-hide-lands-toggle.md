# Hide Lands Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone "Hide Lands" toolbar toggle to the Collection and Deck pages that excludes any card whose `type_line` contains "Land" from both grid and text views, independent of the existing allow-list Types filter and independent of tags.

**Architecture:** A new `hideLands` boolean field on the shared filter model (`makeFilterModel`), enforced as one more early-exit check in the shared `applyFilters` pure function, exposed via a new optional `config.showHideLandsToggle` flag on the shared `buildFilterControls(container, config)` toolbar builder. Per-page defaults are set at the two `filter: makeFilterModel(...)` construction sites (Collection: default `false`; Deck: default `true`, both at initial state creation and at `selectDeck`'s per-deck reset). The Cards browse page is untouched entirely (feature not present there).

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), plain CSS (`static/style.css`), static HTML (`static/index.html`). Frontend unit tests are plain Node scripts under `tests/js/` that extract a sentinel-comment-delimited pure function out of `static/app.js` via string slicing + `new Function(...)` and run under plain `node`, no framework (see `tests/js/apply-filters.test.mjs`). There is no DOM/jsdom harness, so DOM-wiring changes (the toggle button itself, the per-page call sites) are verified by (a) `node --check static/app.js` for syntax, (b) the full existing `tests/js/*.test.mjs` + `pytest` suites staying green, and (c) a live browser check via `mcp__claude-in-chrome__*` tools against the running `uvicorn` dev server, walking every acceptance criterion in the spec — this session has browser automation available, so use it rather than settling for code review alone.

**Spec:** `docs/superpowers/backlog/005-hide-lands-toggle.md`

## Global Constraints

- Substring match only: `(c.type_line || '').includes('Land')` — no tag involvement, no special-casing of MDFC/split cards (the stored `type_line` already concatenates both faces with `" // "`, so the substring check catches them naturally).
- `hideLands` must NOT be added to `activeFilterCount` or `modelToParams` — it is a standalone toolbar toggle, not a Filters-panel facet, and is irrelevant to the Cards-browse page's server-side query serialization.
- Feature is scoped to Collection and Deck pages only. The Cards browse page (`view-browser`) gets no toggle and no behavior change.
- No persistence: `hideLands` resets to each page's default on reload, exactly like every other filter field.
- Collection page default: lands shown (`hideLands: false`). Deck page default: lands hidden (`hideLands: true`), reapplied both at first load and every `selectDeck` switch.
- The Filters panel's "Clear" button must preserve the toggle's current `hideLands` value (same pattern already used to preserve `sort`/`dir`/`text`).

---

### Task 1: Filter model field + `applyFilters` enforcement

**Files:**
- Modify: `static/app.js:188-196` (`makeFilterModel`)
- Modify: `static/app.js:240-285` (`applyFilters`, inside the `// ── applyFilters ──` / `// ── end applyFilters ──` sentinel block)
- Test: `tests/js/apply-filters.test.mjs` (existing file, extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: `model.hideLands` (boolean, default `false` from `makeFilterModel()`), enforced inside `applyFilters(cards, model)`. Task 2, 3, and 4 all depend on this field existing and being enforced.

- [ ] **Step 1: Write the failing test**

Open `tests/js/apply-filters.test.mjs`. Add `hideLands: false` to the `baseModel()` overrides object (it must match the real `makeFilterModel()` shape so the extracted `applyFilters` doesn't choke on a missing property), add an MDFC land fixture card, and add two new cases to the `cases` array:

```js
function baseModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false, types: new Set(),
    cmcMin: null, cmcMax: null, powerMin: null, powerMax: null,
    toughnessMin: null, toughnessMax: null, exactColors: new Set(),
    exactColorlessOnly: false, tags: new Set(), hideLands: false,
    ...overrides,
  };
}
```

Add to the `cards` fixture array (after `Deathrite Shaman`):

```js
  { name: 'Forest', power: null, toughness: null, cmc: 0, type_line: 'Basic Land — Forest', color_identity: '', colors: '' },
  { name: 'Jwari Disruption // Jwari Ruins', power: null, toughness: null, cmc: 2, type_line: 'Instant // Land', color_identity: 'U', colors: 'U' },
```

Add to the `cases` array:

```js
  ['hideLands excludes plain lands and MDFC lands, keeps everything else',
    baseModel({ hideLands: true }),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman']],
  ['hideLands false (default) shows lands too',
    baseModel({ hideLands: false }),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman', 'Forest', 'Jwari Disruption // Jwari Ruins']],
```

Also update two pre-existing cases whose expected lists are affected by the two new fixture cards:

- `'no power/toughness/color filter passes everything through'` (uses `baseModel()`, no filter active): append `'Forest', 'Jwari Disruption // Jwari Ruins'` to its expected array.
- `'exact colorless matches only the colorless card'` (`exactColorlessOnly: true`): `Forest` has `colors: ''` just like `Steel Wall`, so it now matches too — change the expected array from `['Steel Wall']` to `['Steel Wall', 'Forest']`.

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/js/apply-filters.test.mjs`
Expected: FAIL — the `hideLands` cases report unexpected results (lands not excluded yet) since `applyFilters` doesn't check `model.hideLands` yet; the "shows lands too" and "no filter" cases may also fail since the fixture cards were just added.

- [ ] **Step 3: Implement `applyFilters` enforcement and the model field**

In `static/app.js`, inside `makeFilterModel` (~line 188-196), add `hideLands: false` to the returned object:

```js
function makeFilterModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false,
    types: new Set(), cmcMin: null, cmcMax: null,
    powerMin: null, powerMax: null, toughnessMin: null, toughnessMax: null,
    exactColors: new Set(), exactColorlessOnly: false,
    tags: new Set(), hideLands: false, sort: 'name', dir: 'asc', ...overrides,
  };
}
```

Inside `applyFilters` (~line 240-285), add this check right after the existing `model.types` block (after line 264's closing `}`):

```js
    if (model.hideLands && (c.type_line || '').includes('Land')) return false;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/js/apply-filters.test.mjs`
Expected: `all N passing`, exit code 0.

- [ ] **Step 5: Run the full JS + Python suites to check for regressions**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: syntax check passes silently; every `.test.mjs` file prints its all-passing summary; pytest reports all tests passing.

- [ ] **Step 6: Commit**

```bash
git add static/app.js tests/js/apply-filters.test.mjs
git commit -m "feat(filters): add hideLands field to filter model and applyFilters"
```

---

### Task 2: Per-page defaults (Collection shown, Deck hidden)

**Files:**
- Modify: `static/app.js` — `deckState` object initial declaration (`filter: makeFilterModel(),` inside the object created at the `// ── Deck state ──` section)
- Modify: `static/app.js` — `selectDeck`'s per-deck reset (`deckState.filter = makeFilterModel();   // reset filters between decks`)
- Collection page (`collectionState.filter = makeFilterModel();`) is already correct as-is (base default `false` — no change needed there; do not touch it, just confirm it during review).

**Interfaces:**
- Consumes: `makeFilterModel(overrides)` and its new `hideLands` field from Task 1.
- Produces: `deckState.filter.hideLands === true` immediately after both the initial `deckState` declaration and every `selectDeck(id)` call; `collectionState.filter.hideLands === false` at all times (never overridden).

- [ ] **Step 1: Change the Deck page's two filter-construction sites**

In `static/app.js`, find the `deckState` object (`const deckState = { ... filter: makeFilterModel(), ... }`) and change that one line to:

```js
  filter:         makeFilterModel({ hideLands: true }),
```

Then find `selectDeck(id)`'s reset line:

```js
  deckState.filter = makeFilterModel();   // reset filters between decks
```

and change it to:

```js
  deckState.filter = makeFilterModel({ hideLands: true });   // reset filters between decks (lands hidden by default)
```

Leave `collectionState.filter = makeFilterModel();` untouched — its base default of `hideLands: false` is already correct.

- [ ] **Step 2: Syntax-check and run full suites**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green (this task doesn't change any function under unit test, just two object-literal call sites, so no test file needs new cases — this is confirmed by a fresh pair of eyes re-reading both edited lines against the spec's Section 2 before moving on).

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat(deck): default Hide Lands to active for freshly loaded/switched decks"
```

---

### Task 3: Toolbar toggle button in `buildFilterControls` + CSS

**Files:**
- Modify: `static/app.js:382-510` (`buildFilterControls`)
- Modify: `static/style.css` (add `.hide-lands-btn.active` rule near the existing `.action-btn`/`.deck-cmd-btn.active` rules, e.g. after line 426)

**Interfaces:**
- Consumes: `config.showHideLandsToggle` (new optional boolean on the `config` object passed to `buildFilterControls`), `model.hideLands` from Task 1, `config.onChange` (already existing).
- Produces: a `button.hide-lands-btn.action-btn` element (with `.active` class when `model.hideLands` is true) appended to `container` immediately before the existing `filterBtn`, present only when `config.showHideLandsToggle` is truthy. Clicking it flips `model.hideLands`, toggles its own `.active` class, and calls `onChange()`. Task 4's three call sites rely on this new config flag and on this button existing in the DOM before the Filters button.

- [ ] **Step 1: Add the toggle button to `buildFilterControls`**

In `static/app.js`, inside `buildFilterControls(container, config)` (~line 382), destructure the new flag at the top:

```js
function buildFilterControls(container, config) {
  const { model, facets, sortOptions, tagOptions = [], onChange, showHideLandsToggle = false } = config;
```

Immediately before the existing `// Filters disclosure` block (the `filterBtn` creation, ~line 408-409), insert:

```js
  // Hide Lands toggle
  let landsBtn = null;
  if (showHideLandsToggle) {
    landsBtn = document.createElement('button');
    landsBtn.className = 'hide-lands-btn action-btn' + (model.hideLands ? ' active' : '');
    landsBtn.textContent = 'Hide Lands';
    landsBtn.addEventListener('click', () => {
      model.hideLands = !model.hideLands;
      landsBtn.classList.toggle('active', model.hideLands);
      onChange();
    });
  }
```

At the bottom of the function, change the existing append sequence:

```js
  refreshBadge();
  container.appendChild(sortSel);
  container.appendChild(dirBtn);
  container.appendChild(filterBtn);
  container.appendChild(panel);
```

to insert `landsBtn` (when present) right before `filterBtn`:

```js
  refreshBadge();
  container.appendChild(sortSel);
  container.appendChild(dirBtn);
  if (landsBtn) container.appendChild(landsBtn);
  container.appendChild(filterBtn);
  container.appendChild(panel);
```

- [ ] **Step 2: Add the CSS active-state rule**

In `static/style.css`, immediately after the `.action-btn-danger:hover` rule (~line 426), add:

```css
.hide-lands-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
```

(This matches the existing `.deck-cmd-btn.active` pattern exactly — same accent border/color/background — so the toggle reads visually consistent with other pressed toolbar buttons.)

- [ ] **Step 3: Syntax-check and run full suites**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green — `buildFilterControls` has no existing `.test.mjs` coverage (it's DOM-wiring, consistent with the rest of `static/app.js`'s render functions), so this step is a regression check, not new-behavior verification. New-behavior verification happens via the browser check in Task 4.

- [ ] **Step 4: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat(filters): add optional Hide Lands toolbar toggle button to buildFilterControls"
```

---

### Task 4: Wire up Clear-button preservation + the three call sites, then verify all acceptance criteria live

**Files:**
- Modify: `static/app.js` — Clear button handler inside `buildFilterControls` (~line 496-502)
- Modify: `static/app.js` — Collection's `buildFilterControls` call (inside `loadCollectionView`, ~line 1524)
- Modify: `static/app.js` — Deck's `buildFilterControls` call (inside `selectDeck`, ~line 1903)
- Cards browse's `buildFilterControls` call (inside `init()`, ~line 1327) — **no change**, confirm `showHideLandsToggle` stays omitted.

**Interfaces:**
- Consumes: `config.showHideLandsToggle` and the `landsBtn`/`.hide-lands-btn` button from Task 3; `model.hideLands` from Task 1; the Task 2 per-page defaults.
- Produces: fully wired feature — this is the task whose deliverable is checked against every acceptance criterion in the spec.

- [ ] **Step 1: Make Clear preserve `hideLands`**

In `static/app.js`, find the Clear button's click handler (~line 496-502):

```js
  clearBtn.addEventListener('click', () => {
    // Text search is owned by the page's search box, so Clear preserves it.
    const keepText = model.text;
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText }));
    buildFilterControls(container, config);  // re-render to reset control state
    onChange();
  });
```

Change the `Object.assign` line to also preserve `hideLands`:

```js
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText, hideLands: model.hideLands }));
```

- [ ] **Step 2: Add `showHideLandsToggle: true` to the Collection call site**

In `static/app.js`, inside `loadCollectionView` (~line 1524):

```js
    buildFilterControls(document.getElementById('collection-filter-controls'), {
      model: collectionState.filter,
      facets: new Set(['colors', 'exactColors', 'types', 'cmc', 'power', 'toughness', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions,
      onChange: renderCollectionGrid,
      showHideLandsToggle: true,
    });
```

- [ ] **Step 3: Add `showHideLandsToggle: true` to the Deck call site**

In `static/app.js`, inside `selectDeck` (~line 1903):

```js
    buildFilterControls(document.getElementById('deck-filter-controls'), {
      model: deckState.filter,
      facets: new Set(['colors', 'exactColors', 'types', 'cmc', 'power', 'toughness', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions: [...new Set([...collTags, ...deckTags])].sort(),
      onChange: renderDeckContent,
      showHideLandsToggle: true,
    });
```

- [ ] **Step 4: Confirm the Cards browse call site is untouched**

Re-read `init()` (~line 1327) and confirm `showHideLandsToggle` is absent from that config object — no edit needed, this step is a verification-only checkpoint.

- [ ] **Step 5: Syntax-check and run full suites**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green.

- [ ] **Step 6: Commit the wiring**

```bash
git add static/app.js
git commit -m "feat(filters): wire Hide Lands toggle into Collection and Deck toolbars, preserve it on Clear"
```

- [ ] **Step 7: Live browser verification against every acceptance criterion**

Start the dev server if not already running: `uvicorn app:app --reload` (background it or use a separate terminal). Using the `mcp__claude-in-chrome__*` tools, navigate to the local app and walk through:

1. Open the Deck page, select any deck with at least one land in it (add one via the deck search if needed, including an MDFC/land-adjacent card if the collection has one). Confirm the "Hide Lands" button renders in the toolbar next to Filters, and is shown pressed/active by default.
2. Confirm every card whose type line contains "Land" is absent from both grid view and text view while the toggle is active, regardless of `groupBy` mode (cycle through the groupBy options).
3. Click the toggle off — confirm lands reappear immediately in both views. Click it back on — confirm they hide again.
4. Switch to the Collection page. Confirm the same toggle button appears in its toolbar but starts **inactive** (lands shown).
5. On either page, open the Filters panel, change an unrelated facet (e.g. check a color), then click Clear. Confirm the Hide Lands toggle's pressed state is unaffected by Clear.
6. Navigate to the Cards browse page/tab. Confirm no Hide Lands button appears anywhere in its toolbar.
7. Reload the page. Confirm the Deck page's toggle is active (hidden) again and the Collection page's toggle is inactive (shown) again — no persistence across reload.
8. In the Filters panel's existing "Types" checklist, check "Land" (the pre-existing allow-list filter) and confirm it still narrows to lands-only, independently of the new toggle's own state.

If any step fails, fix the underlying code (not the test) and re-run the full step sequence from Step 5 before re-verifying.

- [ ] **Step 8: Update the backlog item's acceptance criteria checkboxes**

Edit `docs/superpowers/backlog/005-hide-lands-toggle.md`, checking off every `- [ ]` under "## Acceptance criteria" that was just verified live in Step 7 (all eight should now be satisfied). Do not change `status` in this task — that's a Stage 2 "Finish" step, not part of this plan.

```bash
git add docs/superpowers/backlog/005-hide-lands-toggle.md
git commit -m "docs(backlog): check off item 005 acceptance criteria"
```
