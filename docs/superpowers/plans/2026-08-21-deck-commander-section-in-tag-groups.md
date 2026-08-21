# Commander Section in Tag-Grouped Deck Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the deck page is grouped by `deck-tag` or `collection-tag`, pull the commander into its own leading `Commander` section, exactly as `groupCardsByType` already does for `groupBy === 'type'`.

**Architecture:** Add a small pure helper, `extractCommanderGroup(cards)`, next to the existing grouping helpers in `static/app.js`. Wrap the two call sites in `renderDeckGrid` and `renderDeckText` that call `groupCards(mainCards, tagField)` so that, only for the tag-based branches, the commander is extracted first and re-inserted as a leading group. `groupCardsByType` itself, `groupCards` itself, and the `groupBy === 'none'` / collection-page call site are untouched.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework). Tests are plain `.mjs` files under `tests/js/` that extract a function from `static/app.js` via sentinel comments and run under plain `node`, no test runner/framework.

**Spec:** `docs/superpowers/backlog/001-deck-commander-section-in-tag-groups.md`

## Global Constraints

- `groupBy === 'type'` behavior must be byte-for-byte unchanged (still `groupCardsByType`'s internal bucket).
- `groupBy === 'none'` behavior must be unchanged (commander pinned first via existing sort comparator in both `renderDeckGrid` and `renderDeckText`).
- The collection page's `groupCards(filtered, 'collection_tags')` call site (around `static/app.js:1593`) must not be touched.
- `groupCards` itself must not be modified — only its call sites in `renderDeckGrid`/`renderDeckText` change.
- A deck with no commander must render tag-grouped views exactly as today (no empty `Commander` group).
- New JS logic must follow the existing test pattern: sentinel-comment-delimited function extracted and tested via plain `node` (see `tests/js/group-cards-by-type.test.mjs`), no new dependencies.

---

### Task 1: Add and test `extractCommanderGroup` helper

**Files:**
- Modify: `static/app.js` (add helper near `groupCards`, i.e. just after line 1417, before the `// ── groupCardsByType ──` sentinel block starting at line 1419)
- Test: `tests/js/extract-commander-group.test.mjs` (new)

**Interfaces:**
- Produces: `function extractCommanderGroup(cards)` → `{ commanderGroup: {label: 'Commander', cards: [card]} | null, rest: Array }`. `rest` preserves the original order/array of all non-commander cards (same array elements, filtered). Consumed by Task 2 in `renderDeckGrid` and `renderDeckText`.

- [ ] **Step 1: Write the failing test**

Create `tests/js/extract-commander-group.test.mjs`:

```js
// Tests extractCommanderGroup by extracting it from static/app.js (a plain
// browser script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── extractCommanderGroup ──';
const END = '// ── end extractCommanderGroup ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'extractCommanderGroup sentinel comments not found in static/app.js');

const extractCommanderGroup = new Function(`${src.slice(from, to)}; return extractCommanderGroup;`)();

const commander = { id: 'c', name: 'Atraxa', is_commander: true };
const tagged     = { id: 't', name: 'Bear',   is_commander: false, deck_tags: ['ramp'] };
const untagged   = { id: 'u', name: 'Bolt',   is_commander: false, deck_tags: [] };

let failed = 0;
function check(label, actual, expected) {
  try {
    assert.deepEqual(actual, expected);
    console.log(`  ok  ${label}`);
  } catch {
    failed++;
    console.error(`  FAIL ${label} -> ${JSON.stringify(actual)}, expected ${JSON.stringify(expected)}`);
  }
}

{
  const { commanderGroup, rest } = extractCommanderGroup([tagged, commander, untagged]);
  check(
    'commander is split into its own group',
    commanderGroup,
    { label: 'Commander', cards: [commander] }
  );
  check(
    'rest excludes the commander, preserves order',
    rest.map(c => c.id),
    ['t', 'u']
  );
}

{
  const { commanderGroup, rest } = extractCommanderGroup([tagged, untagged]);
  check(
    'no commander in the list means commanderGroup is null',
    commanderGroup,
    null
  );
  check(
    'rest is unchanged when there is no commander',
    rest.map(c => c.id),
    ['t', 'u']
  );
}

console.log(failed ? `\n${failed} failing` : `\nall 4 checks passing`);
process.exit(failed ? 1 : 0);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/js/extract-commander-group.test.mjs`
Expected: fails the `assert.ok` sentinel check (helper doesn't exist yet) — output like `AssertionError: extractCommanderGroup sentinel comments not found in static/app.js`.

- [ ] **Step 3: Add the helper to `static/app.js`**

In `static/app.js`, insert this block immediately after line 1417 (the closing `}` of `groupCards`) and before the `// ── groupCardsByType ──` comment on line 1419:

```js
// ── extractCommanderGroup ──
/**
 * Splits the commander out of a card array into its own group, for grouped
 * views (deck-tag / collection-tag) that don't otherwise special-case it.
 * Mirrors the leading Commander bucket groupCardsByType keeps internally.
 */
function extractCommanderGroup(cards) {
  const commander = cards.find(c => c.is_commander);
  if (!commander) return { commanderGroup: null, rest: cards };
  return { commanderGroup: { label: 'Commander', cards: [commander] }, rest: cards.filter(c => !c.is_commander) };
}
// ── end extractCommanderGroup ──

```

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/js/extract-commander-group.test.mjs`
Expected: `all 4 checks passing`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add static/app.js tests/js/extract-commander-group.test.mjs
git commit -m "feat(deck): add extractCommanderGroup helper for tag-grouped views"
```

---

### Task 2: Wire `extractCommanderGroup` into `renderDeckGrid` and `renderDeckText`

**Files:**
- Modify: `static/app.js:1987-1990` (inside `renderDeckGrid`)
- Modify: `static/app.js:2109-2112` (inside `renderDeckText`) — line numbers shift by however many lines Task 1 added; locate by the `deckState.groupBy !== 'none'` block containing the `groupCardsByType(mainCards) : groupCards(...)` ternary, there are exactly two such blocks.
- Test: manual verification via steps below (no automated harness exists for `renderDeckGrid`/`renderDeckText` — they read/write the live DOM and `deckState` singleton, consistent with the rest of `static/app.js`'s render functions, none of which have `.mjs` unit tests).

**Interfaces:**
- Consumes: `extractCommanderGroup(cards)` from Task 1 → `{ commanderGroup, rest }`.

- [ ] **Step 1: Update `renderDeckGrid`**

Current code (`static/app.js`, inside `renderDeckGrid`, originally lines 1987-1990, shifted by Task 1's insert):

```js
  if (deckState.groupBy !== 'none') {
    const groups = deckState.groupBy === 'type'
      ? groupCardsByType(mainCards)
      : groupCards(mainCards, deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags');
    for (const g of groups) g.cards.sort(cmp);
```

Replace with:

```js
  if (deckState.groupBy !== 'none') {
    let groups;
    if (deckState.groupBy === 'type') {
      groups = groupCardsByType(mainCards);
    } else {
      const { commanderGroup, rest } = extractCommanderGroup(mainCards);
      groups = groupCards(rest, deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags');
      if (commanderGroup) groups.unshift(commanderGroup);
    }
    for (const g of groups) g.cards.sort(cmp);
```

Leave the rest of the function (the `consideringCards` push, `renderGroupedGrid` call, and the `else` branch for `groupBy === 'none'`) unchanged. Note: the commander-only group will get re-sorted by `cmp` in the `for (const g of groups) g.cards.sort(cmp)` loop below — harmless since it has exactly one card.

- [ ] **Step 2: Update `renderDeckText`**

Apply the identical replacement to the matching block inside `renderDeckText` (originally lines 2109-2112, same before/after text as Step 1).

- [ ] **Step 3: Manually verify in the running app**

Start the app (`uvicorn app:app --reload`), open a deck that has a commander designated and at least one deck-tag and one collection-tag assigned to various cards, including the commander itself with and without tags (test both). For each of grid view and text view:
  - Set group-by to "Deck Tag": confirm a `Commander` section appears first, containing only the commander, and the commander does not also appear inside any deck-tag group or `Untagged`.
  - Set group-by to "Collection Tag": same check.
  - Set group-by to "Type": confirm behavior is identical to before this change (commander in its own bucket via `groupCardsByType`, as before).
  - Set group-by to "None": confirm the commander is still just pinned first in the flat list (no `Commander` header), as before.
  - Open a deck with no commander designated: confirm no `Commander` section appears in any group-by mode.
  - Open the collection page, group by tag: confirm behavior is unaffected (no `Commander` section, since collection cards don't carry `is_commander` in that context).

- [ ] **Step 4: Run the JS test suite to confirm no regressions**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done`
Expected: every file prints `all N checks passing` and the loop exits 0.

- [ ] **Step 5: Run the Python test suite to confirm no regressions**

Run: `pytest`
Expected: all existing tests pass (this change touches only frontend JS, so no Python test should be affected).

- [ ] **Step 6: Commit**

```bash
git add static/app.js
git commit -m "feat(deck): give commander its own section in tag-grouped views"
```

---

## Self-Review Notes

- Spec coverage: helper (✅ Task 1), both call sites grid+text (✅ Task 2 Steps 1-2), type/none/collection-page untouched (✅ explicit constraints + manual checks in Task 2 Step 3), no-commander deck case (✅ Task 1 test + Task 2 Step 3 manual check).
- Placeholder scan: none — all steps have concrete code/commands.
- Type consistency: `extractCommanderGroup` signature (`{commanderGroup, rest}`) is defined once in Task 1 and consumed identically in both Task 2 call sites.
