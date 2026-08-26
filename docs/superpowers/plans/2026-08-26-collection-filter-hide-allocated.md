# Collection Filter: Hide Fully-Allocated Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collection-view-only filter toggle that hides a card when every owned copy is already committed to built decks' main-deck (non-Considering) cards, while keeping it visible if at least one copy is free.

**Architecture:** `GET /api/collection` gains one new computed column, `allocated_qty`, via a correlated subquery summing `deck_cards.quantity` across built decks (excluding Considering rows) for each card. The frontend adds a `hideFullyAllocated` boolean to the existing filter-model/applyFilters/buildFilterControls machinery, following the exact same opt-in-per-view pattern items 014 (`unownedOnly`) and prior work already established — a new `showHideAllocatedToggle` config flag, wired only on the collection filter bar.

**Tech Stack:** Python (FastAPI, sqlite3), vanilla JS, pytest, Node (`tests/js/*.test.mjs`).

**Spec:** `docs/superpowers/backlog/019-collection-filter-hide-allocated.md`

## Global Constraints

- Depends on item 018 (already merged) — `decks.built` exists.
- "Allocated" only counts a built deck's non-Considering `deck_cards` rows (`is_considering = 0`), matching item 018/020's shared rule.
- Collection view only — do not touch the card browser or deck filter bars.
- Reuse the existing accent-highlight `.active` convention (see `.hide-lands-btn.active` / `.unowned-only-btn.active` in `static/style.css`) — no new visual language.

---

### Task 1: Backend — `allocated_qty` on `GET /api/collection`

**Files:**
- Modify: `app.py` (`get_collection`)
- Test: `tests/test_collection_allocated.py` (new)

**Interfaces:**
- Produces: each row from `GET /api/collection` gains an integer `allocated_qty` field (0 when nothing is allocated), consumed by Task 2's frontend filter.

- [ ] **Step 1: Write failing tests**

Create `tests/test_collection_allocated.py`. The base seeded DB (`tests/conftest.py`) has card id 1 ("Lightning Bolt") with collection quantity 4 and deck id 1 ("Test Deck") holding 4 copies of it — use raw `sqlite3` to mark decks built/not and adjust `deck_cards` rows per test, matching the style of `tests/test_deck_built.py`.

```python
import sqlite3


def test_collection_row_includes_allocated_qty_zero_by_default(client, db_path):
    r = client.get("/api/collection")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 0


def test_allocated_qty_counts_built_deck_cards(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 4


def test_allocated_qty_ignores_non_built_deck_cards(client, db_path):
    # deck 1 is NOT built (default) and already holds 4 copies of card 1 per
    # the base fixture — allocated_qty must stay 0 until the deck is built.
    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 0


def test_allocated_qty_ignores_considering_cards_in_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.execute("UPDATE deck_cards SET is_considering = 1 WHERE deck_id = 1 AND card_id = 1")
    conn.commit()
    conn.close()

    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 0


def test_allocated_qty_sums_across_multiple_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Second Deck', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 2)")
    conn.commit()
    conn.close()

    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 6
```

- [ ] **Step 2: Run them to verify the built-deck-related ones fail**

Run: `pytest tests/test_collection_allocated.py -v`
Expected: `test_collection_row_includes_allocated_qty_zero_by_default` and `test_allocated_qty_ignores_non_built_deck_cards` FAIL with a `KeyError` (no `allocated_qty` key exists yet on the response rows at all); the others also fail once that's fixed, for the same underlying reason.

- [ ] **Step 3: Implement**

In `app.py`, replace `get_collection`'s query:

```python
        cur.execute("""
            SELECT c.id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text,
                   c.colors, c.color_identity, c.image_uri, c.power, c.toughness,
                   col.quantity
            FROM collection col
            JOIN cards c ON c.id = col.card_id
            WHERE col.quantity > 0
            ORDER BY c.name
        """)
```

with:

