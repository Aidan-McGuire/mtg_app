# Deck list grouping + focused-card preview panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify grouping (type / collection tag / deck tag) across the deck page's Grid and Text views, and add a persistent left-side card-preview panel driven by keyboard focus or mouse hover, in both views.

**Architecture:** Entirely frontend (`static/index.html`, `static/style.css`, `static/app.js`) — no backend or schema changes; all fields used (`is_commander`, `is_considering`, `type_line`, `collection_tags`, `deck_tags`) already exist on the deck-card objects the API returns. Grouping and preview-panel state extend the existing `deckState` object. Grid and Text view keep separate rendering functions but share the same grouping helpers (`groupCards`, new `groupCardsByType`) and the same group-section/collapse UI (`renderGroupSection`/`renderGroupedGrid`).

**Tech Stack:** Vanilla JS, no build step. Frontend tests are plain Node scripts under `tests/js/` (sentinel-extraction pattern, see Global Constraints) — no DOM/jsdom harness.

## Global Constraints

- Frontend unit tests are plain Node scripts under `tests/js/` that extract a sentinel-delimited, self-contained function out of `static/app.js` via string slicing + `new Function(...)` (see `tests/js/filter-decks.test.mjs` for the pattern). There is no DOM/jsdom harness — this only covers pure functions with no external dependencies (no `document`, no other `app.js` functions/globals). Run them with plain `node tests/js/<file>.test.mjs` (native ARM node is first on `PATH`). Everything else — DOM wiring, rendering, keyboard/hover behavior — is verified manually in a running browser via `uvicorn app:app --reload`, per the convention documented in `docs/superpowers/plans/2026-08-01-deck-switcher-palette.md`.
- No backend changes — do not touch `app.py`, `main.py`, or the DB schema.
- Match existing code style in the touched files: 2-space indent, semicolons, `esc()` for all HTML-interpolated text, `API.imageUrl()` for all card images.
- Follow the approved design spec at `docs/superpowers/specs/2026-08-02-deck-list-grouping-preview-design.md` exactly — it is the source of truth for behavior if this plan and the spec ever disagree.

---

### Task 1: `groupCardsByType` + "Card type" grouping option (Grid view)

