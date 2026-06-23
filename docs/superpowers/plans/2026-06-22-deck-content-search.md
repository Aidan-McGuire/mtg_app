# Deck Page Content Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a search box to the deck editor that filters the deck's current cards by name, rules text, or card type.

**Architecture:** Frontend-only. Extend the shared `applyFilters` text matcher to also match `type_line` (one line, applies to the collection search too). Add a search input at the top of the deck content column bound to a new `deckState.query`, fed into `deckState.filter.text` by `renderDeckContent` (mirroring the collection search pattern), with reset on deck switch.

**Tech Stack:** Vanilla JS (`static/app.js`), HTML (`static/index.html`), CSS (`static/style.css`). No backend or Python test changes. JS has no automated test harness — verification is `/opt/homebrew/bin/node --check static/app.js` + manual click-through.

## Global Constraints

- **No backend changes.** All filtering is client-side over the already-loaded `deckState.deckCards`.
- **One combined box** matching name OR rules text OR type — case-insensitive substring. No separate per-field inputs.
- **The text matcher is shared** (`applyFilters`); extending it to `type_line` intentionally also affects the collection search ("apply everywhere").
- **Do not add a new keyboard shortcut.** `/` stays mapped to the existing add-cards box (`#deck-search`). Do not touch the add-cards search.
- Use the native ARM node for syntax checks: `/opt/homebrew/bin/node --check static/app.js` (NOT `/usr/local`, a dead Intel binary).

---

### Task 1: Extend the shared text matcher to match `type_line`

**Files:**
- Modify: `static/app.js` — the `model.text` branch in `applyFilters` (currently lines 223-227)

**Interfaces:**
- Consumes: nothing new.
- Produces: `applyFilters(cards, model)` — unchanged signature; `model.text` now matches against `name`, `oracle_text`, AND `type_line` (case-insensitive substring). Consumed by the collection grid, the browser, and the deck content (Task 2).

- [ ] **Step 1: Add the `type_line` clause**

In `static/app.js`, replace the current `model.text` branch in `applyFilters`:

```javascript
    if (model.text) {
      const t = model.text.toLowerCase();
      if (!c.name.toLowerCase().includes(t) &&
          !(c.oracle_text || '').toLowerCase().includes(t)) return false;
    }
```

with:

```javascript
    if (model.text) {
      const t = model.text.toLowerCase();
      if (!c.name.toLowerCase().includes(t) &&
          !(c.oracle_text || '').toLowerCase().includes(t) &&
          !(c.type_line || '').toLowerCase().includes(t)) return false;
    }
```

- [ ] **Step 2: Syntax check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit 0.

- [ ] **Step 3: Manual verification (record result in report)**

Start the server if not running (`uvicorn app:app --reload`). In the **collection** search box (the existing one), type a type word such as `instant` or `creature`. Expected: results now include cards whose type line contains that word (previously the box matched only name + rules text). Typing a card name or a rules-text phrase still works.

If you cannot run a browser, state that explicitly and confirm by re-reading that the new clause mirrors the existing two clauses exactly (same `.toLowerCase().includes(t)` shape, `|| ''` null-guard on `type_line`).

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: match card type in the shared text filter"
```

---

### Task 2: Deck content search box

**Files:**
- Modify: `static/index.html` — add the input at the top of `#deck-content-col` (the `<div class="deck-content-col">` at line 92)
- Modify: `static/app.js` — `deckState` object (line 1533), `renderDeckContent` (line 1610), `selectDeck` (line 1578), and add two event listeners near the collection-search listeners (around line 1364)
- Modify: `static/style.css` — add styling for the new input

**Interfaces:**
- Consumes: `applyFilters` (with the `type_line` match from Task 1); existing `renderDeckContent`, `selectDeck`, `deckState`.
- Produces: a `#deck-content-search` input; a `deckState.query` string field feeding `deckState.filter.text`.

- [ ] **Step 1: Add the input to the HTML**

In `static/index.html`, change the deck content column (line 92):

```html
              <div class="deck-content-col">
                <div id="deck-grid-view" class="deck-grid-view"></div>
                <div id="deck-text-view" class="deck-text-view hidden"></div>
              </div>
```

to:

```html
              <div class="deck-content-col">
                <input id="deck-content-search" class="deck-content-search-input"
                  type="text" placeholder="Filter cards… (name, text, type)"
                  autocomplete="off" spellcheck="false">
                <div id="deck-grid-view" class="deck-grid-view"></div>
                <div id="deck-text-view" class="deck-text-view hidden"></div>
              </div>
```