```python
        cur.execute("""
            SELECT c.id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text,
                   c.colors, c.color_identity, c.image_uri, c.power, c.toughness,
                   col.quantity,
                   COALESCE((
                       SELECT SUM(dc.quantity) FROM deck_cards dc
                       JOIN decks d ON d.id = dc.deck_id
                       WHERE dc.card_id = c.id AND dc.is_considering = 0 AND d.built = 1
                   ), 0) AS allocated_qty
            FROM collection col
            JOIN cards c ON c.id = col.card_id
            WHERE col.quantity > 0
            ORDER BY c.name
        """)
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `pytest tests/test_collection_allocated.py -v`
Expected: PASS for all 5 tests.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS for everything — this is an additive column, no existing consumer of `/api/collection` breaks.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_collection_allocated.py
git commit -m "feat: expose allocated_qty on GET /api/collection"
```

---

### Task 2: Frontend — `hideFullyAllocated` filter toggle

**Files:**
- Modify: `static/app.js` (`makeFilterModel`, `applyFilters`, `buildFilterControls`, the collection-filter-controls call site)
- Modify: `static/style.css`
- Modify: `tests/js/apply-filters.test.mjs`

**Interfaces:**
- Consumes: `allocated_qty` field from Task 1.

- [ ] **Step 1: Write failing JS tests**