**Files:**
- Modify: `static/app.js:1310-1331` (after `groupCards`, insert `groupCardsByType`)
- Modify: `static/app.js:1617` (`deckState.groupBy` comment)
- Modify: `static/app.js:1771-1778` (`renderDeckGrid`'s grouped branch)
- Modify: `static/index.html:67-71` (`#deck-group-by` options)
- Test: `tests/js/group-cards-by-type.test.mjs` (new — mirrors `tests/js/filter-decks.test.mjs`)

**Interfaces:**
- Produces: `groupCardsByType(cards: Card[]) -> {label: string, cards: Card[]}[]`, same return shape as the existing `groupCards(cards, tagField)`, consumable by `renderGroupedGrid`/`renderGroupSection`. Group order is fixed: `Commander` (if a commander is present) first, then `Creature, Instant, Sorcery, Enchantment, Artifact, Planeswalker, Land, Other` (only non-empty groups included) — no alphabetical sort, unlike `groupCards`.

- [ ] **Step 1: Add `groupCardsByType`, sentinel-wrapped for the Node test**

`groupCardsByType` takes no DOM/global dependencies beyond its own parameter, so — per this repo's `tests/js/` convention (see `tests/js/filter-decks.test.mjs`) — it's wrapped in sentinel comments so a plain Node script can extract and unit-test it without a browser.

In `static/app.js`, immediately after the closing `}` of `groupCards` (currently ending at line 1331, right before `function renderGroupSection`), insert:

```js
// ── groupCardsByType ──
const DECK_TYPE_GROUP_ORDER = [
  'Creature', 'Instant', 'Sorcery', 'Enchantment',
  'Artifact', 'Planeswalker', 'Land', 'Other',
];

/**
 * Groups an array of (non-Considering) deck cards by card type, with the
 * commander split into its own leading group. Fixed order, not alphabetical.
 */
function groupCardsByType(cards) {
  const buckets = { Commander: [] };
  for (const label of DECK_TYPE_GROUP_ORDER) buckets[label] = [];
  for (const card of cards) {
    if (card.is_commander) { buckets.Commander.push(card); continue; }
    const t = card.type_line || '';
    if      (t.includes('Creature'))     buckets.Creature.push(card);
    else if (t.includes('Instant'))      buckets.Instant.push(card);
    else if (t.includes('Sorcery'))      buckets.Sorcery.push(card);
    else if (t.includes('Enchantment'))  buckets.Enchantment.push(card);
    else if (t.includes('Artifact'))     buckets.Artifact.push(card);
    else if (t.includes('Planeswalker')) buckets.Planeswalker.push(card);
    else if (t.includes('Land'))         buckets.Land.push(card);
    else                                 buckets.Other.push(card);
  }
  const groups = [];
  for (const label of ['Commander', ...DECK_TYPE_GROUP_ORDER]) {
    if (buckets[label].length) groups.push({ label, cards: buckets[label] });
  }
  return groups;
}
// ── end groupCardsByType ──
```

- [ ] **Step 2: Write the automated test**

Create `tests/js/group-cards-by-type.test.mjs`:

```js
// Tests groupCardsByType by extracting it from static/app.js (a plain browser
// script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── groupCardsByType ──';
const END = '// ── end groupCardsByType ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'groupCardsByType sentinel comments not found in static/app.js');

const groupCardsByType = new Function(`${src.slice(from, to)}; return groupCardsByType;`)();

const commander  = { id: 'c', name: 'Atraxa',  is_commander: true,  type_line: 'Legendary Creature — Phyrexian Angel' };
const creature    = { id: 'r', name: 'Bear',    is_commander: false, type_line: 'Creature — Bear' };
const instant     = { id: 'i', name: 'Bolt',    is_commander: false, type_line: 'Instant' };
const artifact    = { id: 'a', name: 'Signet',  is_commander: false, type_line: 'Artifact' };
const noTypeLine  = { id: 'n', name: 'Mystery', is_commander: false, type_line: '' };

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

check(
  'commander gets its own leading group, others bucket by type',
  groupCardsByType([creature, commander, instant, artifact])
    .map(g => ({ label: g.label, ids: g.cards.map(c => c.id) })),
  [
    { label: 'Commander', ids: ['c'] },
    { label: 'Creature',  ids: ['r'] },
    { label: 'Instant',   ids: ['i'] },
    { label: 'Artifact',  ids: ['a'] },
  ]
);

check(
  'empty type groups are omitted',
  groupCardsByType([creature]).map(g => g.label),
  ['Creature']
);

check(
  'no commander in the list means no Commander group',
  groupCardsByType([creature, instant]).map(g => g.label),
  ['Creature', 'Instant']
);

check(
  'missing/blank type_line falls into Other',
  groupCardsByType([noTypeLine]).map(g => g.label),
  ['Other']
);

console.log(failed ? `\n${failed} failing` : `\nall 4 checks passing`);
process.exit(failed ? 1 : 0);
```

- [ ] **Step 3: Run the test, verify it passes**

Run: `node tests/js/group-cards-by-type.test.mjs`
Expected: four `ok` lines, then `all 4 checks passing`, exit code 0.

- [ ] **Step 4: Update the `deckState.groupBy` type comment**

In `static/app.js:1617`, change:

```js
  groupBy:        'none',   // 'none' | 'collection-tag' | 'deck-tag'
```

to:

```js
  groupBy:        'none',   // 'none' | 'type' | 'collection-tag' | 'deck-tag'
```

- [ ] **Step 5: Wire `'type'` into `renderDeckGrid`'s grouped branch**

In `static/app.js`, inside `renderDeckGrid`, replace:

```js
  if (deckState.groupBy !== 'none') {
    const tagField = deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags';
    const groups = groupCards(mainCards, tagField);
    for (const g of groups) g.cards.sort(cmp);
```

with:

```js
  if (deckState.groupBy !== 'none') {
    const groups = deckState.groupBy === 'type'
      ? groupCardsByType(mainCards)
      : groupCards(mainCards, deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags');
    for (const g of groups) g.cards.sort(cmp);
```

(The rest of the `if` block — the `consideringCards` push and `renderGroupedGrid` call — is unchanged.)

- [ ] **Step 6: Add the "Card type" option to the dropdown**

In `static/index.html:67-71`, replace:

```html
                <select id="deck-group-by" class="group-by-select">
                  <option value="none">Group: None</option>
                  <option value="collection-tag">Collection tag</option>
                  <option value="deck-tag">Deck tag</option>
                </select>
```

with:

```html
                <select id="deck-group-by" class="group-by-select">
                  <option value="none">Group: None</option>
                  <option value="type">Card type</option>
                  <option value="collection-tag">Collection tag</option>
                  <option value="deck-tag">Deck tag</option>
                </select>
```

- [ ] **Step 7: Manual verification**

Run `uvicorn app:app --reload` from the repo root, open `http://localhost:8000`, go to the Decks view, and select (or create) a deck that has a commander and at least one Creature, one Instant, and one Land.

- Grid view, set Group-by to "Card type": confirm a "Commander" group appears first with just the commander, followed by "Creature", "Instant", "Land" groups (only groups with cards render), each with correct card counts in the header.
- Confirm "Collection tag" and "Deck tag" still work exactly as before (unchanged).
- Confirm "Group: None" still shows the flat, ungrouped grid with the commander pinned first (unchanged).

- [ ] **Step 8: Commit**

```bash
git add static/app.js static/index.html tests/js/group-cards-by-type.test.mjs
git commit -m "feat: add Card type grouping option to deck Grid view"
```

---

### Task 2: Text view respects Group-by (type / tag / none)

**Files:**
- Modify: `static/app.js:1853-1910` (replace `renderDeckText` body and remove the old inline row-building)
- Modify: `static/style.css:824-857` (`.deck-text-view` layout + remove now-unused `.deck-text-section`/`.deck-text-group` rules, add `.group-body` override for the text view)

**Interfaces:**
- Consumes: `groupCardsByType` and `groupCards` from Task 1 (same as `renderDeckGrid`); `renderGroupSection`/`renderGroupedGrid` (existing, `static/app.js:1333-1367`); `sortComparator`, `applyFilters` (existing).
- Produces: `buildDeckTextRow(card: Card) -> HTMLElement`, a `.deck-text-row` with `dataset.id = card.id`, used as the `buildTileFn` passed to `renderGroupSection`/`renderGroupedGrid` for text view — later tasks (hover, keyboard nav) both read and extend this element.

**Note on behavior change (intentional, per design spec):** text view currently always groups by card type (ignoring Group-by), sorts each group alphabetically (ignoring the sort dropdown), and has no collapse control. After this task, text view uses the *same* group headers/collapse UI as Grid view, respects the Group-by dropdown (None/Card type/Collection tag/Deck tag), and sorts using the same `cmp` (current sort-dropdown selection) Grid view already uses. Group header counts become "distinct cards in group" (matching Grid view today) rather than the old "total quantity in group."

- [ ] **Step 1: Replace `renderDeckText`**

In `static/app.js`, replace the entire existing `renderDeckText` function (currently `static/app.js:1853-1910`, from `function renderDeckText() {` through its closing `}`) with:

```js
function buildDeckTextRow(card) {
  const row = document.createElement('div');
  row.className = 'deck-text-row';
  row.dataset.id = card.id;
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>`;
  row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
  return row;
}

