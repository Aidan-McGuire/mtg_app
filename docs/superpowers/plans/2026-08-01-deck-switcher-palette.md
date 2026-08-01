# Deck-Switcher Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the always-visible deck-list sidebar on the Decks page with an on-demand searchable palette, freeing the sidebar's width/height for the deck editor and scaling to dozens of decks via search instead of a scrolling list.

**Architecture:** Remove `.decks-sidebar` from `static/index.html`; `.deck-main` takes the full width. A new floating overlay (`#deck-switch-palette`), structurally and visually a twin of the existing add-card palette (`#deck-add-palette`), lists/filters decks on demand. It opens via a header button or the `d` key, closes on select/click-outside/Escape, and auto-opens whenever the Decks page has no deck selected.

**Tech Stack:** Vanilla JS (`static/app.js`), plain CSS (`static/style.css`), no build step. Frontend unit tests are plain Node scripts under `tests/js/` that extract a sentinel-delimited function out of `app.js` via string slicing + `new Function(...)` (see `tests/js/parse-add-query.test.mjs` for the existing pattern) — there is no DOM/jsdom test harness in this repo, so DOM-wiring changes are verified manually via the running dev server.

## Global Constraints

- No backend/API changes — this is frontend-only.
- Follow the existing add-card palette's visual/interaction pattern exactly (fixed floating panel, `hidden` class toggle, arrow-key + Enter navigation, Escape closes, click-outside closes) rather than inventing a new pattern.
- Reuse existing CSS classes (`.action-btn`, `.deck-list-item`, `.deck-list-name`, `.deck-list-count`, `.deck-search-input`) instead of duplicating rules.
- Keep `esc()` (HTML-escaping helper) usage on any deck name rendered into `innerHTML`, matching existing code.
- No automated DOM tests exist for this app; only pure-logic helpers get automated tests. DOM/interaction changes are verified by running the dev server (`uvicorn app:app --reload`) and checking with curl (structural checks) plus a manual pass in the browser (interaction checks).

---

## File Structure

- **Modify `static/app.js`**: add a pure `filterDecks(decks, query)` helper (sentinel-wrapped for testing); replace the sidebar's `renderDeckList()`/`loadDeckList()` machinery with palette open/close/render/select functions; add keyboard wiring (`d` shortcut, arrow/Enter/Escape inside the palette, click-outside-to-close); wire the palette into the Decks-page auto-open flow (nav click, deck delete).
- **Modify `static/index.html`**: remove `<aside class="decks-sidebar">`; add a `#deck-switch-btn` control next to the deck name; add the `#deck-switch-palette` overlay markup near the existing `#deck-add-palette`; update the `#deck-empty` fallback text.
- **Modify `static/style.css`**: remove `.decks-sidebar*`/`#deck-list` rules; add `.deck-editor-title`, `.deck-switch-actions`, `#deck-switch-results`, `.deck-list-item.focused` rules; extend the `.deck-add-palette` positioning rule to also apply to `.deck-switch-palette`.
- **Create `tests/js/filter-decks.test.mjs`**: unit test for `filterDecks`, mirroring `tests/js/parse-add-query.test.mjs`.

---

### Task 1: `filterDecks` pure helper

**Files:**
- Modify: `static/app.js` (insert before the `// ── Deck list ───────` comment, currently around line 1567)
- Create: `tests/js/filter-decks.test.mjs`

**Interfaces:**
- Produces: `filterDecks(decks: {id, name, ...}[], query: string) => same-shaped array` — case-insensitive substring match on `name`; empty/whitespace-only query returns `decks` unchanged (same elements, no reordering).

- [ ] **Step 1: Add a stub implementation and the test file**

In `static/app.js`, insert this immediately before the existing `// ── Deck list ─────...` comment:

```js
// ── filterDecks ──
function filterDecks(decks, query) {
  return [];
}
// ── end filterDecks ──
```

Create `tests/js/filter-decks.test.mjs`:

```js
// Tests filterDecks by extracting it from static/app.js (a plain browser
// script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── filterDecks ──';
const END = '// ── end filterDecks ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'filterDecks sentinel comments not found in static/app.js');

const filterDecks = new Function(`${src.slice(from, to)}; return filterDecks;`)();

const decks = [
  { id: 1, name: 'Atraxa, Praetors’ Voice' },
  { id: 2, name: 'Lightning Aggro' },
  { id: 3, name: 'atraxa reanimator' },
  { id: 4, name: 'Mono Black Control' },
];

const cases = [
  ['atraxa', [1, 3]],
  ['ATRAXA', [1, 3]],
  ['aggro',  [2]],
  ['',       [1, 2, 3, 4]],
  ['   ',    [1, 2, 3, 4]],
  ['xyz',    []],
];

let failed = 0;
for (const [query, expectedIds] of cases) {
  const result = filterDecks(decks, query).map(d => d.id);
  try {
    assert.deepEqual(result, expectedIds);
    console.log(`  ok  ${JSON.stringify(query)}`);
  } catch {
    failed++;
    console.error(`  FAIL ${JSON.stringify(query)} -> ${JSON.stringify(result)}, expected ${JSON.stringify(expectedIds)}`);
  }
}
console.log(failed ? `\n${failed} failing` : `\nall ${cases.length} passing`);
process.exit(failed ? 1 : 0);
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `node tests/js/filter-decks.test.mjs`
Expected: several `FAIL` lines (e.g. the `'atraxa'` and `''` cases fail against the stub's `[]`), exit code 1.

- [ ] **Step 3: Implement `filterDecks` for real**

Replace the stub body in `static/app.js`:

```js
// ── filterDecks ──
function filterDecks(decks, query) {
  const q = query.trim().toLowerCase();
  if (!q) return decks;
  return decks.filter(d => d.name.toLowerCase().includes(q));
}
// ── end filterDecks ──
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `node tests/js/filter-decks.test.mjs`
Expected: `  ok` for all 6 cases, `all 6 passing`, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add static/app.js tests/js/filter-decks.test.mjs
git commit -m "feat: add filterDecks helper for the upcoming deck-switcher palette"
```

---

### Task 2: Replace the sidebar with the switch-palette (structural swap)

**Files:**
- Modify: `static/index.html:53-98` (decks view markup), `static/index.html:101-111` (palette section)
- Modify: `static/style.css:428-502` (sidebar rules → removed/replaced), `static/style.css:529-544` (`.deck-editor-hdr`/`.deck-editor-name`), `static/style.css:561-577` (`.deck-add-palette`)
- Modify: `static/app.js:1554-1598` (`deckState` + `loadDeckList`/`renderDeckList`), plus every call site of `renderDeckList()` and the `new-deck-btn`/`import-deck-btn` handlers

**Interfaces:**
- Consumes: `filterDecks(decks, query)` from Task 1; existing `selectDeck(id)`, `esc(str)`, `API.listDecks()`, `API.createDeck(name)`, `openImportModal()`.
- Produces: `deckSwitchPaletteOpen()`, `openDeckSwitchPalette()`, `closeDeckSwitchPalette()`, `renderDeckSwitchResults()` — used by Tasks 3 and 4.

- [ ] **Step 1: Remove the sidebar and add the switch-palette markup in `static/index.html`**

Replace (the whole `#view-decks` opening through the `deck-editor-hdr` opening):

```html
    <div id="view-decks" class="view">
      <div class="decks-layout">
        <aside class="decks-sidebar">
          <div class="decks-sidebar-hdr">
            <span class="decks-label">Decks</span>
            <div class="decks-sidebar-btns">
              <button id="import-deck-btn" class="action-btn">↑ Import</button>
              <button id="new-deck-btn" class="action-btn">+ New</button>
            </div>
          </div>
          <div id="deck-list"></div>
        </aside>
        <div class="deck-main">
          <div id="deck-empty" class="deck-empty">Select a deck or create a new one</div>
          <div id="deck-editor" class="deck-editor hidden">
            <div class="deck-editor-hdr">
              <span id="deck-editor-name" class="deck-editor-name"></span>
              <div class="deck-editor-acts">
```