In `tests/js/apply-filters.test.mjs`, add `allocated_qty` and `quantity` fields to two of the existing fixture cards (Grizzly Bears, owned per the file's existing ownership comment, and Steel Wall) so the new filter has something concrete to distinguish, then add new cases. Find:

```js
const cards = [
  { id: 1, name: 'Grizzly Bears', power: '2', toughness: '2', cmc: 2, type_line: 'Creature — Bear', color_identity: 'G', colors: 'G' },
  { id: 2, name: 'Wise Elephant', power: '3', toughness: '5', cmc: 5, type_line: 'Creature — Elephant', color_identity: 'G', colors: 'G' },
  { id: 3, name: 'Steel Wall', power: '0', toughness: '4', cmc: 1, type_line: 'Artifact Creature — Wall', color_identity: '', colors: '' },
```

Replace with (add `quantity`/`allocated_qty` to these two rows only — every other fixture card is untouched):

```js
const cards = [
  { id: 1, name: 'Grizzly Bears', power: '2', toughness: '2', cmc: 2, type_line: 'Creature — Bear', color_identity: 'G', colors: 'G', quantity: 4, allocated_qty: 4 },
  { id: 2, name: 'Wise Elephant', power: '3', toughness: '5', cmc: 5, type_line: 'Creature — Elephant', color_identity: 'G', colors: 'G' },
  { id: 3, name: 'Steel Wall', power: '0', toughness: '4', cmc: 1, type_line: 'Artifact Creature — Wall', color_identity: '', colors: '', quantity: 3, allocated_qty: 1 },
```

Find the `baseModel` helper:

```js
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
```

Replace with:

```js
function baseModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false, types: new Set(),
    cmcMin: null, cmcMax: null, powerMin: null, powerMax: null,
    toughnessMin: null, toughnessMax: null, exactColors: new Set(),
    exactColorlessOnly: false, tags: new Set(), hideLands: false,
    unownedOnly: false, hideFullyAllocated: false,
    ...overrides,
  };
}
```

Find the closing of the `cases` array (the `unownedOnly` combines-with-`hideLands` case is the last entry):

```js
  ['unownedOnly combines with hideLands (AND semantics): excludes owned AND excludes lands',
    baseModel({ unownedOnly: true, hideLands: true }),
    ['Wise Elephant', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman']],
];
```

Replace with (add 2 new cases before the closing `];`):

```js
  ['unownedOnly combines with hideLands (AND semantics): excludes owned AND excludes lands',
    baseModel({ unownedOnly: true, hideLands: true }),
    ['Wise Elephant', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman']],
  ['hideFullyAllocated excludes a card whose allocated_qty meets/exceeds its quantity, keeps a card with a free copy',
    baseModel({ hideFullyAllocated: true }),
    ['Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman', 'Forest', 'Jwari Disruption // Jwari Ruins']],
  ['hideFullyAllocated false (default) shows everything regardless of allocation',
    baseModel({ hideFullyAllocated: false }),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman', 'Forest', 'Jwari Disruption // Jwari Ruins']],
];
```

(Grizzly Bears: `quantity: 4, allocated_qty: 4` — fully allocated, hidden. Steel Wall: `quantity: 3, allocated_qty: 1` — one free copy, stays visible. Every other fixture card has no `allocated_qty`/`quantity` fields at all, which must be treated as "0 allocated" — i.e. never hidden by this filter — matching how a card the collection view wouldn't even include unallocated fields for should behave.)

- [ ] **Step 2: Run it to verify the new cases fail**

Run: `node tests/js/apply-filters.test.mjs`
Expected: the 2 new cases FAIL (`hideFullyAllocated` isn't read by `applyFilters` yet, so the toggle has no effect and both cases return the full list) — every pre-existing case still passes.

- [ ] **Step 3: Implement the model field and filter check**

In `static/app.js`, find:

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

Replace with:

```js
function makeFilterModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false,
    types: new Set(), cmcMin: null, cmcMax: null,
    powerMin: null, powerMax: null, toughnessMin: null, toughnessMax: null,
    exactColors: new Set(), exactColorlessOnly: false,
    tags: new Set(), hideLands: false, unownedOnly: false, hideFullyAllocated: false,
    sort: 'name', dir: 'asc', ...overrides,
  };
}
```

Find, inside `applyFilters` (between its sentinel comments):

```js
    if (model.hideLands && (c.type_line || '').includes('Land')) return false;
    if (model.unownedOnly && qty(c.id) > 0) return false;
```

Replace with:

```js
    if (model.hideLands && (c.type_line || '').includes('Land')) return false;
    if (model.unownedOnly && qty(c.id) > 0) return false;
    if (model.hideFullyAllocated && (c.allocated_qty || 0) >= (c.quantity || 0)) return false;
```

This intentionally uses `c.quantity`/`c.allocated_qty` (fields present on collection rows from `GET /api/collection`), not the `qty()` helper — the helper reads the global `state.collection` map, which doesn't carry `allocated_qty`. This filter is meaningful only on collection rows, which already carry both fields directly.

- [ ] **Step 4: Run the JS test again to verify it passes**

Run: `node tests/js/apply-filters.test.mjs`
Expected: all cases pass, including the 2 new ones.

- [ ] **Step 5: Add the toggle button to `buildFilterControls`**

In `static/app.js`, find:

```js
function buildFilterControls(container, config) {
  const { model, facets, sortOptions, tagOptions = [], onChange, showHideLandsToggle = false, showUnownedOnlyToggle = false } = config;
```

Replace with:

```js
function buildFilterControls(container, config) {
  const { model, facets, sortOptions, tagOptions = [], onChange, showHideLandsToggle = false, showUnownedOnlyToggle = false, showHideAllocatedToggle = false } = config;
```

Find:

```js
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

Add immediately after it:

```js

  // Hide Allocated toggle
  let hideAllocatedBtn = null;
  if (showHideAllocatedToggle) {
    hideAllocatedBtn = document.createElement('button');
    hideAllocatedBtn.className = 'hide-allocated-btn action-btn' + (model.hideFullyAllocated ? ' active' : '');
    hideAllocatedBtn.textContent = 'Hide Allocated';
    hideAllocatedBtn.addEventListener('click', () => {
      model.hideFullyAllocated = !model.hideFullyAllocated;
      hideAllocatedBtn.classList.toggle('active', model.hideFullyAllocated);
      onChange();
    });
  }
```

Find the Clear-filters handler:

```js
  clearBtn.addEventListener('click', () => {
    // Text search is owned by the page's search box, so Clear preserves it.
    const keepText = model.text;
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText, hideLands: model.hideLands, unownedOnly: model.unownedOnly }));
    buildFilterControls(container, config);  // re-render to reset control state
    onChange();
  });
