# Deck Add-Card Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the deck editor's permanently-visible 260px add-card column with a foreground palette opened by `/` or a `+ Add` button, and support adding many copies of one card via an `x20 Swamp` prefix.

**Architecture:** Frontend-only. The existing `#deck-search` input and `#deck-search-results` list are *moved* (not rebuilt) into a new fixed-position `#deck-add-palette` element that lives outside `#app` alongside the modals, so nothing clips it. Open/close is class-toggling on `.hidden`. A new pure `parseAddQuery` helper splits an `xN ` prefix off the query; the search runs on the name half and the add POSTs the quantity in one call.

**Tech Stack:** Vanilla JS (`static/app.js`), HTML (`static/index.html`), CSS (`static/style.css`). No backend changes — `POST /api/decks/{id}/cards` already accepts `quantity` and upserts additively (`app.py:588-590`), and `API.addCardToDeck(deckId, cardId, quantity = 1)` already forwards it (`static/app.js:57-62`). No pytest changes.

## Global Constraints

- **No backend changes.** Do not touch `app.py` or `tests/`.
- **Quantity syntax is `xN ` and only `xN `** — a leading `x` (case-insensitive) immediately followed by digits, then whitespace, then the name. A bare leading number is NOT a quantity: `20 swamp` searches the literal string. This intentionally differs from the importer's `20x` form (`app.py:145`).
- **Singleton is the default.** No prefix → quantity 1. A normal add never requires typing a prefix.
- **No dim backdrop.** The deck must stay visible and readable behind the palette.
- **Do not change the deck grid tile size** (`minmax(140px, 1fr)`), the decks sidebar (220px), or the deck content filter box (`#deck-content-search`). Those are out of scope.
- **Do not reuse `showNote`** (`static/app.js:774`) — it is a closure local to the modal's add-to-deck section, bound to `#modal-add-deck-note`. The palette gets its own note helper.
- Use the native ARM node for syntax checks and JS tests: `/opt/homebrew/bin/node` (NOT `/usr/local`, a dead Intel binary).

---

### Task 1: `parseAddQuery` helper, with node tests

**Files:**
- Modify: `static/app.js` — add the helper immediately above the `// ── Deck search ──` banner (currently line 1808)
- Create: `tests/js/parse-add-query.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces: `parseAddQuery(raw)` → `{ quantity: number, name: string }`. `quantity` is an integer in `[1, 999]`; `name` is the trimmed remainder. Used by Task 3.

The project has no JS test harness and `static/app.js` is a plain browser script with no exports, so the test reads the file and evals the function out of it between sentinel comments. That keeps one source of truth and needs no build step.

- [ ] **Step 1: Write the failing test**

Create `tests/js/parse-add-query.test.mjs`:

```javascript
// Tests parseAddQuery by extracting it from static/app.js (a plain browser
// script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── parseAddQuery ──';
const END = '// ── end parseAddQuery ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'parseAddQuery sentinel comments not found in static/app.js');

const parseAddQuery = new Function(`${src.slice(from, to)}; return parseAddQuery;`)();

const cases = [
  ['swamp',                { quantity: 1,   name: 'swamp' }],
  ['x20 swamp',            { quantity: 20,  name: 'swamp' }],
  ['X4 Bolt',              { quantity: 4,   name: 'Bolt' }],
  ['x1 swamp',             { quantity: 1,   name: 'swamp' }],
  ['20 swamp',             { quantity: 1,   name: '20 swamp' }],
  ['20x swamp',            { quantity: 1,   name: '20x swamp' }],
  ['x20',                  { quantity: 1,   name: 'x20' }],
  ['x20 ',                 { quantity: 1,   name: 'x20' }],
  ['x0 swamp',             { quantity: 1,   name: 'swamp' }],
  ['x9999 swamp',          { quantity: 999, name: 'swamp' }],
  ['1996 World Champion',  { quantity: 1,   name: '1996 World Champion' }],
  ['  x3   Forest  ',      { quantity: 3,   name: 'Forest' }],
  ['',                     { quantity: 1,   name: '' }],
];

