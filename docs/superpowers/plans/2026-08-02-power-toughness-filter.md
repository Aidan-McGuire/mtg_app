# Power / Toughness Range Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add power and toughness min/max range filters, matching the existing CMC range filter, to the Cards browser, Collection view, and Deck editor.

**Architecture:** Extend the existing filter pipeline in parallel with how `cmc_min`/`cmc_max` already works: a numeric-safe SQL fragment builder in `app.py` for the server-backed Cards browser, and a matching client-side check in `static/app.js`'s `applyFilters` for the in-memory Collection/Deck views, both driven by the same shared filter model and `buildFilterControls` UI.

**Tech Stack:** FastAPI + sqlite3 (backend), vanilla JS + DOM (frontend), pytest (backend tests), Node's built-in `assert` module via sentinel-comment extraction (frontend tests).

## Global Constraints

- Non-numeric or missing power/toughness (`*`, `X`, `1+*`, `∞`, `NULL`, etc.) is **excluded** whenever a power or toughness filter (min or max) is active. Spec: `docs/superpowers/specs/2026-08-02-power-toughness-filter-design.md`.
- Numeric-safe check (backend SQL): a column value counts as numeric only if `col GLOB '[0-9]*' AND col NOT GLOB '*[^0-9.]*'` (digits and `.` only) — stricter than the existing sort's `GLOB '[0-9]*'`, which wrongly treats `"1+*"` as numeric.
- Power and Toughness are two **separate** filter groups (not combined), each with independent min/max inputs, mirroring the existing "Mana value" (CMC) group.
- Enabled on all three pages that currently have the `'cmc'` facet: Cards browser, Collection view, Deck editor.
- New model fields: `powerMin, powerMax, toughnessMin, toughnessMax` (default `null`). New API params: `power_min, power_max, toughness_min, toughness_max` (all optional floats).

---

### Task 1: Backend — power/toughness range filters on `/api/cards`

**Files:**
- Modify: `app.py:26-63` (`_build_card_filters`), `app.py:228-282` (`search_cards` / `/api/cards`)
- Test: `tests/test_cards_filter_sort.py`

**Interfaces:**
- Produces: `_build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="", power_min=None, power_max=None, toughness_min=None, toughness_max=None) -> (frags: list[str], params: list)`. `/api/cards` accepts new optional query params `power_min, power_max, toughness_min, toughness_max: float | None`.

- [ ] **Step 1: Write the failing tests**

Add to the top of `tests/test_cards_filter_sort.py`:

```python
import sqlite3
```

Then append these tests to the end of the file:

```python
def test_filter_by_power_range(client, seed_cards):
    # powers: Steel Wall 0, Grizzly Bears 2, Wise Elephant 3, Mystery Hydra '*', Ancestral Vision NULL
    r = client.get("/api/cards", params={"power_min": 1, "power_max": 3})
    assert _names(r) == ["Grizzly Bears", "Wise Elephant"]


def test_filter_by_toughness_range(client, seed_cards):
    # toughness: Grizzly Bears 2, Steel Wall 4, Wise Elephant 5, Mystery Hydra '*', Ancestral Vision NULL
    r = client.get("/api/cards", params={"toughness_min": 2, "toughness_max": 4})
    assert _names(r) == ["Grizzly Bears", "Steel Wall"]


def test_filter_by_power_excludes_variable_power(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, power, toughness) "
        "VALUES ('variable', 'Battlefield Construct', '{2}', 2, 'Creature — Construct', '1+*', '1+*')"
    )
    conn.commit()
    conn.close()
    # CAST('1+*' AS REAL) == 1.0 in SQLite, so a naive numeric check would wrongly
    # let this card pass power_min=1; the stricter digits-and-dot-only check excludes it.
    r = client.get("/api/cards", params={"power_min": 1})
    assert "Battlefield Construct" not in _names(r)


def test_filter_by_power_combined_with_cmc(client, seed_cards):
    # Grizzly Bears: power 2, cmc 2 -> matches both.
    # Wise Elephant: power 3, but cmc 5 -> excluded by cmc_max.
    r = client.get("/api/cards", params={"power_min": 2, "cmc_max": 2})
    assert _names(r) == ["Grizzly Bears"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cards_filter_sort.py -v -k "power"`