```

Replace with:

```js
  clearBtn.addEventListener('click', () => {
    // Text search is owned by the page's search box, so Clear preserves it.
    const keepText = model.text;
    Object.assign(model, makeFilterModel({
      sort: model.sort, dir: model.dir, text: keepText,
      hideLands: model.hideLands, unownedOnly: model.unownedOnly,
      hideFullyAllocated: model.hideFullyAllocated,
    }));
    buildFilterControls(container, config);  // re-render to reset control state
    onChange();
  });
```

Find:

```js
  if (landsBtn) container.appendChild(landsBtn);
  if (unownedBtn) container.appendChild(unownedBtn);
```

Replace with:

```js
  if (landsBtn) container.appendChild(landsBtn);
  if (unownedBtn) container.appendChild(unownedBtn);
  if (hideAllocatedBtn) container.appendChild(hideAllocatedBtn);
```

- [ ] **Step 6: Wire the toggle onto the collection filter bar only**

In `static/app.js`, find:

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

Replace with:

```js
    buildFilterControls(document.getElementById('collection-filter-controls'), {
      model: collectionState.filter,
      facets: new Set(['colors', 'exactColors', 'types', 'cmc', 'power', 'toughness', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions,
      onChange: renderCollectionGrid,
      showHideLandsToggle: true,
      showHideAllocatedToggle: true,
    });
```

Do NOT add `showHideAllocatedToggle: true` to the card-browser (`browser-filter-controls`) or deck (`deck-filter-controls`) call sites.

- [ ] **Step 7: Add the active-state CSS**

In `static/style.css`, find:

```css
.hide-lands-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
.unowned-only-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
```

Add a line right after (before the `#deck-built-btn.active` line that already follows):

```css
.hide-allocated-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
```

- [ ] **Step 8: Run the full check**

Run:
```bash
node --check static/app.js
node tests/js/apply-filters.test.mjs
for f in tests/js/*.test.mjs; do node "$f" || echo "FAILED: $f"; done
pytest -v
```
Expected: PASS everywhere.

- [ ] **Step 9: Manual verification**

In this worktree, run `python3 main.py` if not already migrated, then `uvicorn app:app --reload --port 8001`. In a browser: open the Collection tab, confirm a new "Hide Allocated" button appears next to "Hide Lands" with the same visual style; mark a deck built (via the item-018 toggle) that contains some of your owned cards, add/confirm at least one card is now fully allocated (owned quantity == allocated quantity) and at least one card in that deck still has a free copy; toggle "Hide Allocated" and confirm the fully-allocated card disappears while the free-copy card stays; toggle off and confirm it reappears; open "Clear" and confirm the toggle's state survives being cleared, matching Hide Lands/Unowned Only.

- [ ] **Step 10: Commit**

```bash
git add static/app.js static/style.css tests/js/apply-filters.test.mjs
git commit -m "feat: add Hide Allocated toggle to collection filter bar"
```

---

### Task 3: Check off acceptance criteria and finish

**Files:**
- Modify: `docs/superpowers/backlog/019-collection-filter-hide-allocated.md`

- [ ] **Step 1: Verify each acceptance criterion against the finished work, then check it off**

Re-read the item's "Acceptance criteria" section and mark each `- [ ]` as `- [x]` only once genuinely confirmed — Tasks 1-2's tests and manual verification already cover all of them (toggle behavior, spare-copy visibility, Considering exclusion, non-built-deck exclusion, Clear-persistence, other filter bars unaffected).

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/backlog/019-collection-filter-hide-allocated.md
git commit -m "docs(backlog): check off item 019 acceptance criteria"
```

- [ ] **Step 3: Run the full test suite one last time**

Run: `pytest -v && for f in tests/js/*.test.mjs; do node "$f"; done`
Expected: PASS for everything.