function renderDeckText() {
  const el = document.getElementById('deck-text-view');
  el.innerHTML = '';
  const filtered = applyFilters(deckState.deckCards, deckState.filter);
  if (!filtered.length) {
    el.innerHTML = deckState.deckCards.length
      ? '<div class="deck-empty-msg">No cards match — adjust filters.</div>'
      : '<div class="deck-empty-msg">No cards yet — search to add some.</div>';
    return;
  }

  const cmp = sortComparator(deckState.filter);
  const mainCards = filtered.filter(c => !c.is_considering);
  const consideringCards = filtered.filter(c => c.is_considering);

  if (deckState.groupBy !== 'none') {
    const groups = deckState.groupBy === 'type'
      ? groupCardsByType(mainCards)
      : groupCards(mainCards, deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags');
    for (const g of groups) g.cards.sort(cmp);
    if (consideringCards.length) {
      groups.push({ label: 'Considering', cards: [...consideringCards].sort(cmp) });
    }
    renderGroupedGrid(el, groups, buildDeckTextRow, deckGroupCollapsed);
  } else {
    const sorted = [...mainCards].sort((a, b) => {
      if (a.is_commander && !b.is_commander) return -1;   // commander pinned first
      if (!a.is_commander && b.is_commander) return 1;
      return cmp(a, b);
    });
    const frag = document.createDocumentFragment();
    for (const card of sorted) frag.appendChild(buildDeckTextRow(card));
    el.appendChild(frag);
    if (consideringCards.length) {
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckTextRow,
        deckGroupCollapsed
      );
    }
  }
}
```

- [ ] **Step 2: Update text-view CSS**

In `static/style.css`, replace the entire `/* ── Deck text view ── */` block (currently lines 824-857, from `.deck-text-view {` through `.deck-text-mana { ... }`) with:

```css
/* ── Deck text view ────────────────────────────────────────────────────────── */
.deck-text-view {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

/* Group bodies in text view are a vertical row list, not the tile grid
   `.group-body` uses elsewhere — this ID-scoped override wins over the
   shared `.group-body { display: grid; ... }` rule. */
#deck-text-view .group-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.deck-text-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 4px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.1s;
}
.deck-text-row:hover { background: var(--surface2); }

.deck-text-qty  { font-size: 12px; color: var(--muted); min-width: 22px; }
.deck-text-name { font-size: 13px; font-weight: 500; flex: 1; }
.deck-text-mana { font-size: 11px; color: var(--muted); }
```

(This drops the now-unused `.deck-text-section` and `.deck-text-group` rules — nothing creates those classes anymore.)

- [ ] **Step 3: Manual verification**

With the dev server running and the same test deck from Task 1's verification:

- Switch to Text view. With Group-by "Card type": confirm a "Commander" section, then type sections, each with a header showing a card count and a collapse chevron, matching Grid view's look.
- Click a group header: confirm it collapses/expands (this worked in Grid view before; confirm it now also works in Text view).
- Set Group-by to "Collection tag" / "Deck tag": confirm Text view groups match what Grid view shows for the same setting.
- Set Group-by to "None": confirm a flat, ungrouped row list with no header, commander pinned first; if any card is in Considering, confirm it still appears in its own collapsed-by-default "Considering" section below the flat list.
- Click any row: confirm it still opens the card detail modal.

- [ ] **Step 4: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: make deck Text view respect Group-by, share Grid view's group UI"
```

---

### Task 3: Preview panel — layout, markup, and content resolution

**Files:**
- Modify: `static/index.html:79-87` (`.deck-editor-body` — add the panel div)
- Modify: `static/style.css:541-546` (`.deck-editor-body`) — add new panel rules after it
- Modify: `static/app.js:1612-1625` (`deckState` — add `focusedCardId`/`lastFocusedCardId`)
- Modify: `static/app.js:1702-1729` (`selectDeck` — reset the two new fields)
- Modify: `static/app.js:1739-1757` (`renderDeckContent` — call the new panel renderer)

**Interfaces:**
- Consumes: `deckState.deckCards`, `deckState.filter`, `applyFilters`, `sortComparator` (all existing); `esc`, `API.imageUrl` (existing).
- Produces: `resolvePreviewCard() -> Card | null` and `renderDeckPreviewPanel() -> void`, both used as-is by Task 4 (hover) and Tasks 5/6 (keyboard nav) — those tasks call `renderDeckPreviewPanel()` after changing `deckState.focusedCardId`, they do not reimplement card resolution.

- [ ] **Step 1: Add the panel container to the HTML**

In `static/index.html`, replace:

```html
            <div class="deck-editor-body">
              <div class="deck-content-col">
```

with:

```html
            <div class="deck-editor-body">
              <div id="deck-preview-panel" class="deck-preview-panel">
                <div class="deck-preview-empty">Hover or focus a card to preview it here.</div>
              </div>
              <div class="deck-content-col">
```

(Leave the rest of the `.deck-content-col` block and its closing `</div></div>` untouched.)

- [ ] **Step 2: Add panel CSS**

In `static/style.css`, immediately after the existing `.deck-editor-body { ... }` block (currently lines 541-546), insert:

```css
.deck-preview-panel {
  flex: 0 0 260px;
  overflow-y: auto;
  padding: 12px;
  border-right: 1px solid var(--border);
}

.deck-preview-empty {
  color: var(--muted);
  font-size: 13px;
  text-align: center;
  padding: 24px 8px;
}

.deck-preview-img img {
  width: 100%;
  border-radius: 10px;
  display: block;
  margin-bottom: 12px;
}
.deck-preview-img-placeholder {
  width: 100%;
  aspect-ratio: 488 / 680;
  background: var(--surface2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 12px;
}

.deck-preview-name {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 6px;
}
.deck-preview-mana { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
.deck-preview-type {
  font-size: 13px;
  color: var(--accent);
  padding-bottom: 10px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--border);
}
.deck-preview-oracle {
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-line;
}
```

- [ ] **Step 3: Add `focusedCardId`/`lastFocusedCardId` to `deckState`**

In `static/app.js`, inside the `deckState` object (currently lines 1612-1625), replace:

```js
  switchQuery:    '',        // deck-switcher palette search box
  switchFocusIdx: -1,
};
```

with:

```js
  switchQuery:    '',        // deck-switcher palette search box
  switchFocusIdx: -1,
  focusedCardId:     null,   // live keyboard/hover focus for the preview panel
  lastFocusedCardId: null,   // sticky — survives mouseleave, cleared only on deck switch
};
```

- [ ] **Step 4: Reset focus state when switching decks**

In `static/app.js`, inside `selectDeck`, replace:

```js
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
  resetDeckGroupCollapsed();              // Considering starts collapsed for every freshly loaded deck
```

with:

```js
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
  deckState.focusedCardId = null;         // reset preview-panel focus between decks
  deckState.lastFocusedCardId = null;
  resetDeckGroupCollapsed();              // Considering starts collapsed for every freshly loaded deck
```

- [ ] **Step 5: Add `resolvePreviewCard` and `renderDeckPreviewPanel`**

In `static/app.js`, immediately before `function renderDeckContent() {` (currently line 1739), insert:

```js
function resolvePreviewCard() {
  const visible = applyFilters(deckState.deckCards, deckState.filter);
  if (!visible.length) return null;
  const byId = id => visible.find(c => c.id === id);

  if (deckState.focusedCardId) {
    const c = byId(deckState.focusedCardId);
    if (c) return c;
  }
  const commander = visible.find(c => c.is_commander);
  if (commander) return commander;
  if (deckState.lastFocusedCardId) {
    const c = byId(deckState.lastFocusedCardId);
    if (c) return c;
  }
  const cmp = sortComparator(deckState.filter);
  return [...visible].sort(cmp)[0];
}

function renderDeckPreviewPanel() {
  const el = document.getElementById('deck-preview-panel');
  if (!el) return;
  const card = resolvePreviewCard();
  if (!card) {
    el.innerHTML = '<div class="deck-preview-empty">Hover or focus a card to preview it here.</div>';
    return;
  }
  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" alt="${esc(card.name)}">`
    : `<div class="deck-preview-img-placeholder">${esc(card.name)}</div>`;
  el.innerHTML = `
    <div class="deck-preview-img">${imgHtml}</div>
    <div class="deck-preview-name">${esc(card.name)}</div>
    <div class="deck-preview-mana">${esc(card.mana_cost || '—')}</div>
    <div class="deck-preview-type">${esc(card.type_line || '')}</div>
    <div class="deck-preview-oracle">${esc(card.oracle_text || '')}</div>`;
}
```

- [ ] **Step 6: Call the panel renderer from `renderDeckContent`**

In `static/app.js`, inside `renderDeckContent`, replace:

```js
  if (deckState.deckView === 'grid') {
    renderDeckGrid();
    document.getElementById('deck-grid-view').classList.remove('hidden');
    document.getElementById('deck-text-view').classList.add('hidden');
  } else {
    renderDeckText();
    document.getElementById('deck-text-view').classList.remove('hidden');
    document.getElementById('deck-grid-view').classList.add('hidden');
  }
}
```

with:

```js
  if (deckState.deckView === 'grid') {
    renderDeckGrid();
    document.getElementById('deck-grid-view').classList.remove('hidden');
    document.getElementById('deck-text-view').classList.add('hidden');
  } else {
    renderDeckText();
    document.getElementById('deck-text-view').classList.remove('hidden');
    document.getElementById('deck-grid-view').classList.add('hidden');
  }
  renderDeckPreviewPanel();
}
```

- [ ] **Step 7: Manual verification**

With the dev server running:

- Open a deck that has a commander set: confirm the left panel immediately shows the commander's image, name, mana cost, type line, and oracle text, before hovering anything.
- Open a deck with no commander: confirm the panel falls back to showing the first card in the current sort order.
- Switch Grid ↔ Text view: confirm the panel keeps showing the same card.
- Change the sort-order dropdown (e.g. name → CMC) with no commander set and nothing focused: confirm the panel's fallback card updates to match the new top-of-sort card.
- Resize the browser narrow: confirm the panel doesn't overlap or break the content column layout (it's fine if it just stays a fixed 260px column).

- [ ] **Step 8: Commit**

```bash
git add static/index.html static/style.css static/app.js
git commit -m "feat: add persistent deck card-preview panel with commander/fallback logic"
```

---

### Task 4: Hover updates the preview panel

**Files:**
- Modify: `static/app.js` — `buildDeckCardTile` (currently `static/app.js:1805-1851`) and `buildDeckTextRow` (from Task 2)
- Modify: `static/style.css` — add `.focused` styles near `.deck-card-tile` (currently ends `static/style.css:732`) and `.deck-text-row` (from Task 2)

**Interfaces:**
- Consumes: `renderDeckPreviewPanel` (Task 3).
- Produces: `setDeckFocus(cardId: string, el: HTMLElement) -> void` — the single place that updates `deckState.focusedCardId`/`lastFocusedCardId`, moves the `.focused` class, and re-renders the panel. Tasks 5 and 6 call this directly instead of duplicating its logic.

- [ ] **Step 1: Add `setDeckFocus`**

In `static/app.js`, immediately before `function buildDeckCardTile(card) {` (currently `static/app.js:1805`), insert:

```js
function setDeckFocus(cardId, el) {
  deckState.focusedCardId = cardId;
  deckState.lastFocusedCardId = cardId;
  document.querySelectorAll('.deck-card-tile.focused, .deck-text-row.focused')
    .forEach(node => node.classList.remove('focused'));
  if (el) el.classList.add('focused');
  renderDeckPreviewPanel();
}
```

- [ ] **Step 2: Hover on Grid tiles**

In `static/app.js`, inside `buildDeckCardTile`, find the block of `addEventListener` calls right before `return div;` and add one more line:

```js
  div.querySelector('[data-action="inc"]').addEventListener('click', e => { e.stopPropagation(); incDeckCard(card.id); });
  div.querySelector('[data-action="dec"]').addEventListener('click', e => { e.stopPropagation(); decDeckCard(card.id); });
  div.querySelector('.deck-cmd-btn').addEventListener('click', e => { e.stopPropagation(); toggleCommander(card.id); });
  div.querySelector('.deck-remove-btn').addEventListener('click', e => { e.stopPropagation(); removeDeckCard(card.id); });
  const consideringBtn = div.querySelector('.deck-considering-btn');
  if (consideringBtn) consideringBtn.addEventListener('click', e => { e.stopPropagation(); toggleConsidering(card.id); });
  div.addEventListener('mouseenter', () => setDeckFocus(card.id, div));
  div.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));

  return div;
