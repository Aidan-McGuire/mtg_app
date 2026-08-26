# Deck Filter for Cards Not Owned Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Unowned only" toggle button to the deck view's filter bar that, when active, shows only deck cards with collection quantity 0 — a shopping-list view. Deck view only; card browser and collection browser filter bars are unchanged.

**Architecture:** Pure frontend change to `static/app.js`, following the exact existing pattern of the `hideLands` boolean toggle: a new field on the filter model (`unownedOnly`), a new early-return check in `applyFilters`, and a new toggle button in `buildFilterControls`, gated behind a new `showUnownedOnlyToggle` config flag that only the deck-view call site sets to `true` (the card-browser and collection-browser call sites do not pass it, so they get no button — mirrors how `showHideLandsToggle` gates the existing lands button, except that flag happens to be `true` at two of the three call sites already; the new flag is deliberately `true` at only one).

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), plain CSS (`static/style.css`, unchanged — reusing the existing `.action-btn`/`.active` rules already used by `.hide-lands-btn`). Frontend unit tests are plain Node scripts under `tests/js/` that extract sentinel-comment-delimited pure functions out of `static/app.js` via string slicing + `new Function(...)` (see `tests/js/apply-filters.test.mjs`). `applyFilters` is one such sentinel-delimited pure function and is directly extended and tested; `qty()` (app.js:535-537) is a second, currently un-sentineled pure-ish helper (it closes over module-level `state.collection`) that `applyFilters` will now call — it needs its own sentinel pair so the test harness can extract and stub it. `buildFilterControls` is DOM-wiring (reads/writes `document`), consistent with the rest of the codebase's render functions it gets no unit test — verification for it is a careful trace against the acceptance criteria plus `node --check`.

**Spec:** `docs/superpowers/backlog/014-deck-filter-unowned.md`

## Global Constraints

- New toggle must follow the exact same pattern as `hideLands` (model field, `applyFilters` check, button in `buildFilterControls`, preserved across filter-bar "Clear").
- "Not owned" = collection quantity exactly 0 (via the existing `qty(cardId)` helper), not "fewer than the deck needs."
- Deck view only: the button must render on `deck-filter-controls` and must NOT render on `browser-filter-controls` or `collection-filter-controls`.
- Reuse the existing `action-btn` visual style (button gets classes `unowned-only-btn action-btn` + conditional `active`, matching `hide-lands-btn action-btn`) — no new CSS.
- `pytest` suite (128 tests) must stay green — this item touches only frontend files, so it's a pure regression check.

---

## Current code (reference — read before editing)

`makeFilterModel` (app.js:188-196):
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

`applyFilters` (app.js:240-287, between sentinel comments `// ── applyFilters ──` and `// ── end applyFilters ──`), relevant line:
```js
    if (model.hideLands && (c.type_line || '').includes('Land')) return false;
```

`qty` (app.js:535-537, no sentinels yet):
```js
function qty(cardId) {
  return state.collection[cardId] || 0;
}
```
`state` is declared at app.js:160 as `const state = { ... collection: {}, ... }` — module-level, populated by `loadCollection()`/`loadCollectionView()` from `GET /api/collection`.

`buildFilterControls` (app.js:383-525), relevant slices:
```js
function buildFilterControls(container, config) {
  const { model, facets, sortOptions, tagOptions = [], onChange, showHideLandsToggle = false } = config;
  ...
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
  ...
  // Clear
  const clearBtn = document.createElement('button');
  clearBtn.className = 'clear-filters-btn action-btn';
  clearBtn.textContent = 'Clear';
  clearBtn.addEventListener('click', () => {
    const keepText = model.text;
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText, hideLands: model.hideLands }));
    buildFilterControls(container, config);  // re-render to reset control state
    onChange();
  });
  panel.appendChild(clearBtn);

  refreshBadge();
  container.appendChild(sortSel);
  container.appendChild(dirBtn);
  if (landsBtn) container.appendChild(landsBtn);
  container.appendChild(filterBtn);
  container.appendChild(panel);
}
```

Three call sites:
- `browser-filter-controls` (app.js:1363) — no `showHideLandsToggle` passed (browser has no lands toggle either). Do not touch.
- `collection-filter-controls` (app.js:1560-1567) — passes `showHideLandsToggle: true`. Do not add the new flag here.
- `deck-filter-controls` (app.js:1944-1951) — passes `showHideLandsToggle: true`. Add `showUnownedOnlyToggle: true` here only.