let failed = 0;
for (const [input, expected] of cases) {
  try {
    assert.deepEqual(parseAddQuery(input), expected);
    console.log(`  ok  ${JSON.stringify(input)}`);
  } catch {
    failed++;
    console.error(`  FAIL ${JSON.stringify(input)} -> ${JSON.stringify(parseAddQuery(input))}, expected ${JSON.stringify(expected)}`);
  }
}
console.log(failed ? `\n${failed} failing` : `\nall ${cases.length} passing`);
process.exit(failed ? 1 : 0);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `/opt/homebrew/bin/node tests/js/parse-add-query.test.mjs`
Expected: FAIL — exits non-zero with `AssertionError [ERR_ASSERTION]: parseAddQuery sentinel comments not found in static/app.js`.

- [ ] **Step 3: Write the implementation**

In `static/app.js`, insert immediately **above** the existing banner comment
`// ── Deck search ───...` (currently line 1808):

```javascript
// ── parseAddQuery ──
/**
 * Splits a leading "xN " quantity off an add-card query.
 *   "x20 swamp" -> { quantity: 20, name: "swamp" }
 *   "swamp"     -> { quantity: 1,  name: "swamp" }
 *   "20 swamp"  -> { quantity: 1,  name: "20 swamp" }  (bare number is not a quantity)
 * The leading "x" is required so card names that start with digits
 * ("1996 World Champion") are searched literally.
 */
function parseAddQuery(raw) {
  const q = (raw || '').trim();
  const m = /^x(\d+)\s+(.+)$/i.exec(q);
  if (!m) return { quantity: 1, name: q };
  const qty = Math.min(Math.max(parseInt(m[1], 10) || 1, 1), 999);
  return { quantity: qty, name: m[2].trim() };
}
// ── end parseAddQuery ──

```

- [ ] **Step 4: Run the test to verify it passes**

Run: `/opt/homebrew/bin/node tests/js/parse-add-query.test.mjs`
Expected: PASS — every line prefixed `ok`, final line `all 13 passing`, exit 0.

- [ ] **Step 5: Syntax check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add static/app.js tests/js/parse-add-query.test.mjs
git commit -m "feat: parse an xN quantity prefix off add-card queries"
```

---

### Task 2: Move the add-card search into a foreground palette

**Files:**
- Modify: `static/index.html` — remove `.deck-search-col` (lines 86-91); add a `+ Add` button in `.deck-editor-acts` (lines 70-83); add `#deck-add-palette` after the `</div>` closing `#app` (line 104), before the card detail modal
- Modify: `static/style.css` — delete `.deck-search-col` (lines 560-567); adjust `.deck-search-input`; reveal `.dsearch-type`; add palette rules
- Modify: `static/app.js` — `closeModal` (lines 1058-1059), the `/` handler (lines 1113-1121), the Escape handler (lines 1098-1110), `selectDeck` (line 1589), the nav view-switch handler (lines 1145-1153), the `#deck-search` Escape branch (lines 2012-2017); add open/close helpers and an outside-click listener

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `openAddPalette()`, `closeAddPalette()`, `addPaletteOpen()` → boolean. Task 3 calls `addPaletteOpen()` and relies on the `#deck-add-note` and `#deck-add-qty` elements created here.

- [ ] **Step 1: Remove the search column from the HTML**

In `static/index.html`, replace the deck editor body (lines 85-99):

```html
            <div class="deck-editor-body">
              <div class="deck-search-col">
                <input id="deck-search" class="deck-search-input"
                  placeholder="Search cards to add…  (/ to focus)"
                  autocomplete="off" spellcheck="false">
                <div id="deck-search-results"></div>
              </div>
              <div class="deck-content-col">
```

with:

```html
            <div class="deck-editor-body">
              <div class="deck-content-col">
```