- [ ] **Step 2: Add `query` to `deckState`**

In `static/app.js`, in the `deckState` object literal (starts line 1533), add a `query` field. Change:

```javascript
  filter:         makeFilterModel(),
  searchResults:  [],
```

to:

```javascript
  filter:         makeFilterModel(),
  query:          '',       // deck content search box (name/text/type)
  searchResults:  [],
```

- [ ] **Step 3: Feed `query` into the filter in `renderDeckContent`**

In `static/app.js`, at the start of `renderDeckContent` (line 1610), set the
filter text from the query before any rendering. Change:

```javascript
function renderDeckContent() {
  const deck  = deckState.decks.find(d => d.id === deckState.currentDeckId);
```

to:

```javascript
function renderDeckContent() {
  deckState.filter.text = deckState.query;   // content search box feeds the model
  const deck  = deckState.decks.find(d => d.id === deckState.currentDeckId);
```

- [ ] **Step 4: Reset the search on deck switch**

In `static/app.js`, in `selectDeck` (line 1578), reset the query and clear the
input alongside the existing filter reset. Change:

```javascript
async function selectDeck(id) {
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  deckState.filter = makeFilterModel();   // reset filters between decks
  renderDeckList();
```

to:

```javascript
async function selectDeck(id) {
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
  const searchInput = document.getElementById('deck-content-search');
  if (searchInput) searchInput.value = '';
  renderDeckList();
```

- [ ] **Step 5: Wire the input events**

In `static/app.js`, immediately after the collection-search `keydown` listener
(the block ending at line 1364), add:

```javascript
document.getElementById('deck-content-search').addEventListener('input', e => {
  deckState.query = e.target.value;
  renderDeckContent();
});

document.getElementById('deck-content-search').addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.target.blur(); deckState.query = ''; renderDeckContent(); }
});
```

- [ ] **Step 6: Add CSS for the input (sticky at top of the scrolling column)**

In `static/style.css`, add after the `.deck-content-col` rule (line 637-641):

```css
.deck-content-search-input {
  position: sticky;
  top: 0;
  z-index: 1;
  box-sizing: border-box;
  width: 100%;
  margin-bottom: 10px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  font-size: 13px;
  padding: 8px 12px;
  outline: none;
  transition: border-color 0.12s;
}
.deck-content-search-input:focus { border-color: var(--accent); }
.deck-content-search-input::placeholder { color: var(--muted); }
```

- [ ] **Step 7: Syntax check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit 0.

- [ ] **Step 8: Manual verification (record result in report)**

Start the server (`uvicorn app:app --reload`). Open a deck with several cards:
- Type a type word (e.g. `instant`) → the deck content (grid and text views) narrows to matching cards.
- Type part of a card name → filters by name; type a rules-text phrase → filters by oracle text.
- Clear the box or press Escape → the full deck returns.
- Switch to another deck → the search box is empty and the new deck shows in full.
- The box stays visible (sticky) when scrolling a long deck.

If you cannot run a browser, state that explicitly and confirm by re-reading: the input id matches the listeners, `deckState.query` is set on input and reset on deck switch, and `renderDeckContent` copies `query` into `filter.text` before `applyFilters`.

- [ ] **Step 9: Commit**

```bash
git add static/index.html static/app.js static/style.css
git commit -m "feat: add content search box to the deck editor"
```

---

## Self-Review Notes

- **Spec coverage:** `type_line` added to shared matcher (Task 1) ✓; search box in deck content column (Task 2 Step 1) ✓; `deckState.query` field (Step 2) ✓; `renderDeckContent` feeds query→filter.text mirroring collection (Step 3) ✓; reset on deck switch incl. input clear with null guard (Step 4) ✓; input + Escape listeners mirroring collection-search (Step 5) ✓; CSS incl. sticky polish for the scrolling column (Step 6) ✓; empty-state reuses existing `deck-empty-msg` path (no new code — the existing messages at `renderDeckGrid`/`renderDeckText` already cover "no cards match") ✓; no new `/` shortcut, add-cards box untouched ✓.
- **Placeholders:** none — full before/after code for every edit. No automated JS tests exist; verification is `node --check` + manual, stated honestly.
- **Type consistency:** `deckState.query` (string) defined in Task 2 Step 2, read in Steps 3/4/5 consistently. `#deck-content-search` id identical across HTML (Step 1), reset (Step 4), and listeners (Step 5). `applyFilters` signature unchanged; Task 2 relies only on the `type_line` behavior added in Task 1.