with:

```html
    <div id="view-decks" class="view">
      <div class="decks-layout">
        <div class="deck-main">
          <div id="deck-empty" class="deck-empty">No deck selected — press <kbd>d</kbd></div>
          <div id="deck-editor" class="deck-editor hidden">
            <div class="deck-editor-hdr">
              <div class="deck-editor-title">
                <span id="deck-editor-name" class="deck-editor-name"></span>
                <button id="deck-switch-btn" class="action-btn" title="Switch deck  (d)">⇅ Switch</button>
              </div>
              <div class="deck-editor-acts">
```

(The rest of `deck-editor-acts` and everything below it through the end of `#view-decks` is unchanged — only the `<aside>` block was deleted and the header gained one wrapper div.)

Then, in the "Add-card palette (decks page)" section, add a new block right after the existing `#deck-add-palette` div closes:

```html
  <!-- Deck-switch palette (decks page) -->
  <div id="deck-switch-palette" class="deck-switch-palette hidden">
    <div class="deck-switch-actions">
      <button id="deck-switch-new-btn" class="action-btn">+ New</button>
      <button id="deck-switch-import-btn" class="action-btn">↑ Import</button>
    </div>
    <input id="deck-switch-search" class="deck-search-input"
      placeholder="Switch deck…" autocomplete="off" spellcheck="false">
    <div id="deck-switch-results"></div>
  </div>
```

- [ ] **Step 2: Update `static/style.css`**

Remove the sidebar-specific rules: `.decks-sidebar`, `.decks-sidebar-hdr`, `.decks-label`, `.decks-sidebar-btns`, and the `#deck-list` rule. Keep `.deck-list-empty`, `.deck-list-item`, `.deck-list-item:hover`, `.deck-list-item.active`, `.deck-list-name`, `.deck-list-count` — they're reused by the new palette.

Add a `.focused` variant next to `.deck-list-item.active`:

```css
.deck-list-item:hover  { background: var(--surface2); }
.deck-list-item.active { background: var(--surface2); border-left: 2px solid var(--accent); padding-left: 8px; }
.deck-list-item.focused { background: var(--surface2); }
```

Add `.deck-editor-title` next to `.deck-editor-name`:

```css
.deck-editor-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
```

Extend the add-card palette's positioning rule to cover both panels:

```css
.deck-add-palette, .deck-switch-palette {
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
```

Add, near `#deck-search-results`:

```css
.deck-switch-actions {
  display: flex;
  gap: 8px;
  padding: 10px 10px 0;
  flex-shrink: 0;
}

#deck-switch-results {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}
```

- [ ] **Step 3: Replace the sidebar state/render code in `static/app.js`**

Add two fields to `deckState` (currently at line ~1554):

```js
const deckState = {
  decks:          [],
  currentDeckId:  null,
  deckCards:      [],
  deckView:       'grid',
  groupBy:        'none',   // 'none' | 'collection-tag' | 'deck-tag'
  filter:         makeFilterModel(),
  query:          '',       // deck content search box (name/text/type)
  searchResults:  [],
  searchFocusIdx: -1,
  addingCards:    new Set(), // card IDs with an in-flight add request
  switchQuery:    '',        // deck-switcher palette search box
  switchFocusIdx: -1,
};
```

Replace `loadDeckList()` and `renderDeckList()`:

```js
async function loadDeckList() {
  try {
    deckState.decks = await API.listDecks();
    renderDeckSwitchResults();
  } catch (e) {
    console.error(e);
  }
}

function deckSwitchPaletteOpen() {
  const p = document.getElementById('deck-switch-palette');
  return !!p && !p.classList.contains('hidden');
}

function openDeckSwitchPalette() {
  closeAddPalette();
  const palette = document.getElementById('deck-switch-palette');
  const input   = document.getElementById('deck-switch-search');
  if (!palette || !input) return;
  palette.classList.remove('hidden');
  input.value = deckState.switchQuery;
  input.focus();
  input.select();
  renderDeckSwitchResults();
}

function closeDeckSwitchPalette() {
  const palette = document.getElementById('deck-switch-palette');
  const input   = document.getElementById('deck-switch-search');
  if (palette) palette.classList.add('hidden');
  if (input) { input.blur(); input.value = ''; }
  deckState.switchQuery = '';
  deckState.switchFocusIdx = -1;
}

function renderDeckSwitchResults() {
  const el = document.getElementById('deck-switch-results');
  if (!el) return;
  el.innerHTML = '';
  if (!deckState.decks.length) {
    el.innerHTML = '<div class="deck-list-empty">No decks yet.</div>';
    return;
  }
  const matches = filterDecks(deckState.decks, deckState.switchQuery);
  if (!matches.length) {
    el.innerHTML = '<div class="deck-list-empty">No matches.</div>';
    return;
  }
  for (let i = 0; i < matches.length; i++) {
    const deck = matches[i];
    const item = document.createElement('div');
    item.className = 'deck-list-item'
      + (deck.id === deckState.currentDeckId ? ' active' : '')
      + (i === deckState.switchFocusIdx ? ' focused' : '');
    item.dataset.id = deck.id;
    item.innerHTML = `
      <span class="deck-list-name">${esc(deck.name)}</span>
      <span class="deck-list-count">${deck.card_count}</span>`;
    item.addEventListener('click', () => { selectDeck(deck.id); closeDeckSwitchPalette(); });
    el.appendChild(item);
  }
  const focusedEl = el.querySelector('.deck-list-item.focused');
  if (focusedEl) focusedEl.scrollIntoView({ block: 'nearest' });
}
```

Rename every remaining call site of `renderDeckList()` to `renderDeckSwitchResults()`. Search for `renderDeckList()` in `static/app.js` after this edit — four call sites remain: inside `selectDeck()`, inside the `deck-rename-btn` click handler, inside `syncDeckCount()`, and inside the `import-submit` click handler. (A fifth call site, inside `deck-delete-btn`, is handled separately in Task 4 Step 2.) Change each of these four to `renderDeckSwitchResults();`.

- [ ] **Step 4: Relocate the New/Import button handlers**

Replace:

```js
document.getElementById('new-deck-btn').addEventListener('click', async () => {
  const name = prompt('Deck name:');
  if (!name || !name.trim()) return;
  try {
    const deck = await API.createDeck(name.trim());
    deckState.decks.push({ ...deck, card_count: 0 });
    deckState.decks.sort((a, b) => a.name.localeCompare(b.name));
    renderDeckList();
    selectDeck(deck.id);
  } catch (e) { alert('Failed to create deck.'); }
});
```

with:

```js
document.getElementById('deck-switch-new-btn').addEventListener('click', async () => {
  const name = prompt('Deck name:');
  if (!name || !name.trim()) return;
  try {
    const deck = await API.createDeck(name.trim());
    deckState.decks.push({ ...deck, card_count: 0 });
    deckState.decks.sort((a, b) => a.name.localeCompare(b.name));
    selectDeck(deck.id);
    closeDeckSwitchPalette();
  } catch (e) { alert('Failed to create deck.'); }
});
```

Replace:

```js
document.getElementById('import-deck-btn').addEventListener('click', openImportModal);
```

with:

```js
document.getElementById('deck-switch-import-btn').addEventListener('click', () => {
  closeDeckSwitchPalette();
  openImportModal();
});
```

Add a click handler to open the palette from the header button, near the other deck-controls wiring:

```js
document.getElementById('deck-switch-btn').addEventListener('click', openDeckSwitchPalette);
```

Add the `input` listener that filters as you type, near the other search-input wiring:

```js
document.getElementById('deck-switch-search').addEventListener('input', e => {
  deckState.switchQuery = e.target.value;
  deckState.switchFocusIdx = -1;
  renderDeckSwitchResults();
});
```