(The `.deck-content-col` contents and its closing tags are unchanged.)

- [ ] **Step 2: Add the `+ Add` button**

In `static/index.html`, in `.deck-editor-acts`, insert the button before the group-by select. Change:

```html
              <div class="deck-editor-acts">
                <button id="deck-rename-btn" class="action-btn">Rename</button>
                <button id="deck-delete-btn" class="action-btn action-btn-danger">Delete</button>
                <select id="deck-group-by" class="group-by-select">
```

to:

```html
              <div class="deck-editor-acts">
                <button id="deck-add-btn" class="action-btn" title="Add cards  (/)">+ Add</button>
                <button id="deck-rename-btn" class="action-btn">Rename</button>
                <button id="deck-delete-btn" class="action-btn action-btn-danger">Delete</button>
                <select id="deck-group-by" class="group-by-select">
```

- [ ] **Step 3: Add the palette element**

In `static/index.html`, immediately after the `</div>` that closes `#app` (line 104) and before the `<!-- Card detail modal -->` comment, insert:

```html
  <!-- Add-card palette (decks page) -->
  <div id="deck-add-palette" class="deck-add-palette hidden">
    <div class="deck-add-input-row">
      <input id="deck-search" class="deck-search-input"
        placeholder="Add cards…  (x20 Swamp for multiples)"
        autocomplete="off" spellcheck="false">
      <span id="deck-add-qty" class="deck-add-qty hidden"></span>
    </div>
    <div id="deck-add-note" class="deck-add-note"></div>
    <div id="deck-search-results"></div>
  </div>
```

Placing it outside `#app` guarantees the `overflow: hidden` on `.decks-layout` and `.deck-editor-body` cannot clip it.

- [ ] **Step 4: Replace the column CSS with palette CSS**

In `static/style.css`, delete the `.deck-search-col` rule (lines 560-567):

```css
.deck-search-col {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  overflow: hidden;
}
```

and replace it with:

```css
/* ── Add-card palette ──────────────────────────────────────────────────────── */
.deck-add-palette {
  position: fixed;
  top: 110px;
  left: 50%;
  transform: translateX(-50%);
  width: 560px;
  max-width: calc(100vw - 40px);
  max-height: 60vh;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.5);
  z-index: 50;   /* above .filter-panel (20), below .modal-overlay (100) */
  overflow: hidden;
}

.deck-add-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  flex-shrink: 0;
}

.deck-add-qty {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  flex-shrink: 0;
  white-space: nowrap;
}

.deck-add-note {
  padding: 0 12px 8px;
  font-size: 12px;
  color: var(--muted);
  min-height: 0;
  flex-shrink: 0;
}
.deck-add-note:empty { display: none; }
.deck-add-note.error { color: #e74c3c; }
```

- [ ] **Step 5: Adjust the input and result-list CSS for the palette**

In `static/style.css`, change `.deck-search-input` (lines 569-580) so it fills the palette row instead of carrying its own margin. Change:

```css
.deck-search-input {
  margin: 10px;
  background: var(--surface2);
```

to:

```css
.deck-search-input {
  flex: 1;
  min-width: 0;
  background: var(--surface2);
```

Then reveal the type column — the palette is 560px wide, so the type no longer has to be hidden as it was in the 260px column. Change `.dsearch-type` (lines 609-617):

```css
.dsearch-type {
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 80px;
  display: none;
}
```

to:

```css
.dsearch-type {
  font-size: 11px;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 160px;
}
```

- [ ] **Step 6: Add the open/close helpers**

In `static/app.js`, insert immediately **below** the `// ── parseAddQuery ──` block added in Task 1 (and above the `// ── Deck search ──` banner):

