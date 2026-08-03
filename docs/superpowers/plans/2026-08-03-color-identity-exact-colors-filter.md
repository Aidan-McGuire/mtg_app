# Color Identity / Exact Colors Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the existing "Colors" filter into two independent groups — Color Identity (existing, unchanged, subset match against `color_identity`) and a new Exact Colors group (exact set-equality match against `colors`) — available on the Cards browser, Collection view, and Deck editor.

**Architecture:** Add a fully independent second filter group in parallel with the existing one, at every layer (backend SQL fragment builder, frontend model, client-side `applyFilters`, and the `buildFilterControls` UI) — the same shape as the recently-shipped power/toughness feature. The `colors` column is already returned everywhere and pre-sorted alphabetically at import time, so exact matching is a plain string-equality comparison, no subset trick needed.

**Tech Stack:** FastAPI + sqlite3 (backend), vanilla JS + DOM (frontend), pytest (backend tests), Node's built-in `assert` module via sentinel-comment extraction (frontend tests).

## Global Constraints

- Two separate, independently-toggleable filter groups — not a mode toggle over one shared color selection. Both can be active at once and AND together with every other filter.
- **Color Identity** (existing): completely unchanged behavior — subset match against `color_identity`, model fields `colors`/`colorlessOnly`, API params `colors`/`colorless`. Only its UI label changes, from "Colors" to "Color Identity".
- **Exact Colors** (new): exact set-equality match against `colors`. New model fields `exactColors: Set, exactColorlessOnly: bool` (default empty/false). New API params `exact_colors` (comma-separated letters) and `exact_colorless` (bool).
- Exact-match SQL/JS both rely on `colors` being pre-sorted alphabetically by the importer (`sort_colors`) — build the comparison string by sorting the selected letters the same way, then compare with `=` (SQL) / `!==` (JS). No `REPLACE`-chain subset logic for this path.
- Enabled everywhere the existing `'colors'` facet is: Cards browser, Collection view, Deck editor.

---

### Task 1: Backend — exact color filter on `/api/cards`

**Files:**
- Modify: `app.py:44-96` (`_build_card_filters`), `app.py:261-325` (`search_cards` / `/api/cards`)
- Test: `tests/test_cards_filter_sort.py`

**Interfaces:**
- Produces: `_build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="", power_min=None, power_max=None, toughness_min=None, toughness_max=None, exact_colors="", exact_colorless=False) -> (frags: list[str], params: list)`. `/api/cards` accepts new optional query params `exact_colors: str = Query("")`, `exact_colorless: bool = Query(False)`.

- [ ] **Step 1: Write the failing tests**

Append these tests to the end of `tests/test_cards_filter_sort.py` (the file already has `import sqlite3` at the top):

```python
def test_filter_by_exact_colors_single_letter(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, colors, color_identity) "
        "VALUES ('deathrite', 'Deathrite Shaman', '{B/G}', 1, 'Creature — Elf Shaman', 'BG', 'BG')"
    )
    conn.commit()
    conn.close()
    # exact G match returns only the mono-green seeded cards, excluding the
    # multicolor Deathrite Shaman even though it contains green.
    r = client.get("/api/cards", params={"exact_colors": "G"})
    assert _names(r) == ["Grizzly Bears", "Mystery Hydra", "Wise Elephant"]


def test_filter_by_exact_colors_multicolor(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, colors, color_identity) "
        "VALUES ('deathrite', 'Deathrite Shaman', '{B/G}', 1, 'Creature — Elf Shaman', 'BG', 'BG')"
    )
    conn.commit()
    conn.close()
    r = client.get("/api/cards", params={"exact_colors": "B,G"})
    assert _names(r) == ["Deathrite Shaman"]


def test_filter_exact_colorless(client, seed_cards):
    r = client.get("/api/cards", params={"exact_colorless": "1"})
    assert _names(r) == ["Steel Wall"]


def test_filter_color_identity_and_exact_colors_combined(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, colors, color_identity) "
        "VALUES ('deathrite', 'Deathrite Shaman', '{B/G}', 1, 'Creature — Elf Shaman', 'BG', 'BG')"
    )
    conn.commit()
    conn.close()
    # Deathrite satisfies exact_colors=B,G but fails colors=G (identity BG is not
    # a subset of {G}); bears/ele/hydra satisfy colors=G but fail exact_colors=B,G
    # (their colors is 'G', not 'BG'). No card satisfies both filters at once, so
    # an empty result proves the two are ANDed rather than ORed.
    r = client.get("/api/cards", params={"colors": "G", "exact_colors": "B,G"})
    assert r.json() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cards_filter_sort.py -v -k "exact_colors or exact_colorless"`