```

(Only the new `mouseenter` line is added; every other line here is unchanged, shown for exact placement.)

- [ ] **Step 3: Hover on Text rows**

In `static/app.js`, inside `buildDeckTextRow` (from Task 2), replace:

```js
  row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
  return row;
```

with:

```js
  row.addEventListener('mouseenter', () => setDeckFocus(card.id, row));
  row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
  return row;
```

- [ ] **Step 4: `.focused` styles**

In `static/style.css`, immediately after `.deck-card-tile.is-considering { border-style: dashed; opacity: 0.7; }` (currently line 732), insert:

```css
.deck-card-tile.focused { outline: 2px solid var(--accent); outline-offset: 2px; }
```

In the `.deck-text-row` rules added in Task 2, add one more line right after `.deck-text-row:hover { background: var(--surface2); }`:

```css
.deck-text-row.focused { background: var(--surface2); box-shadow: inset 2px 0 0 var(--accent); }
```

- [ ] **Step 5: Manual verification**

With the dev server running and a deck open:

- Grid view: hover different tiles, confirm the preview panel updates live to each one, and the hovered tile gets a visible accent outline.
- Text view: hover different rows, confirm the same (panel updates, row gets a highlighted left edge).
- Move the mouse entirely off the deck area (e.g. onto the header): confirm the panel keeps showing the last-hovered card rather than reverting to the commander/default.
- Click a tile/row while hovering a different one: confirm the modal opens for the *clicked* card, not the hovered one.

- [ ] **Step 6: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: update deck preview panel on card hover in both views"
```