```javascript
// ── Add-card palette ──────────────────────────────────────────────────────────

function addPaletteOpen() {
  const p = document.getElementById('deck-add-palette');
  return !!p && !p.classList.contains('hidden');
}

function openAddPalette() {
  if (!deckState.currentDeckId) return;
  const palette = document.getElementById('deck-add-palette');
  const input   = document.getElementById('deck-search');
  if (!palette || !input) return;
  palette.classList.remove('hidden');
  input.focus();
  input.select();
}

function closeAddPalette() {
  const palette = document.getElementById('deck-add-palette');
  const input   = document.getElementById('deck-search');
  const note    = document.getElementById('deck-add-note');
  if (palette) palette.classList.add('hidden');
  if (input) { input.blur(); input.value = ''; }
  if (note) { note.textContent = ''; note.classList.remove('error'); }
  deckState.searchResults  = [];
  deckState.searchFocusIdx = -1;
  renderDeckSearchResults();
}
```

- [ ] **Step 7: Point `/` at the palette**

In `static/app.js`, in the global keydown handler, change the `/` block (lines 1112-1121):

```javascript
  // '/' focuses the relevant search input
  if (e.key === '/') {
    if (decksActive && document.activeElement !== deckSearch) {
      e.preventDefault(); deckSearch.focus(); return;
    } else if (collectionViewActive() && document.activeElement !== collectionSearch) {
```

to:

```javascript
  // '/' opens the add palette (decks) or focuses the relevant search input
  if (e.key === '/') {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea');
    if (decksActive && !typingInField) {
      e.preventDefault(); openAddPalette(); return;
    } else if (collectionViewActive() && document.activeElement !== collectionSearch) {
```

The `typingInField` guard replaces the old `activeElement !== deckSearch` check and additionally stops `/` from yanking you out of the deck content filter box mid-word.

- [ ] **Step 8: Make Escape close the palette**

In `static/app.js`, in the global keydown handler's Escape block (lines 1098-1110), add a palette check after the import-modal checks. Change:

```javascript
    if (!document.getElementById('col-import-overlay').classList.contains('hidden')) {
      closeColImportModal(); return;
    }
    searchInput.blur();
    deckSearch.blur();
    return;
```

to:

```javascript
    if (!document.getElementById('col-import-overlay').classList.contains('hidden')) {
      closeColImportModal(); return;
    }
    if (addPaletteOpen()) { closeAddPalette(); return; }
    searchInput.blur();
    deckSearch.blur();
    return;
```

Then change the `#deck-search` input's own Escape branch (lines 2012-2017):

```javascript
  } else if (e.key === 'Escape') {
    e.preventDefault();
    document.getElementById('deck-search').blur();
    deckState.searchResults = [];
    renderDeckSearchResults();
  }
```

to:

```javascript
  } else if (e.key === 'Escape') {
    e.preventDefault();
    closeAddPalette();
  }
```

- [ ] **Step 9: Wire the `+ Add` button and outside-click close**

In `static/app.js`, immediately after the existing `#deck-search` keydown listener block (ends line 2018), add:

```javascript
document.getElementById('deck-add-btn').addEventListener('click', openAddPalette);

document.addEventListener('mousedown', e => {
  if (!addPaletteOpen()) return;
  const palette = document.getElementById('deck-add-palette');
  const btn     = document.getElementById('deck-add-btn');
  if (palette && palette.contains(e.target)) return;
  if (btn && btn.contains(e.target)) return;   // let the opener's own click through
  closeAddPalette();
});
```

- [ ] **Step 10: Close the palette on deck switch and view switch**

In `static/app.js`, in `selectDeck` (line 1589), add the close alongside the existing resets. Change:

```javascript
async function selectDeck(id) {
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
```

to:

```javascript
async function selectDeck(id) {
  closeAddPalette();                      // never carry the palette between decks
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
```

Then in the nav handler (lines 1145-1153), close it when leaving the decks view — the palette is `position: fixed` and would otherwise float over the Cards/Collection pages. Change:

```javascript
    document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
    btn.classList.add('active');
    if (btn.dataset.view === 'decks')      loadDeckList();
```

to:

```javascript
    document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
    btn.classList.add('active');
    if (btn.dataset.view !== 'decks')      closeAddPalette();
    if (btn.dataset.view === 'decks')      loadDeckList();
```

- [ ] **Step 11: Stop `closeModal` focusing a hidden input**

In `static/app.js`, in `closeModal` (lines 1058-1059), only restore focus when the palette is actually open. Change:

```javascript
  if (document.getElementById('view-decks').classList.contains('active')) {
    document.getElementById('deck-search').focus();
  } else if (collectionViewActive()) {
```

to:

```javascript
  if (document.getElementById('view-decks').classList.contains('active')) {
    if (addPaletteOpen()) document.getElementById('deck-search').focus();
  } else if (collectionViewActive()) {
```

- [ ] **Step 12: Guard `renderDeckSearchResults` against a missing container**

`closeAddPalette` calls `renderDeckSearchResults`, and the global Escape handler can fire before the deck view has ever rendered. In `static/app.js`, change the opening of `renderDeckSearchResults` (line 1827-1829):

```javascript
function renderDeckSearchResults() {
  const el = document.getElementById('deck-search-results');
  el.innerHTML = '';
```

to:

```javascript
function renderDeckSearchResults() {
  const el = document.getElementById('deck-search-results');
  if (!el) return;
  el.innerHTML = '';
```

- [ ] **Step 13: Syntax check and re-run the Task 1 test**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit 0.

Run: `/opt/homebrew/bin/node tests/js/parse-add-query.test.mjs`
Expected: `all 13 passing`, exit 0 (unchanged by this task — confirms the sentinel block survived the edits).

- [ ] **Step 14: Manual verification (record result in report)**

Start the server (`/opt/homebrew/bin/python3 -m uvicorn app:app --reload` or `uvicorn app:app --reload`) and open a deck:

- The 260px search column is gone; the card grid spans the full width and fits more columns than before.
- `/` opens the palette centered near the top; the deck is still visible behind it (no dimming).
- The `+ Add` button opens the same palette.
- Typing searches as before; `↑↓` move the highlight, `↑` past the top returns to the input.
- `Escape` closes it. Clicking anywhere outside closes it. Clicking `+ Add` while it is open does not close-then-reopen into a broken state.
- Switching decks closes it; switching to Cards/Collection closes it (it must not float over those pages).
- Opening and closing a card modal from the decks view does not leave focus stranded.

If you cannot run a browser, state that explicitly and confirm by re-reading that `#deck-search` and `#deck-search-results` exist exactly once in `index.html` (inside the palette), that `#deck-add-palette` sits outside `#app`, and that every `closeAddPalette`/`openAddPalette` call site resolves to the helpers added in Step 6.

- [ ] **Step 15: Commit**

```bash
git add static/index.html static/app.js static/style.css
git commit -m "feat: move deck add-card search into a foreground palette"
```

---

### Task 3: Quantity-aware adds, in-deck counts, and post-add reset

**Files:**
- Modify: `static/app.js` — `onDeckSearchInput` (lines 1812-1816), `renderDeckSearchResults` (lines 1827-1843), `addCardToDeck` (lines 1845-1861), the `#deck-search` Enter/`+` branch (lines 2008-2011), the `#deck-search` input listener (line 1996); add `showAddNote`, `updateQtyBadge`, `resetPaletteQuery`, `addFromPalette`
- Modify: `static/style.css` — add `.dsearch-indeck`

**Interfaces:**
- Consumes: `parseAddQuery(raw)` → `{ quantity, name }` (Task 1); `addPaletteOpen()`, and the `#deck-add-note` / `#deck-add-qty` elements (Task 2).
- Produces: `addCardToDeck(cardId, cardData, quantity = 1)` → `Promise<boolean>` (true on success); `addFromPalette(card)`; `showAddNote(msg, isError)`; `updateQtyBadge()`; `resetPaletteQuery()`.