`tests/js/apply-filters.test.mjs` extracts only the `// ── applyFilters ──` … `// ── end applyFilters ──` slice via `new Function`, and defines its own local `baseModel()` helper (does not import `makeFilterModel`) and its own `cards` fixture array (no `id` field currently, since no existing filter needs one).

---

## Task 1: Add sentinel comments around `qty` so it's independently testable

**Files:**
- Modify: `static/app.js:535-537`

**Interfaces:**
- Produces: sentinel-delimited `qty(cardId)` source block, extractable the same way `applyFilters` already is.

- [ ] **Step 1: Add sentinel comments around the existing `qty` function**

In `static/app.js`, change:
```js
function qty(cardId) {
  return state.collection[cardId] || 0;
}
```
to:
```js
// ── qty ──
function qty(cardId) {
  return state.collection[cardId] || 0;
}
// ── end qty ──
```

- [ ] **Step 2: Verify the file still parses**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Run existing JS + Python tests to confirm no regression**

Run: `node tests/js/apply-filters.test.mjs && node tests/js/filter-decks.test.mjs && python3 -m pytest -q`
Expected: `all 10 passing`, `all 6 passing`, `128 passed`.

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "refactor: add sentinel comments around qty for test extraction"
```

---

## Task 2: Add `unownedOnly` to the filter model and `applyFilters`, with a failing-then-passing test

**Files:**
- Modify: `static/app.js` (`makeFilterModel` at line 194, `applyFilters` inside the sentinel block at line 265)
- Test: `tests/js/apply-filters.test.mjs`

**Interfaces:**
- Consumes: `qty(cardId)` from Task 1 (now sentinel-delimited).
- Produces: `model.unownedOnly` (boolean, default `false`) consumed by Task 3's button and Task 4's clear-filters preservation.

- [ ] **Step 1: Update the test harness to extract and stub `qty`, and add `id` fields to the card fixtures**

In `tests/js/apply-filters.test.mjs`, replace the single-block extraction with a two-block extraction (`qty` + `applyFilters`) evaluated together against a local stub `state`, and add `id` to every fixture card plus a way to set owned quantity per test case. Replace the top of the file (from the `const applyFilters = ...` line) with:

```js
const QTY_START = '// ── qty ──';
const QTY_END = '// ── end qty ──';
const qtyFrom = src.indexOf(QTY_START);
const qtyTo = src.indexOf(QTY_END);
assert.ok(qtyFrom !== -1 && qtyTo > qtyFrom, 'qty sentinel comments not found in static/app.js');

const { applyFilters, setOwned } = new Function(`
  const state = { collection: {} };
  ${src.slice(qtyFrom, qtyTo)}
  ${src.slice(from, to)}
  return { applyFilters, setOwned: (id, n) => { state.collection[id] = n; } };
`)();

function baseModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false, types: new Set(),
    cmcMin: null, cmcMax: null, powerMin: null, powerMax: null,
    toughnessMin: null, toughnessMax: null, exactColors: new Set(),
    exactColorlessOnly: false, tags: new Set(), hideLands: false,
    unownedOnly: false,
    ...overrides,
  };
}

const cards = [
  { id: 1, name: 'Grizzly Bears', power: '2', toughness: '2', cmc: 2, type_line: 'Creature — Bear', color_identity: 'G', colors: 'G' },
  { id: 2, name: 'Wise Elephant', power: '3', toughness: '5', cmc: 5, type_line: 'Creature — Elephant', color_identity: 'G', colors: 'G' },
  { id: 3, name: 'Steel Wall', power: '0', toughness: '4', cmc: 1, type_line: 'Artifact Creature — Wall', color_identity: '', colors: '' },
  { id: 4, name: 'Mystery Hydra', power: '*', toughness: '*', cmc: 1, type_line: 'Creature — Hydra', color_identity: 'G', colors: 'G' },
  { id: 5, name: 'Ancestral Vision', power: null, toughness: null, cmc: 1, type_line: 'Sorcery', color_identity: 'U', colors: 'U' },
  { id: 6, name: 'Compound Beast', power: '1+*', toughness: '1+*', cmc: 3, type_line: 'Creature — Beast', color_identity: 'G', colors: 'G' },
  { id: 7, name: 'Deathrite Shaman', power: '1', toughness: '2', cmc: 1, type_line: 'Creature — Elf Shaman', color_identity: 'BG', colors: 'BG' },
  { id: 8, name: 'Forest', power: null, toughness: null, cmc: 0, type_line: 'Basic Land — Forest', color_identity: '', colors: '' },
  { id: 9, name: 'Jwari Disruption // Jwari Ruins', power: null, toughness: null, cmc: 2, type_line: 'Instant // Land', color_identity: 'U', colors: 'U' },
];