- [ ] **Step 5: Manual verification**

Start the dev server if it isn't already running: `uvicorn app:app --reload` (from the project root).

```bash
curl -s http://localhost:8000/ | grep -c "decks-sidebar"   # expect 0
curl -s http://localhost:8000/ | grep -c "deck-switch-palette"  # expect 1 (the div open tag)
curl -s http://localhost:8000/app.js | grep -c "renderDeckList"  # expect 0 — fully renamed
node tests/js/filter-decks.test.mjs   # still passing — untouched by this task
```

Then, in a browser, open the app, go to the Decks page, click "⇅ Switch" — the palette should open, listing all decks with counts; typing should filter the list live; clicking a deck should select it and close the palette; clicking "+ New" / "↑ Import" inside the palette should behave as the old sidebar buttons did.

- [ ] **Step 6: Commit**

```bash
git add static/index.html static/style.css static/app.js
git commit -m "feat: replace decks sidebar with an on-demand switch palette"
```

---

### Task 3: Keyboard layer (shortcut, arrow nav, Escape, click-outside)

**Files:**
- Modify: `static/app.js` — global `keydown` listener (currently `static/app.js:1072-1143`), and the deck-controls wiring section added in Task 2.

**Interfaces:**
- Consumes: `deckSwitchPaletteOpen()`, `openDeckSwitchPalette()`, `closeDeckSwitchPalette()`, `renderDeckSwitchResults()`, `filterDecks()`, `deckState.switchQuery`, `deckState.switchFocusIdx` from Task 2.

- [ ] **Step 1: Add the `d` shortcut**

In the global `keydown` listener, immediately after the existing `'/'` branch (which ends with the closing `}` right before the "Everything below drives the Cards page" comment), add:

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

- [ ] **Step 2: Add Escape handling**

In the same listener's `Escape` branch, add a check before the existing `if (addPaletteOpen())` line:

```js
    if (deckSwitchPaletteOpen()) { closeDeckSwitchPalette(); return; }
    if (addPaletteOpen()) { closeAddPalette(); return; }
```

- [ ] **Step 3: Add arrow/Enter navigation inside the palette's search input**

Near the `#deck-switch-search` `input` listener added in Task 2, add:

```js
document.getElementById('deck-switch-search').addEventListener('keydown', e => {
  const matches = filterDecks(deckState.decks, deckState.switchQuery);
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    deckState.switchFocusIdx = Math.min(deckState.switchFocusIdx + 1, matches.length - 1);
    renderDeckSwitchResults();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    deckState.switchFocusIdx = Math.max(deckState.switchFocusIdx - 1, -1);
    renderDeckSwitchResults();
  } else if (e.key === 'Enter') {
    e.preventDefault();
    const idx = deckState.switchFocusIdx >= 0 ? deckState.switchFocusIdx : 0;
    const deck = matches[idx];
    if (deck) { selectDeck(deck.id); closeDeckSwitchPalette(); }
  } else if (e.key === 'Escape') {
    e.preventDefault();
    closeDeckSwitchPalette();
  }
});
```

- [ ] **Step 4: Add click-outside-to-close**

Near the existing `mousedown` listener that closes the add-card palette on outside click, add:

```js
document.addEventListener('mousedown', e => {
  if (!deckSwitchPaletteOpen()) return;
  const palette = document.getElementById('deck-switch-palette');
  const btn     = document.getElementById('deck-switch-btn');
  if (palette && palette.contains(e.target)) return;
  if (btn && btn.contains(e.target)) return;   // let the opener's own click through
  closeDeckSwitchPalette();
});
```

- [ ] **Step 5: Manual verification**

With the dev server running, on the Decks page with a deck already selected:
- Press `d` → palette opens, search input focused.
- Type part of a deck name → list filters live.
- Press ArrowDown/ArrowUp → focus ring moves through matches (`.deck-list-item.focused` background).
- Press Enter → selects the focused (or first, if none focused) match and closes the palette.
- Press `d` again, then Escape → palette closes without changing the selected deck.
- Press `d` again, then click outside the panel → palette closes.
- Confirm typing "d" inside `deck-content-search` or the add-card palette's `deck-search` input does **not** open the switch palette.