- [ ] **Step 1: Search on the name half of the query**

In `static/app.js`, change `onDeckSearchInput` (lines 1812-1816):

```javascript
function onDeckSearchInput(e) {
  const q = e.target.value.trim();
  clearTimeout(deckSearchTimer);
  deckSearchTimer = setTimeout(() => runDeckSearch(q), 250);
}
```

to:

```javascript
function onDeckSearchInput(e) {
  const { name } = parseAddQuery(e.target.value);
  updateQtyBadge();
  clearTimeout(deckSearchTimer);
  deckSearchTimer = setTimeout(() => runDeckSearch(name), 250);
}
```

`runDeckSearch` already clears results when handed an empty string (line 1819), which covers a query that is only a prefix.

- [ ] **Step 2: Add the note, badge, and reset helpers**

In `static/app.js`, add immediately below the `closeAddPalette` function from Task 2 Step 6:

```javascript
let addNoteTimer = null;

function showAddNote(msg, isError) {
  const note = document.getElementById('deck-add-note');
  if (!note) return;
  note.textContent = msg;
  note.classList.toggle('error', !!isError);
  if (addNoteTimer) clearTimeout(addNoteTimer);
  addNoteTimer = setTimeout(() => {
    note.textContent = '';
    note.classList.remove('error');
  }, 2000);
}

function updateQtyBadge() {
  const badge = document.getElementById('deck-add-qty');
  const input = document.getElementById('deck-search');
  if (!badge || !input) return;
  const { quantity } = parseAddQuery(input.value);
  badge.textContent = quantity > 1 ? `×${quantity}` : '';
  badge.classList.toggle('hidden', quantity <= 1);
}

/** Clear the query after an add, leaving the palette open for the next card. */
function resetPaletteQuery() {
  const input = document.getElementById('deck-search');
  if (input) { input.value = ''; input.focus(); }
  deckState.searchResults  = [];
  deckState.searchFocusIdx = -1;
  renderDeckSearchResults();
  updateQtyBadge();
}
```

Then add `updateQtyBadge();` to `closeAddPalette` (from Task 2 Step 6), immediately after the `renderDeckSearchResults();` line, so a stale `×20` badge cannot survive a close.

- [ ] **Step 3: Show the current deck quantity on result rows**

In `static/app.js`, change `renderDeckSearchResults` (the loop body, lines 1830-1842):

```javascript
  for (let i = 0; i < deckState.searchResults.length; i++) {
    const card = deckState.searchResults[i];
    const row = document.createElement('div');
    row.className = 'deck-search-row';
    row.dataset.idx = i;
    row.innerHTML = `
      <span class="dsearch-name">${esc(card.name)}</span>
      <span class="dsearch-type">${esc(card.type_line || '')}</span>
      <button class="dsearch-add-btn" title="Add to deck">+</button>`;
    row.querySelector('.dsearch-add-btn').addEventListener('click', e => { e.stopPropagation(); addCardToDeck(card.id, card); });
    row.addEventListener('click', () => addCardToDeck(card.id, card));
    el.appendChild(row);
  }
```

to:

```javascript
  for (let i = 0; i < deckState.searchResults.length; i++) {
    const card = deckState.searchResults[i];
    const inDeck = deckState.deckCards.find(c => c.id === card.id);
    const row = document.createElement('div');
    row.className = 'deck-search-row';
    row.dataset.idx = i;
    row.innerHTML = `
      <span class="dsearch-name">${esc(card.name)}</span>
      <span class="dsearch-type">${esc(card.type_line || '')}</span>
      <span class="dsearch-indeck">${inDeck ? `in deck: ${inDeck.quantity}` : ''}</span>
      <button class="dsearch-add-btn" title="Add to deck">+</button>`;
    row.querySelector('.dsearch-add-btn').addEventListener('click', e => { e.stopPropagation(); addFromPalette(card); });
    row.addEventListener('click', () => addFromPalette(card));
    el.appendChild(row);
  }
```