// Ownership fixture: cards 1, 3, 8 are owned (qty > 0); everything else is unowned (qty 0).
setOwned(1, 4);
setOwned(3, 1);
setOwned(8, 12);
```

Leave the rest of the file (the `names`, `cases`, and run-loop) as-is for now — this step only changes the harness setup, and the existing `cases` array must still pass unchanged since `id` fields and `unownedOnly: false` don't alter any existing expectation.

- [ ] **Step 2: Run the test to confirm the harness refactor alone doesn't break anything**

Run: `node tests/js/apply-filters.test.mjs`
Expected: `all 10 passing` (same 10 cases as before — no new cases yet).

- [ ] **Step 3: Add the new failing test cases for `unownedOnly`**

Append to the `cases` array in `tests/js/apply-filters.test.mjs` (before the closing `];`):
```js
  ['unownedOnly excludes owned cards (qty > 0), keeps unowned (qty 0)',
    baseModel({ unownedOnly: true }),
    ['Wise Elephant', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman', 'Jwari Disruption // Jwari Ruins']],
  ['unownedOnly false (default) shows owned and unowned',
    baseModel({ unownedOnly: false }),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman', 'Forest', 'Jwari Disruption // Jwari Ruins']],
  ['unownedOnly combines with hideLands (AND semantics): excludes owned AND excludes lands',
    baseModel({ unownedOnly: true, hideLands: true }),
    ['Wise Elephant', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman']],
```

- [ ] **Step 4: Run the test to verify the new cases fail**

Run: `node tests/js/apply-filters.test.mjs`
Expected: the 3 new cases show `FAIL` (since `applyFilters` doesn't check `unownedOnly` yet — it's currently ignored, so unowned filtering has no effect and all cards pass through), other 10 still `ok`.

- [ ] **Step 5: Add `unownedOnly` to `makeFilterModel` in `static/app.js`**

Change (app.js:188-196):
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
to:
```js
function makeFilterModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false,
    types: new Set(), cmcMin: null, cmcMax: null,
    powerMin: null, powerMax: null, toughnessMin: null, toughnessMax: null,
    exactColors: new Set(), exactColorlessOnly: false,
    tags: new Set(), hideLands: false, unownedOnly: false, sort: 'name', dir: 'asc', ...overrides,
  };
}
```

- [ ] **Step 6: Add the `unownedOnly` check to `applyFilters` in `static/app.js`**

Change (app.js:265, inside the `// ── applyFilters ──` sentinel block):
```js
    if (model.hideLands && (c.type_line || '').includes('Land')) return false;
```
to:
```js
    if (model.hideLands && (c.type_line || '').includes('Land')) return false;
    if (model.unownedOnly && qty(c.id) > 0) return false;
```

- [ ] **Step 7: Run the test to verify all cases now pass**

Run: `node tests/js/apply-filters.test.mjs`
Expected: `all 13 passing`.

- [ ] **Step 8: Run the full test suite for regressions**

Run: `node tests/js/apply-filters.test.mjs && node tests/js/filter-decks.test.mjs && python3 -m pytest -q`
Expected: `all 13 passing`, `all 6 passing`, `128 passed`.

- [ ] **Step 9: Commit**

```bash
git add static/app.js tests/js/apply-filters.test.mjs
git commit -m "feat: add unownedOnly boolean filter to filter model and applyFilters"
```

---

## Task 3: Add the "Unowned only" toggle button to `buildFilterControls`, gated to deck view only

**Files:**
- Modify: `static/app.js` (`buildFilterControls` at lines 383-525, and the `deck-filter-controls` call site at lines 1944-1951)

**Interfaces:**
- Consumes: `model.unownedOnly` from Task 2.
- Produces: a `showUnownedOnlyToggle` config flag on `buildFilterControls(container, config)` (default `false`, mirroring `showHideLandsToggle`); when `true`, renders a button with classes `unowned-only-btn action-btn` (+ `active` when `model.unownedOnly` is true) that toggles `model.unownedOnly` on click and calls `onChange()`.

- [ ] **Step 1: Destructure the new config flag**

Change (app.js:384):
```js
  const { model, facets, sortOptions, tagOptions = [], onChange, showHideLandsToggle = false } = config;
```
to:
```js
  const { model, facets, sortOptions, tagOptions = [], onChange, showHideLandsToggle = false, showUnownedOnlyToggle = false } = config;
```

- [ ] **Step 2: Add the button, right after the existing Hide Lands toggle block**

Change (app.js:409-420):
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
to:
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

  // Unowned Only toggle
  let unownedBtn = null;
  if (showUnownedOnlyToggle) {
    unownedBtn = document.createElement('button');
    unownedBtn.className = 'unowned-only-btn action-btn' + (model.unownedOnly ? ' active' : '');
    unownedBtn.textContent = 'Unowned Only';
    unownedBtn.addEventListener('click', () => {
      model.unownedOnly = !model.unownedOnly;
      unownedBtn.classList.toggle('active', model.unownedOnly);
      onChange();
    });
  }
```

- [ ] **Step 3: Append the button to the container, next to `landsBtn`**

Change (app.js:519-524):
```js
  refreshBadge();
  container.appendChild(sortSel);
  container.appendChild(dirBtn);
  if (landsBtn) container.appendChild(landsBtn);
  container.appendChild(filterBtn);
  container.appendChild(panel);
}
```
to:
```js
  refreshBadge();
  container.appendChild(sortSel);
  container.appendChild(dirBtn);
  if (landsBtn) container.appendChild(landsBtn);
  if (unownedBtn) container.appendChild(unownedBtn);
  container.appendChild(filterBtn);
  container.appendChild(panel);
}
```

- [ ] **Step 4: Wire the flag at the deck-view call site only**

Change (app.js:1944-1951):
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
to:
```js
    buildFilterControls(document.getElementById('deck-filter-controls'), {
      model: deckState.filter,
      facets: new Set(['colors', 'exactColors', 'types', 'cmc', 'power', 'toughness', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions: [...new Set([...collTags, ...deckTags])].sort(),
      onChange: renderDeckContent,
      showHideLandsToggle: true,
      showUnownedOnlyToggle: true,
    });
```

Do NOT modify the `browser-filter-controls` call site (app.js:1363) or the `collection-filter-controls` call site (app.js:1560-1567) — leave both exactly as they are, so neither gets the new button.

- [ ] **Step 5: Verify the file still parses**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 6: Manual trace verification (no DOM harness available)**

Re-read the diff for this task and confirm by inspection:
- `showUnownedOnlyToggle` defaults to `false`, so `buildFilterControls` calls that don't pass it (browser and collection call sites) get `unownedBtn === null` and nothing is appended.
- The deck call site is the only one passing `showUnownedOnlyToggle: true`.
- Button class/active-toggle mirrors `landsBtn` exactly.

- [ ] **Step 7: Run the full test suite for regressions**

Run: `node tests/js/apply-filters.test.mjs && node tests/js/filter-decks.test.mjs && python3 -m pytest -q`
Expected: `all 13 passing`, `all 6 passing`, `128 passed`.

- [ ] **Step 8: Commit**

```bash
git add static/app.js
git commit -m "feat: add Unowned Only toggle button to deck filter bar"
```

---

## Task 4: Preserve `unownedOnly` across the filter-bar "Clear" action

**Files:**
- Modify: `static/app.js:513`

**Interfaces:**
- Consumes: `model.unownedOnly` (Task 2), `showUnownedOnlyToggle`-gated button (Task 3).
- Produces: `unownedOnly` survives a "Clear" click the same way `hideLands` does.

- [ ] **Step 1: Add `unownedOnly` to the preserved-fields list in the Clear handler**

Change (app.js:513):
```js
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText, hideLands: model.hideLands }));
```
to:
```js
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText, hideLands: model.hideLands, unownedOnly: model.unownedOnly }));
```

- [ ] **Step 2: Verify the file still parses**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Manual trace verification against acceptance criteria**

Re-read `docs/superpowers/backlog/014-deck-filter-unowned.md`'s acceptance criteria list and confirm each is satisfied by the current diff:
- Toggle button exists on deck filter bar, shows qty-0 cards only when active — Task 3 + Task 2.
- Toggling off restores full list — Task 3's click handler flips the boolean and calls `onChange()`, which re-runs `applyFilters`.
- Combines with other filters via AND — Task 2 Step 3's third test case (`unownedOnly` + `hideLands` together) covers this; every check in `applyFilters` is an independent early-return `if`, so all active filters always AND together by construction.
- Persists across Clear — this task.
- No new button on card browser / collection browser — Task 3 Step 4 (flag not passed at those two call sites).

- [ ] **Step 4: Run the full test suite one final time**

Run: `node tests/js/apply-filters.test.mjs && node tests/js/filter-decks.test.mjs && python3 -m pytest -q`
Expected: `all 13 passing`, `all 6 passing`, `128 passed`.

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "fix: preserve unownedOnly across deck filter-bar clear action"
```