- [ ] **Step 6: Commit**

```bash
git add static/app.js
git commit -m "feat: add keyboard navigation to the deck-switcher palette"
```

---

### Task 4: Auto-open on empty selection + final cleanup pass

**Files:**
- Modify: `static/app.js` — nav-click handler (currently `static/app.js:1154-1164`) and the `deck-delete-btn` click handler (currently `static/app.js:2013-2026`).

**Interfaces:**
- Consumes: `openDeckSwitchPalette()`, `loadDeckList()` (now returns the same promise as before — `async function`, unchanged signature), `deckState.currentDeckId`.

- [ ] **Step 1: Auto-open when navigating to Decks with nothing selected**

Replace:

```js
    if (btn.dataset.view !== 'decks')      closeAddPalette();
    if (btn.dataset.view === 'decks')      loadDeckList();
    if (btn.dataset.view === 'collection') loadCollectionView();
```

with:

```js
    if (btn.dataset.view !== 'decks')      closeAddPalette();
    if (btn.dataset.view === 'decks') {
      loadDeckList().then(() => {
        if (!deckState.currentDeckId) openDeckSwitchPalette();
      });
    }
    if (btn.dataset.view === 'collection') loadCollectionView();
```

- [ ] **Step 2: Auto-open after deleting the current deck**

Replace:

```js
document.getElementById('deck-delete-btn').addEventListener('click', async () => {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (!deck) return;
  if (!confirm(`Delete "${deck.name}"?`)) return;
  try {
    await API.deleteDeck(deck.id);
    deckState.decks = deckState.decks.filter(d => d.id !== deck.id);
    deckState.currentDeckId = null;
    deckState.deckCards = [];
    renderDeckSwitchResults();
    document.getElementById('deck-editor').classList.add('hidden');
    document.getElementById('deck-empty').classList.remove('hidden');
  } catch (e) { alert('Failed to delete deck.'); }
});
```

with:

```js
document.getElementById('deck-delete-btn').addEventListener('click', async () => {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (!deck) return;
  if (!confirm(`Delete "${deck.name}"?`)) return;
  try {
    await API.deleteDeck(deck.id);
    deckState.decks = deckState.decks.filter(d => d.id !== deck.id);
    deckState.currentDeckId = null;
    deckState.deckCards = [];
    renderDeckSwitchResults();
    document.getElementById('deck-editor').classList.add('hidden');
    document.getElementById('deck-empty').classList.remove('hidden');
    openDeckSwitchPalette();
  } catch (e) { alert('Failed to delete deck.'); }
});
```

(This is the fifth `renderDeckList()` call site mentioned in Task 2 Step 3, deliberately left for this task — the replacement above both renames it to `renderDeckSwitchResults()` and adds the trailing `openDeckSwitchPalette()` call.)

- [ ] **Step 3: Full manual QA pass**

With the dev server running:
- Fresh load → Collection page shown (unrelated prior work) → click "Decks" nav button → palette auto-opens (no decks selected yet).
- Pick a deck → palette closes, editor shows that deck, full width (no sidebar).
- Switch to Collection, then back to Decks → palette does **not** re-open (a deck is already selected) — editor shows the same deck.
- Delete the currently-open deck → confirms, then the switch palette auto-opens again.
- With zero decks (delete all, or a fresh DB) → palette auto-opens showing "No decks yet." plus "+ New"/"↑ Import" still reachable.
- Escape out of an auto-opened palette with nothing picked → main area shows "No deck selected — press d".

- [ ] **Step 4: Run the full existing test suite to confirm nothing else broke**

Run: `pytest` and `node tests/js/parse-add-query.test.mjs` and `node tests/js/filter-decks.test.mjs`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: auto-open the deck-switcher palette when no deck is selected"
```