Cards not in the deck render an empty span, not `in deck: 0`.

- [ ] **Step 4: Add the `.dsearch-indeck` style**

In `static/style.css`, add immediately after the `.dsearch-type` rule (edited in Task 2 Step 5):

```css
.dsearch-indeck {
  font-size: 11px;
  color: var(--accent);
  white-space: nowrap;
  flex-shrink: 0;
}
```

- [ ] **Step 5: Make `addCardToDeck` quantity-aware and single-path**

In `static/app.js`, replace `addCardToDeck` (lines 1845-1861) entirely:

```javascript
async function addCardToDeck(cardId, cardData) {
  if (!deckState.currentDeckId) return;
  const existing = deckState.deckCards.find(c => c.id === cardId);
  if (existing) {
    incDeckCard(cardId);
  } else {
    if (deckState.addingCards.has(cardId)) return;
    deckState.addingCards.add(cardId);
    try {
      const res = await API.addCardToDeck(deckState.currentDeckId, cardId);
      deckState.deckCards.push({ ...cardData, quantity: res.quantity, is_commander: false, collection_tags: [], deck_tags: [] });
      syncDeckCount();
      renderDeckContent();
    } catch (e) { console.error(e); }
    finally { deckState.addingCards.delete(cardId); }
  }
}
```

with:

```javascript
/**
 * Adds `quantity` copies of a card to the current deck in one request.
 * The backend upserts additively, so this works for new and existing cards
 * alike. Returns true on success.
 */
async function addCardToDeck(cardId, cardData, quantity = 1) {
  if (!deckState.currentDeckId) return false;
  if (deckState.addingCards.has(cardId)) return false;
  deckState.addingCards.add(cardId);
  try {
    const res = await API.addCardToDeck(deckState.currentDeckId, cardId, quantity);
    const existing = deckState.deckCards.find(c => c.id === cardId);
    if (existing) {
      existing.quantity = res.quantity;
    } else {
      deckState.deckCards.push({ ...cardData, quantity: res.quantity, is_commander: false, collection_tags: [], deck_tags: [] });
    }
    syncDeckCount();
    renderDeckContent();
    return true;
  } catch (e) {
    console.error(e);
    return false;
  } finally {
    deckState.addingCards.delete(cardId);
  }
}
```

`incDeckCard` stays as-is — the grid tile `+` button still uses it.

- [ ] **Step 6: Add the palette add wrapper**

In `static/app.js`, add immediately below the new `addCardToDeck`:

```javascript
/** Add from the palette: reads the quantity prefix, notes the result, resets. */
async function addFromPalette(card) {
  const input = document.getElementById('deck-search');
  const { quantity } = parseAddQuery(input ? input.value : '');
  const ok = await addCardToDeck(card.id, card, quantity);
  if (!ok) { showAddNote(`Could not add ${card.name}`, true); return; }
  showAddNote(quantity > 1 ? `Added ${quantity}× ${card.name}` : `Added ${card.name}`);
  resetPaletteQuery();
}
```

- [ ] **Step 7: Route the keyboard add through the wrapper**

In `static/app.js`, change the `#deck-search` keydown Enter/`+` branch (lines 2008-2011):

```javascript
  } else if ((e.key === 'Enter' || e.key === '+') && deckState.searchFocusIdx >= 0) {
    e.preventDefault();
    const card = results[deckState.searchFocusIdx];
    if (card) addCardToDeck(card.id, card);
```

to:

```javascript
  } else if ((e.key === 'Enter' || e.key === '+') && deckState.searchFocusIdx >= 0) {
    e.preventDefault();
    const card = results[deckState.searchFocusIdx];
    if (card) addFromPalette(card);
```

- [ ] **Step 8: Syntax check and run the JS test**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit 0.

Run: `/opt/homebrew/bin/node tests/js/parse-add-query.test.mjs`
Expected: `all 13 passing`, exit 0.