Expected: FAIL — `power_min`/`power_max`/`toughness_min`/`toughness_max` are unknown query params (FastAPI silently ignores unknown `Query` params today, so results come back unfiltered), so `test_filter_by_power_range`, `test_filter_by_toughness_range`, and `test_filter_by_power_combined_with_cmc` fail on the name-list assertion (all 5 seeded cards / wrong set returned instead of the filtered subset). `test_filter_by_power_excludes_variable_power` fails because `"Battlefield Construct"` is still present in the unfiltered response.

- [ ] **Step 3: Implement the numeric-safe range-fragment helper and wire it into `_build_card_filters`**

In `app.py`, add a helper function right before `_build_card_filters` (currently at line 26):

```python
def _numeric_pt_frags(col_expr, min_v, max_v):
    """Return SQL fragments constraining a power/toughness column to a numeric range.

    Power/toughness are stored as free text (e.g. "3", "*", "1+*", "2.5"). A
    value only counts as numeric if it consists solely of digits and ".",
    which excludes "1+*"-style variable values that a bare GLOB '[0-9]*'
    check would wrongly accept (SQLite's CAST stops at the first non-numeric
    character, so CAST('1+*' AS REAL) == 1.0).
    """
    is_numeric = f"({col_expr} GLOB '[0-9]*' AND {col_expr} NOT GLOB '*[^0-9.]*')"
    frags = []
    if min_v is not None:
        frags.append(f"({is_numeric} AND CAST({col_expr} AS REAL) >= ?)")
    if max_v is not None:
        frags.append(f"({is_numeric} AND CAST({col_expr} AS REAL) <= ?)")
    return frags
```

Then change the `_build_card_filters` signature and body:

```python
def _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="",
                         power_min=None, power_max=None, toughness_min=None, toughness_max=None):
```

Add this block right before the final `return frags, params` (i.e. after the existing `text` block):

```python
    for frag in _numeric_pt_frags(f"{col}power", power_min, power_max):
        frags.append(frag)
    if power_min is not None:
        params.append(power_min)
    if power_max is not None:
        params.append(power_max)

    for frag in _numeric_pt_frags(f"{col}toughness", toughness_min, toughness_max):
        frags.append(frag)
    if toughness_min is not None:
        params.append(toughness_min)
    if toughness_max is not None:
        params.append(toughness_max)
```

- [ ] **Step 4: Wire the new params into `/api/cards`**

In `search_cards` (`app.py:228`), add four params to the function signature, right after `cmc_max`:

```python
    cmc_min: float | None = Query(None),
    cmc_max: float | None = Query(None),
    power_min: float | None = Query(None),
    power_max: float | None = Query(None),
    toughness_min: float | None = Query(None),
    toughness_max: float | None = Query(None),
    text: str = Query(""),
```

Update all three `_build_card_filters(...)` call sites in the same function to pass the new args through:

```python
                cfrags, cparams = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="c.",
                                                        power_min=power_min, power_max=power_max,
                                                        toughness_min=toughness_min, toughness_max=toughness_max)
```

```python
                bfrags, bparams = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text,
                                                       power_min=power_min, power_max=power_max,
                                                       toughness_min=toughness_min, toughness_max=toughness_max)
```

```python
            frags, params = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text,
                                                 power_min=power_min, power_max=power_max,
                                                 toughness_min=toughness_min, toughness_max=toughness_max)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_cards_filter_sort.py -v`