---

### Task 5: Keyboard focus navigation — List (Text) view

**Files:**
- Modify: `static/app.js` — insert new nav helpers near the end of the deck-editor rendering section (after `renderDeckText`/`buildDeckTextRow`, before `// ── Deck card mutations ──` which currently starts at `static/app.js:1912`)
- Modify: `static/app.js:1105-1186` (global `keydown` handler)

**Interfaces:**
- Consumes: `setDeckFocus` (Task 4), `deckState.focusedCardId`, `deckState.deckView`, `deckSwitchPaletteOpen`, `addPaletteOpen` (all existing/prior tasks).
- Produces: `deckNavGroups(container: HTMLElement) -> HTMLElement[][]`, `findTileIndex(groups, cardId: string) -> {g: number, i: number} | null`, `focusDeckTile(el: HTMLElement) -> void` — all three are reused as-is by Task 6's grid nav.

- [ ] **Step 1: Add shared nav helpers and the list-nav handler**

In `static/app.js`, immediately before `// ── Deck card mutations ──` (currently `static/app.js:1912`), insert:

```js
// ── Deck keyboard focus navigation ──────────────────────────────────────────

/**
 * Reads the currently-rendered groups out of the DOM: any tiles/rows that
 * are direct children of `container` (the flat ungrouped list, if present)
 * form one implicit group, followed by one group per non-collapsed
 * `.group-section`. Mirrors exactly what's visually rendered, including
 * collapsed-group and filter state, without recomputing it separately.
 */
function deckNavGroups(container) {
  if (!container) return [];
  const groups = [];
  const directTiles = [...container.children]
    .filter(node => node.matches('.deck-card-tile, .deck-text-row'));
  if (directTiles.length) groups.push(directTiles);
  for (const section of container.querySelectorAll(':scope > .group-section')) {
    if (section.querySelector('.group-header.collapsed')) continue;
    groups.push([...section.querySelectorAll('.deck-card-tile, .deck-text-row')]);
  }
  return groups;
}

function findTileIndex(groups, cardId) {
  for (let g = 0; g < groups.length; g++) {
    const i = groups[g].findIndex(el => el.dataset.id === cardId);
    if (i >= 0) return { g, i };
  }
  return null;
}

function focusDeckTile(el) {
  if (!el) return;
  setDeckFocus(el.dataset.id, el);
  el.scrollIntoView({ block: 'nearest' });
}

function handleDeckListKey(e) {
  const groups = deckNavGroups(document.getElementById('deck-text-view'));
  if (!groups.length) return;
  const pos = deckState.focusedCardId && findTileIndex(groups, deckState.focusedCardId);

  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    if (!pos) { focusDeckTile(groups[0][0]); return; }
    const delta = e.key === 'ArrowDown' ? 1 : -1;
    const nextI = Math.max(0, Math.min(pos.i + delta, groups[pos.g].length - 1));
    focusDeckTile(groups[pos.g][nextI]);
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    e.preventDefault();
    if (!pos) { focusDeckTile(groups[0][0]); return; }
    const nextG = pos.g + (e.key === 'ArrowRight' ? 1 : -1);
    if (nextG < 0 || nextG >= groups.length) return;   // clamp — no wrap past the ends
    focusDeckTile(groups[nextG][0]);
  }
}
```