- [ ] **Step 9: Confirm the backend is untouched**

Run: `git status --porcelain app.py tests/test_card_decks.py`
Expected: no output (neither file modified).

Run: `/opt/homebrew/bin/python3 -m pytest tests/ -q`
Expected: all tests pass, same count as before the branch.

- [ ] **Step 10: Manual verification (record result in report)**

With the server running and a deck open:

- `/`, type a card name, `Enter` → the card is added, the query clears, the palette stays open and focused, and a note reads `Added <name>`.
- Type `x20 swamp` → a `×20` badge appears next to the input, Swamp results appear while typing, `Enter` adds 20 in a single request (check the server log for one `POST /api/decks/.../cards`), and the note reads `Added 20× Swamp`.
- Type `20 swamp` → **no** badge; it searches the literal string.
- Add a card that is already in the deck → its quantity increases by the parsed amount rather than resetting to it; the grid tile updates immediately.
- Result rows for cards already in the deck show `in deck: N`, and N ticks up after adding.
- The deck count in the sidebar tracks the added copies.

If you cannot run a browser, state that explicitly and confirm by re-reading that `addFromPalette` is the only caller of `addCardToDeck` from the palette, that `addCardToDeck` returns a boolean on every path, and that `updateQtyBadge` is called from the input handler, `resetPaletteQuery`, and `closeAddPalette`.

- [ ] **Step 11: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: xN bulk adds and in-deck counts in the add palette"
```

---

## Self-Review Notes

- **Spec coverage:** §1 remove column + full-width grid → Task 2 Steps 1, 4 ✓. §2 palette element, fixed position, no backdrop, 60vh scroll, z-index 50 → Task 2 Steps 3, 4 ✓; `openAddPalette`/`closeAddPalette` incl. the no-deck guard → Step 6 ✓. §3 `+ Add` button → Step 2, 9 ✓; `/` → Step 7 ✓; Escape (both handlers, precedence preserved) → Step 8 ✓; outside click excluding the opener → Step 9 ✓; `closeModal` conditional refocus → Step 11 ✓. §4 `parseAddQuery` with leading-`x` rule, case-insensitivity, 0→1, 999 clamp → Task 1 ✓; search on the name half → Task 3 Step 1 ✓; empty-name clears → Task 3 Step 1 note ✓; `×N` badge → Task 3 Step 2 ✓. §5 in-deck counts → Task 3 Steps 3, 4 ✓; single-POST add path with in-flight guard → Step 5 ✓. §6 post-add clear/refocus/note, singular vs plural → Steps 2, 6 ✓. Keyboard contract table → Task 2 Steps 7, 8 + Task 3 Step 7 ✓. Error handling: no-deck guard ✓, failed POST surfaces an error note (Step 6) ✓, duplicate-POST guard ✓, null-guarded element lookups throughout ✓.
- **Beyond the spec, justified:** Task 2 Step 10 (close on view switch) and Step 12 (null-guard `renderDeckSearchResults`) — both are required by the move to a fixed-position element callable from the global Escape handler; without them the palette floats over other pages or throws. Task 2 Step 7's `typingInField` guard replaces an equivalent existing guard and additionally fixes `/` stealing focus from the deck content filter.
- **Placeholders:** none — every code step shows complete before/after text.
- **Type consistency:** `parseAddQuery` returns `{ quantity, name }` in Task 1 and is destructured as such in Task 3 Steps 1, 2, 6 ✓. `addCardToDeck(cardId, cardData, quantity = 1)` returns `Promise<boolean>`; `addFromPalette` is its only palette caller and checks the boolean ✓. Element ids `deck-add-palette`, `deck-add-btn`, `deck-add-qty`, `deck-add-note`, `deck-search`, `deck-search-results` are identical across HTML (Task 2 Steps 2, 3), CSS (Steps 4, 5), and every JS lookup ✓. `incDeckCard` is untouched and still used by the grid tile ✓.