Expected: PASS — all tests in the file, including the 4 new ones.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_cards_filter_sort.py
git commit -m "feat: add power/toughness range filters to /api/cards"
```

---

### Task 2: Frontend — `applyFilters` power/toughness checks + `makeFilterModel` fields

**Files:**
- Modify: `static/app.js` (sentinel comments around `ptNum`/`sortComparator`/`applyFilters`, currently `static/app.js:192-248`; `makeFilterModel`, currently `static/app.js:178-184`; `applyFilters`, currently `static/app.js:221-248`)
- Test: `tests/js/apply-filters.test.mjs` (new file)

**Interfaces:**
- Consumes: nothing from Task 1 (independent surface — this is the client-side path used by Collection/Deck views).
- Produces: `makeFilterModel(overrides = {})` returns an object additionally containing `powerMin: null, powerMax: null, toughnessMin: null, toughnessMax: null`. `applyFilters(cards, model)` additionally excludes cards whose `power`/`toughness` don't satisfy an active `model.powerMin/powerMax/toughnessMin/toughnessMax` bound (non-numeric/missing always excluded when a bound is active). Task 3 consumes both.

- [ ] **Step 1: Write the failing test**

Create `tests/js/apply-filters.test.mjs`:

```js
// Tests applyFilters (power/toughness range checks) by extracting it, along
// with its ptNum helper, from static/app.js between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── applyFilters ──';
const END = '// ── end applyFilters ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'applyFilters sentinel comments not found in static/app.js');

const applyFilters = new Function(`${src.slice(from, to)}; return applyFilters;`)();

function baseModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false, types: new Set(),
    cmcMin: null, cmcMax: null, powerMin: null, powerMax: null,
    toughnessMin: null, toughnessMax: null, tags: new Set(),
    ...overrides,
  };
}

const cards = [
  { name: 'Grizzly Bears', power: '2', toughness: '2', cmc: 2, type_line: 'Creature — Bear', color_identity: 'G' },
  { name: 'Wise Elephant', power: '3', toughness: '5', cmc: 5, type_line: 'Creature — Elephant', color_identity: 'G' },
  { name: 'Steel Wall', power: '0', toughness: '4', cmc: 1, type_line: 'Artifact Creature — Wall', color_identity: '' },
  { name: 'Mystery Hydra', power: '*', toughness: '*', cmc: 1, type_line: 'Creature — Hydra', color_identity: 'G' },
  { name: 'Ancestral Vision', power: null, toughness: null, cmc: 1, type_line: 'Sorcery', color_identity: 'U' },
];

const names = (result) => result.map(c => c.name);