- [ ] **Step 2: Wire it into the global keydown handler**

In `static/app.js`, inside the global `document.addEventListener('keydown', e => { ... })` handler, find:

```js
  // 'd' opens the deck-switcher palette
  if (e.key === 'd' || e.key === 'D') {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea');
    if (decksActive && !typingInField) {
      e.preventDefault(); openDeckSwitchPalette(); return;
    }
  }
```

and insert immediately after it (before the `// Everything below drives the Cards page` comment):

```js
  // Deck page: arrow-key focus navigation drives the preview panel.
  if (decksActive && deckState.currentDeckId &&
      !deckSwitchPaletteOpen() && !addPaletteOpen()) {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea, select');
    const isArrow = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key);
    if (!typingInField && isArrow && deckState.deckView === 'text') {
      handleDeckListKey(e);
      return;
    }
  }
```

- [ ] **Step 3: Manual verification**

With the dev server running, a deck open, Text view active, Group-by set to "Card type" (so there are multiple groups):

- Press Down repeatedly: confirm focus moves down through rows within the first group, stopping at the group's last row (doesn't spill into the next group).
- Press Up at the first row of a group: confirm it stays put (no wrap to the previous group).
- Press Right: confirm focus jumps to the first row of the next group.
- Press Left: confirm focus jumps to the first row of the previous group.
- Collapse a group by clicking its header, then arrow toward it: confirm it's skipped entirely.
- Confirm the preview panel updates on every focus change, matching the newly focused row, and the row gets the `.focused` highlight.
- Focus the "Filter cards…" search box and press arrow keys: confirm nothing happens to the deck list's focus (typing-in-field guard works).

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: add arrow-key focus navigation to deck Text view"
```

---

### Task 6: Keyboard focus navigation — Grid view

**Files:**
- Modify: `static/app.js` — insert `groupColumnCount`/`handleDeckGridKey` next to `handleDeckListKey` (Task 5)
- Modify: `static/app.js` — extend the keydown wiring added in Task 5

**Interfaces:**
- Consumes: `deckNavGroups`, `findTileIndex`, `focusDeckTile` (Task 5).

- [ ] **Step 1: Add `groupColumnCount` and `handleDeckGridKey`**

In `static/app.js`, immediately after `handleDeckListKey`'s closing `}` (added in Task 5), insert:

```js
/** Column count for one group's tiles, measured from actual layout (same
 *  technique as the Cards page's `columnCount()`), since a group's own
 *  `.group-body` can wrap to a different column count than another group's. */