Expected: FAIL — `exact_colors`/`exact_colorless` are unknown query params today (FastAPI ignores them), so every new test's assertion fails: the first two return the full unfiltered seeded set (plus Deathrite Shaman) instead of the exact-matched subset, `test_filter_exact_colorless` returns more than just `["Steel Wall"]`, and the combined test returns a non-empty list instead of `[]`.

- [ ] **Step 3: Add `exact_colors`/`exact_colorless` handling to `_build_card_filters`**

In `app.py`, change the `_build_card_filters` signature (currently at line 44):

```python
def _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="",
                         power_min=None, power_max=None, toughness_min=None, toughness_max=None):
```

to:

```python
def _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="",
                         power_min=None, power_max=None, toughness_min=None, toughness_max=None,
                         exact_colors="", exact_colorless=False):
```

Add this block right before the final `return frags, params` (i.e. after the existing power/toughness block):

```python
    if exact_colorless:
        frags.append(f"{col}colors = ''")
    elif exact_colors:
        wanted_exact = sorted(set(
            c.strip() for c in exact_colors.upper().split(",") if c.strip() in COLOR_LETTERS
        ))
        if wanted_exact:
            frags.append(f"{col}colors = ?")
            params.append("".join(wanted_exact))
```

- [ ] **Step 4: Wire the new params into `/api/cards`**

In `search_cards` (`app.py:261`), add two params to the function signature, right after `toughness_max`:

```python
    toughness_min: float | None = Query(None),
    toughness_max: float | None = Query(None),
    exact_colors: str = Query(""),
    exact_colorless: bool = Query(False),
    text: str = Query(""),
```

Update all three `_build_card_filters(...)` call sites in the same function to pass the new args through:

```python
            cfrags, cparams = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="c.",
                                                    power_min=power_min, power_max=power_max,
                                                    toughness_min=toughness_min, toughness_max=toughness_max,
                                                    exact_colors=exact_colors, exact_colorless=exact_colorless)
```

```python
                bfrags, bparams = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text,
                                                       power_min=power_min, power_max=power_max,
                                                       toughness_min=toughness_min, toughness_max=toughness_max,
                                                       exact_colors=exact_colors, exact_colorless=exact_colorless)
```

```python
            frags, params = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text,
                                                 power_min=power_min, power_max=power_max,
                                                 toughness_min=toughness_min, toughness_max=toughness_max,
                                                 exact_colors=exact_colors, exact_colorless=exact_colorless)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_cards_filter_sort.py -v`
Expected: PASS — all tests in the file, including the 4 new ones.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_cards_filter_sort.py
git commit -m "feat: add exact-color-match filter to /api/cards"
```

---

### Task 2: Frontend — `applyFilters` exact-color check + `makeFilterModel` fields

**Files:**
- Modify: `static/app.js` — `makeFilterModel` (currently `static/app.js:178-185`), `applyFilters` (currently `static/app.js:229-269`, inside the existing `// ── applyFilters ──` sentinel block)
- Test: `tests/js/apply-filters.test.mjs`

**Interfaces:**
- Consumes: nothing from Task 1 (independent surface — this is the client-side path used by Collection/Deck views).
- Produces: `makeFilterModel(overrides = {})` returns an object additionally containing `exactColors: new Set(), exactColorlessOnly: false`. `applyFilters(cards, model)` additionally excludes cards whose `colors` field doesn't exactly equal the canonical sorted string built from `model.exactColors` (or isn't `''` when `model.exactColorlessOnly` is set). Task 3 consumes both.

- [ ] **Step 1: Write the failing test**

Replace the full contents of `tests/js/apply-filters.test.mjs` with:

```js
// Tests applyFilters (power/toughness range checks, color identity, and exact
// color match) by extracting it, along with its ptNumStrict helper, from
// static/app.js between its sentinel comments.
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
    toughnessMin: null, toughnessMax: null, exactColors: new Set(),
    exactColorlessOnly: false, tags: new Set(),
    ...overrides,
  };
}

const cards = [
  { name: 'Grizzly Bears', power: '2', toughness: '2', cmc: 2, type_line: 'Creature — Bear', color_identity: 'G', colors: 'G' },
  { name: 'Wise Elephant', power: '3', toughness: '5', cmc: 5, type_line: 'Creature — Elephant', color_identity: 'G', colors: 'G' },
  { name: 'Steel Wall', power: '0', toughness: '4', cmc: 1, type_line: 'Artifact Creature — Wall', color_identity: '', colors: '' },
  { name: 'Mystery Hydra', power: '*', toughness: '*', cmc: 1, type_line: 'Creature — Hydra', color_identity: 'G', colors: 'G' },
  { name: 'Ancestral Vision', power: null, toughness: null, cmc: 1, type_line: 'Sorcery', color_identity: 'U', colors: 'U' },
  { name: 'Compound Beast', power: '1+*', toughness: '1+*', cmc: 3, type_line: 'Creature — Beast', color_identity: 'G', colors: 'G' },
  { name: 'Deathrite Shaman', power: '1', toughness: '2', cmc: 1, type_line: 'Creature — Elf Shaman', color_identity: 'BG', colors: 'BG' },
];

const names = (result) => result.map(c => c.name);

const cases = [
  // Note: Deathrite Shaman (power 1, toughness 2) is numeric, so it now
  // satisfies these three pre-existing power/toughness ranges too — its name
  // was added to their expected lists when the color fixture card was added.
  ['power range 1-3 excludes non-numeric/missing/out-of-range',
    baseModel({ powerMin: 1, powerMax: 3 }),
    ['Grizzly Bears', 'Wise Elephant', 'Deathrite Shaman']],
  ['toughness range 2-4 excludes non-numeric/missing/out-of-range',
    baseModel({ toughnessMin: 2, toughnessMax: 4 }),
    ['Grizzly Bears', 'Steel Wall', 'Deathrite Shaman']],
  ['power min only',
    baseModel({ powerMin: 2 }),
    ['Grizzly Bears', 'Wise Elephant']],
  ['power filter excludes compound variable power (1+*)',
    baseModel({ powerMin: 0 }),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Deathrite Shaman']],
  ['exact color match on single letter excludes multicolor card',
    baseModel({ exactColors: new Set(['G']) }),
    ['Grizzly Bears', 'Wise Elephant', 'Mystery Hydra', 'Compound Beast']],
  ['exact color match on multiple letters matches only that precise set',
    baseModel({ exactColors: new Set(['B', 'G']) }),
    ['Deathrite Shaman']],
  ['exact colorless matches only the colorless card',
    baseModel({ exactColorlessOnly: true }),
    ['Steel Wall']],
  ['no power/toughness/color filter passes everything through',
    baseModel(),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman']],
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
Expected: the three new exact-color cases fail (`applyFilters` doesn't check `exactColors`/`exactColorlessOnly` yet, so all three return the full 7-card list instead of their filtered subset); all other cases pass, including the power/toughness cases whose expected lists already account for `Deathrite Shaman`'s numeric power/toughness — that logic is unchanged from the prior feature, only the exact-color check is new.

- [ ] **Step 3: Add `exactColors`/`exactColorlessOnly` fields to `makeFilterModel`**

In `static/app.js`, change:

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

to:

```js
function makeFilterModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false,
    types: new Set(), cmcMin: null, cmcMax: null,
    powerMin: null, powerMax: null, toughnessMin: null, toughnessMax: null,
    exactColors: new Set(), exactColorlessOnly: false,
    tags: new Set(), sort: 'name', dir: 'asc', ...overrides,
  };
}
```

- [ ] **Step 4: Add the exact-color check to `applyFilters`**

In `static/app.js`, inside `applyFilters`, change:

```js
    if (model.colorlessOnly) {
      if ((c.color_identity || '') !== '') return false;
    } else if (model.colors.size) {
      for (const ch of (c.color_identity || '')) {
        if (!model.colors.has(ch)) return false;   // subset; '' passes
      }
    }
    if (model.types.size) {
```

to:

```js
    if (model.colorlessOnly) {
      if ((c.color_identity || '') !== '') return false;
    } else if (model.colors.size) {
      for (const ch of (c.color_identity || '')) {
        if (!model.colors.has(ch)) return false;   // subset; '' passes
      }
    }
    if (model.exactColorlessOnly) {
      if ((c.colors || '') !== '') return false;
    } else if (model.exactColors.size) {
      const wantedExact = [...model.exactColors].sort().join('');
      if ((c.colors || '') !== wantedExact) return false;
    }
    if (model.types.size) {
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `node tests/js/apply-filters.test.mjs`
Expected: `all 8 passing`, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add static/app.js tests/js/apply-filters.test.mjs
git commit -m "feat: add exact-color-match check to client-side applyFilters"
```

---

### Task 3: Frontend — Exact Colors UI, param wiring, and per-page enablement

**Files:**
- Modify: `static/app.js` — `activeFilterCount` (currently `static/app.js:271-281`), `modelToParams` (currently `static/app.js:283-298`), the inline `'colors'` facet block inside `buildFilterControls` (currently `static/app.js:369-404`), the `buildFilterControls` JSDoc comment (currently `static/app.js:321-324`), and the three `facets: new Set([...])` call sites (currently `static/app.js:1328`, `:1490`, `:1833`)

**Interfaces:**
- Consumes: `makeFilterModel` fields and `applyFilters` behavior from Task 2; `/api/cards` query params `exact_colors`, `exact_colorless` from Task 1.
- Produces: `appendColorFilterGroup(panel, label, model, colorsKey, colorlessKey, refreshBadge, onChange)` — shared color-button-group builder used by both the Color Identity and Exact Colors groups. `buildFilterControls` recognizes a new facet `'exactColors'`. All three pages (Cards browser, Collection, Deck editor) enable it.

No automated test exists for DOM-building code in this codebase (same as the CMC/Power/Toughness UI work) — this task is implementation + a manual verification checklist in place of an automated test cycle.

- [ ] **Step 1: Update `activeFilterCount`**

In `static/app.js`, change:

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

to:

```js
function activeFilterCount(model) {
  let n = 0;
  if (model.text) n++;
  if (model.colorlessOnly || model.colors.size) n++;
  if (model.exactColorlessOnly || model.exactColors.size) n++;
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
  if (model.colorlessOnly) p.colorless = '1';
  else if (model.colors.size) p.colors = [...model.colors].join(',');
  if (model.types.size) p.types = [...model.types].join(',');
```

to:

```js
  if (model.colorlessOnly) p.colorless = '1';
  else if (model.colors.size) p.colors = [...model.colors].join(',');
  if (model.exactColorlessOnly) p.exact_colorless = '1';
  else if (model.exactColors.size) p.exact_colors = [...model.exactColors].join(',');
  if (model.types.size) p.types = [...model.types].join(',');
```

- [ ] **Step 3: Extract the shared color-group builder**

In `static/app.js`, immediately before `function appendRangeFilterGroup(panel, label, model, minKey, maxKey, refreshBadge, onChange) {` (currently line 300), add a new standalone function:

```js
function appendColorFilterGroup(panel, label, model, colorsKey, colorlessKey, refreshBadge, onChange) {
  const grp = document.createElement('div');
  grp.className = 'filter-group';
  grp.innerHTML = `<span class="filter-group-label">${label}</span>`;
  const clBtn = document.createElement('button');
  clBtn.className = 'color-btn color-C' + (model[colorlessKey] ? ' active' : '');
  clBtn.textContent = 'C';
  clBtn.title = 'Colorless only';
  for (const letter of COLOR_LETTERS) {
    const b = document.createElement('button');
    b.className = 'color-btn color-' + letter +
      (model[colorsKey].has(letter) ? ' active' : '');
    b.textContent = letter;
    b.dataset.color = letter;
    b.addEventListener('click', () => {
      if (model[colorsKey].has(letter)) model[colorsKey].delete(letter);
      else { model[colorsKey].add(letter); model[colorlessKey] = false; }
      b.classList.toggle('active');
      clBtn.classList.toggle('active', model[colorlessKey]);
      refreshBadge(); onChange();
    });
    grp.appendChild(b);
  }
  clBtn.addEventListener('click', () => {
    model[colorlessKey] = !model[colorlessKey];
    if (model[colorlessKey]) model[colorsKey].clear();
    grp.querySelectorAll('.color-btn').forEach(x =>
      x.classList.toggle('active',
        x === clBtn ? model[colorlessKey] : model[colorsKey].has(x.dataset.color)));
    refreshBadge(); onChange();
  });
  grp.appendChild(clBtn);
  panel.appendChild(grp);
}
```

- [ ] **Step 4: Update the `buildFilterControls` JSDoc comment**

In `static/app.js`, change:

```js
/**
 * Render a filter/sort control bar into `container`.
 * config: { model, facets:Set<'colors'|'types'|'cmc'|'power'|'toughness'|'tags'>,
 *           sortOptions:[{value,label}], tagOptions:[], onChange:fn }
 */
```

to:

```js
/**
 * Render a filter/sort control bar into `container`.
 * config: { model, facets:Set<'colors'|'exactColors'|'types'|'cmc'|'power'|'toughness'|'tags'>,
 *           sortOptions:[{value,label}], tagOptions:[], onChange:fn }
 */
```

- [ ] **Step 5: Replace the inline Colors block with the shared helper, relabel it, and add the Exact Colors group**

In `static/app.js`, inside `buildFilterControls`, change:

```js
  // Colors
  if (facets.has('colors')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Colors</span>';
    // Declare clBtn before the loop so the loop's click handlers can reference it.
    const clBtn = document.createElement('button');
    clBtn.className = 'color-btn color-C' + (model.colorlessOnly ? ' active' : '');
    clBtn.textContent = 'C';
    clBtn.title = 'Colorless only';
    for (const letter of COLOR_LETTERS) {
      const b = document.createElement('button');
      b.className = 'color-btn color-' + letter +
        (model.colors.has(letter) ? ' active' : '');
      b.textContent = letter;
      b.dataset.color = letter;
      b.addEventListener('click', () => {
        if (model.colors.has(letter)) model.colors.delete(letter);
        else { model.colors.add(letter); model.colorlessOnly = false; }
        b.classList.toggle('active');
        clBtn.classList.toggle('active', model.colorlessOnly);
        refreshBadge(); onChange();
      });
      grp.appendChild(b);
    }
    clBtn.addEventListener('click', () => {
      model.colorlessOnly = !model.colorlessOnly;
      if (model.colorlessOnly) model.colors.clear();
      grp.querySelectorAll('.color-btn').forEach(x =>
        x.classList.toggle('active',
          x === clBtn ? model.colorlessOnly : model.colors.has(x.dataset.color)));
      refreshBadge(); onChange();
    });
    grp.appendChild(clBtn);
    panel.appendChild(grp);
  }
```

to:

```js
  // Color Identity
  if (facets.has('colors')) {
    appendColorFilterGroup(panel, 'Color Identity', model, 'colors', 'colorlessOnly', refreshBadge, onChange);
  }

  // Exact Colors
  if (facets.has('exactColors')) {
    appendColorFilterGroup(panel, 'Exact Colors', model, 'exactColors', 'exactColorlessOnly', refreshBadge, onChange);
  }
```

- [ ] **Step 6: Enable the new facet on the Cards browser**

In `static/app.js`, inside `init()`, change:

```js
    facets: new Set(['colors', 'types', 'cmc', 'power', 'toughness']),
```

to:

```js
    facets: new Set(['colors', 'exactColors', 'types', 'cmc', 'power', 'toughness']),
```

- [ ] **Step 7: Enable the new facet on Collection and Deck editor**

In `static/app.js`, this exact line appears twice — once in `loadCollectionView()`, once in `selectDeck()`:

```js
      facets: new Set(['colors', 'types', 'cmc', 'power', 'toughness', 'tags']),
```

Replace **both** occurrences with:

```js
      facets: new Set(['colors', 'exactColors', 'types', 'cmc', 'power', 'toughness', 'tags']),
```

- [ ] **Step 8: Run the existing test suites to confirm nothing broke**

Run: `python -m pytest -v` and `for f in tests/js/*.test.mjs; do node "$f" || exit 1; done`
Expected: all pass, including the Task 1/2 additions.

- [ ] **Step 9: Manual verification**

Start the dev server: `uvicorn app:app --reload`, then in a browser at `http://localhost:8000`:

- **Cards page:** open the Filters panel; confirm "Color Identity" (relabeled from "Colors") and "Exact Colors" appear as two separate button rows. Select a single color in Exact Colors — confirm the grid narrows to cards whose actual printed color is exactly that one color (multicolor cards containing it drop out). Confirm the badge count increases independently for each active color group. Select colors in both groups at once — confirm results satisfy both (AND). Click Clear — confirm both groups reset.
- **Collection page:** repeat the same check against owned cards.
- **Deck editor:** open a deck, repeat the same check against its card list.

- [ ] **Step 10: Commit**

```bash
git add static/app.js
git commit -m "feat: add Exact Colors filter UI, wire through all three filterable pages"
```

---