const cases = [
  ['power range 1-3 excludes non-numeric/missing/out-of-range',
    baseModel({ powerMin: 1, powerMax: 3 }),
    ['Grizzly Bears', 'Wise Elephant']],
  ['toughness range 2-4 excludes non-numeric/missing/out-of-range',
    baseModel({ toughnessMin: 2, toughnessMax: 4 }),
    ['Grizzly Bears', 'Steel Wall']],
  ['power min only',
    baseModel({ powerMin: 2 }),
    ['Grizzly Bears', 'Wise Elephant']],
  ['no power/toughness filter passes everything through',
    baseModel(),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision']],
];

let failed = 0;
for (const [label, model, expectedNames] of cases) {
  const result = names(applyFilters(cards, model));
  try {
    assert.deepEqual(result, expectedNames);
    console.log(`  ok  ${label}`);
  } catch {
    failed++;
    console.error(`  FAIL ${label} -> ${JSON.stringify(result)}, expected ${JSON.stringify(expectedNames)}`);
  }
}
console.log(failed ? `\n${failed} failing` : `\nall ${cases.length} passing`);
process.exit(failed ? 1 : 0);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node tests/js/apply-filters.test.mjs`
Expected: throws an uncaught `AssertionError: applyFilters sentinel comments not found in static/app.js` (the sentinel comments don't exist yet), exiting non-zero.

- [ ] **Step 3: Add sentinel comments around the `ptNum`/`sortComparator`/`applyFilters` block**

In `static/app.js`, immediately before `function ptNum(v) {` (currently line 192), add:

```js
// ── applyFilters ──
```

Immediately after the closing `}` of `applyFilters` (currently line 248), add:

```js
// ── end applyFilters ──
```

- [ ] **Step 4: Add power/toughness fields to `makeFilterModel`**

In `static/app.js`, change:

```js
function makeFilterModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false,
    types: new Set(), cmcMin: null, cmcMax: null, tags: new Set(),
    sort: 'name', dir: 'asc', ...overrides,
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
    tags: new Set(), sort: 'name', dir: 'asc', ...overrides,
  };
}
```

- [ ] **Step 5: Add power/toughness range checks to `applyFilters`**

In `static/app.js`, inside `applyFilters`, change:

```js
    if (model.cmcMin != null && (c.cmc ?? 0) < model.cmcMin) return false;
    if (model.cmcMax != null && (c.cmc ?? 0) > model.cmcMax) return false;
    if (model.tags.size) {
```

to:

```js
    if (model.cmcMin != null && (c.cmc ?? 0) < model.cmcMin) return false;
    if (model.cmcMax != null && (c.cmc ?? 0) > model.cmcMax) return false;
    if (model.powerMin != null || model.powerMax != null) {
      const pv = ptNum(c.power);
      if (pv == null) return false;
      if (model.powerMin != null && pv < model.powerMin) return false;
      if (model.powerMax != null && pv > model.powerMax) return false;
    }
    if (model.toughnessMin != null || model.toughnessMax != null) {
      const tv = ptNum(c.toughness);
      if (tv == null) return false;
      if (model.toughnessMin != null && tv < model.toughnessMin) return false;
      if (model.toughnessMax != null && tv > model.toughnessMax) return false;
    }
    if (model.tags.size) {
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `node tests/js/apply-filters.test.mjs`
Expected: `all 4 passing`, exit code 0.

- [ ] **Step 7: Commit**

```bash
git add static/app.js tests/js/apply-filters.test.mjs
git commit -m "feat: add power/toughness range checks to client-side applyFilters"
```

---

### Task 3: Frontend — filter panel UI, param wiring, and per-page enablement

**Files:**
- Modify: `static/app.js` — `activeFilterCount` (currently `static/app.js:250-258`), `modelToParams` (currently `static/app.js:260-271`), `buildFilterControls`'s CMC block (currently `static/app.js:380-399`), and the three `facets: new Set([...])` call sites (currently `static/app.js:1287`, `:1449`, `:1792`)

**Interfaces:**
- Consumes: `makeFilterModel` fields and `applyFilters` behavior from Task 2; `/api/cards` query params `power_min, power_max, toughness_min, toughness_max` from Task 1.
- Produces: `appendRangeFilterGroup(panel, label, model, minKey, maxKey, refreshBadge, onChange)` — shared min/max range-input builder used by the CMC, Power, and Toughness filter groups. `buildFilterControls` recognizes new facets `'power'` and `'toughness'`. All three pages (Cards browser, Collection, Deck editor) enable them.

No automated test exists for DOM-building code in this codebase (per spec section 3b) — this task is implementation + a manual verification checklist in place of an automated test cycle.

- [ ] **Step 1: Update `activeFilterCount`**

In `static/app.js`, change:

```js
function activeFilterCount(model) {
  let n = 0;
  if (model.text) n++;
  if (model.colorlessOnly || model.colors.size) n++;
  if (model.types.size) n++;
  if (model.cmcMin != null || model.cmcMax != null) n++;
  if (model.tags.size) n++;
  return n;
}
```

to:

```js
function activeFilterCount(model) {
  let n = 0;
  if (model.text) n++;
  if (model.colorlessOnly || model.colors.size) n++;
  if (model.types.size) n++;
  if (model.cmcMin != null || model.cmcMax != null) n++;
  if (model.powerMin != null || model.powerMax != null) n++;
  if (model.toughnessMin != null || model.toughnessMax != null) n++;
  if (model.tags.size) n++;
  return n;
}
```

- [ ] **Step 2: Update `modelToParams`**

In `static/app.js`, change:

```js
  if (model.cmcMin != null) p.cmc_min = model.cmcMin;
  if (model.cmcMax != null) p.cmc_max = model.cmcMax;
  if (model.sort) p.sort = model.sort;
```

to:

```js
  if (model.cmcMin != null) p.cmc_min = model.cmcMin;
  if (model.cmcMax != null) p.cmc_max = model.cmcMax;
  if (model.powerMin != null) p.power_min = model.powerMin;
  if (model.powerMax != null) p.power_max = model.powerMax;
  if (model.toughnessMin != null) p.toughness_min = model.toughnessMin;
  if (model.toughnessMax != null) p.toughness_max = model.toughnessMax;
  if (model.sort) p.sort = model.sort;
```

- [ ] **Step 3: Extract the shared range-group builder**

In `static/app.js`, immediately before the `/**\n * Render a filter/sort control bar into \`container\`...` comment that precedes `function buildFilterControls(container, config) {`, add a new standalone function:

```js
function appendRangeFilterGroup(panel, label, model, minKey, maxKey, refreshBadge, onChange) {
  const grp = document.createElement('div');
  grp.className = 'filter-group';
  grp.innerHTML = `<span class="filter-group-label">${label}</span>`;
  const mk = (key, ph) => {
    const inp = document.createElement('input');
    inp.type = 'number'; inp.min = '0'; inp.className = 'cmc-input';
    inp.placeholder = ph;
    if (model[key] != null) inp.value = model[key];
    inp.addEventListener('input', () => {
      model[key] = inp.value === '' ? null : parseFloat(inp.value);
      refreshBadge(); onChange();
    });
    return inp;
  };
  grp.appendChild(mk(minKey, 'min'));
  grp.appendChild(document.createTextNode('–'));
  grp.appendChild(mk(maxKey, 'max'));
  panel.appendChild(grp);
}
```

- [ ] **Step 4: Replace the inline CMC block with the shared helper, and add Power/Toughness groups**

In `static/app.js`, inside `buildFilterControls`, change:

```js
  // CMC range
  if (facets.has('cmc')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Mana value</span>';
    const mk = (key, ph) => {
      const inp = document.createElement('input');
      inp.type = 'number'; inp.min = '0'; inp.className = 'cmc-input';
      inp.placeholder = ph;
      if (model[key] != null) inp.value = model[key];
      inp.addEventListener('input', () => {
        model[key] = inp.value === '' ? null : parseFloat(inp.value);
        refreshBadge(); onChange();
      });
      return inp;
    };
    grp.appendChild(mk('cmcMin', 'min'));
    grp.appendChild(document.createTextNode('–'));
    grp.appendChild(mk('cmcMax', 'max'));
    panel.appendChild(grp);
  }
```

to:

```js
  // CMC range
  if (facets.has('cmc')) {
    appendRangeFilterGroup(panel, 'Mana value', model, 'cmcMin', 'cmcMax', refreshBadge, onChange);
  }

  // Power range
  if (facets.has('power')) {
    appendRangeFilterGroup(panel, 'Power', model, 'powerMin', 'powerMax', refreshBadge, onChange);
  }

  // Toughness range
  if (facets.has('toughness')) {
    appendRangeFilterGroup(panel, 'Toughness', model, 'toughnessMin', 'toughnessMax', refreshBadge, onChange);
  }
```

- [ ] **Step 5: Enable the new facets on the Cards browser**

In `static/app.js`, inside `init()`, change:

```js
    facets: new Set(['colors', 'types', 'cmc']),
```

to:

```js
    facets: new Set(['colors', 'types', 'cmc', 'power', 'toughness']),
```

- [ ] **Step 6: Enable the new facets on Collection and Deck editor**

In `static/app.js`, this exact line appears twice — once in `loadCollectionView()`, once in `selectDeck()`:

```js
      facets: new Set(['colors', 'types', 'cmc', 'tags']),
```

Replace **both** occurrences with:

```js
      facets: new Set(['colors', 'types', 'cmc', 'power', 'toughness', 'tags']),
```

- [ ] **Step 7: Run the existing test suites to confirm nothing broke**

Run: `python -m pytest -v` and `for f in tests/js/*.test.mjs; do node "$f" || exit 1; done`
Expected: all pass, including the Task 1/2 additions.

- [ ] **Step 8: Manual verification**

Start the dev server: `uvicorn app:app --reload`, then in a browser at `http://localhost:8000`:

- **Cards page:** open the Filters panel; confirm "Power" and "Toughness" groups appear beside "Mana value". Set Power min=2, max=4 — confirm the grid narrows to creatures with numeric power in that range and that `*`/variable-power/non-creature cards drop out. Confirm the filter badge count increases by one per active group (Power, Toughness independently). Click Clear — confirm both new inputs reset and the grid returns to unfiltered.
- **Collection page:** repeat the same Power/Toughness filter check against owned cards.
- **Deck editor:** open a deck, repeat the same check against its card list (grid or text view).

- [ ] **Step 9: Commit**

```bash
git add static/app.js
git commit -m "feat: add power/toughness filter UI, wire through all three filterable pages"
```

---