function groupColumnCount(tiles) {
  if (tiles.length < 2) return 1;
  const top0 = tiles[0].getBoundingClientRect().top;
  let n = 0;
  for (const t of tiles) {
    if (t.getBoundingClientRect().top !== top0) break;
    n++;
  }
  return Math.max(1, n);
}

function handleDeckGridKey(e) {
  const groups = deckNavGroups(document.getElementById('deck-grid-view'));
  if (!groups.length) return;
  const isArrow = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key);
  if (!isArrow) return;
  e.preventDefault();

  const pos = deckState.focusedCardId && findTileIndex(groups, deckState.focusedCardId);
  if (!pos) { focusDeckTile(groups[0][0]); return; }

  const tiles = groups[pos.g];
  const cols  = groupColumnCount(tiles);
  const col   = pos.i % cols;

  if (e.key === 'ArrowRight') {
    if (pos.i + 1 < tiles.length) focusDeckTile(tiles[pos.i + 1]);
  } else if (e.key === 'ArrowLeft') {
    if (pos.i - 1 >= 0) focusDeckTile(tiles[pos.i - 1]);
  } else if (e.key === 'ArrowDown') {
    if (pos.i + cols < tiles.length) {
      focusDeckTile(tiles[pos.i + cols]);
    } else {
      const next = groups[pos.g + 1];
      if (next) focusDeckTile(next[Math.min(col, next.length - 1)]);
    }
  } else if (e.key === 'ArrowUp') {
    if (pos.i - cols >= 0) {
      focusDeckTile(tiles[pos.i - cols]);
    } else {
      const prev = groups[pos.g - 1];
      if (prev) {
        const prevCols = groupColumnCount(prev);
        const lastRowStart = prev.length - (prev.length % prevCols || prevCols);
        focusDeckTile(prev[Math.min(lastRowStart + col, prev.length - 1)]);
      }
    }
  }
}
```

- [ ] **Step 2: Extend the keydown wiring to cover Grid view**

In `static/app.js`, replace the block added in Task 5's Step 2:

```js
  // Deck page: arrow-key focus navigation drives the preview panel.
  if (decksActive && deckState.currentDeckId &&
      !deckSwitchPaletteOpen() && !addPaletteOpen()) {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea, select');
    const isArrow = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key);
    if (!typingInField && isArrow && deckState.deckView === 'text') {
      handleDeckListKey(e);
      return;
    }
  }
```

with:

```js
  // Deck page: arrow-key focus navigation drives the preview panel.
  if (decksActive && deckState.currentDeckId &&
      !deckSwitchPaletteOpen() && !addPaletteOpen()) {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea, select');
    const isArrow = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key);
    if (!typingInField && isArrow) {
      if (deckState.deckView === 'grid') handleDeckGridKey(e); else handleDeckListKey(e);
      return;
    }
  }
```

- [ ] **Step 3: Manual verification**

With the dev server running, a deck open, Grid view active, Group-by "Card type" (so multiple groups, and at least one group with more cards than fit in one row — resize the browser narrower if needed to force wrapping):

- Press an arrow key with nothing focused: confirm the first tile of the first group gets focus and the outline.
- Move Right/Left across a row: confirm normal ±1 movement, stopping at the group's actual start/end (no cross into the next group).
- Move Down past the last row of a group: confirm focus lands in the next group, in the closest matching column.
- Move Up past the first row of a group: confirm focus lands in the previous group's last row, closest matching column.
- Set Group-by to "None": confirm arrow-key movement behaves like a single continuous grid (matches the Cards page's existing model).
- Switch to Text view then back to Grid: confirm focus/preview panel state is preserved across the switch (per Task 3).

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: add spatial arrow-key focus navigation to deck Grid view"
```

---

## Self-Review Notes

- **Spec coverage:** Grouping unification (§Grouping) → Tasks 1–2. Preview panel + fallback priority (§Preview panel) → Task 3. Hover model (§Focus & hover model, mouse half) → Task 4. Keyboard model (§Focus & hover model, keyboard half) → Tasks 5–6. Layout (§Layout) → Task 3. Click-unchanged requirement verified explicitly in Task 4's manual check.
- **Type consistency:** `groupCardsByType`/`groupCards` both return `{label, cards}[]` and are used interchangeably by `renderGroupedGrid`/`renderGroupSection` across Tasks 1–2. `setDeckFocus(cardId, el)` (Task 4) is the single mutator of `deckState.focusedCardId`/`lastFocusedCardId`; Tasks 5–6 call it only through `focusDeckTile`, never touch the state fields directly. `deckNavGroups`/`findTileIndex`/`focusDeckTile` (Task 5) are reused unmodified by Task 6.
- **No placeholders:** every step has complete, runnable code; no TBD/TODO left anywhere.
