# Deck Quick-Tag Keyboard Palette Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user apply a deck tag to the keyboard-focused deck card without touching the mouse, via a `t`/`T` quick-tag palette on the deck page.

**Architecture:** Add a small fixed-position palette (`#deck-tag-palette`), following the exact structural/behavioral pattern of the existing `deck-add-palette` / `deck-switch-palette`: a global keydown handler opens it when `t`/`T` is pressed on the deck page with a card keyboard-focused; the palette's own input listens for `Enter`/`,` (add tag, stay open) and `Escape` (close); a global `mousedown` listener closes it on outside click. Tag submission reuses the existing `API.addDeckTag` / `API.listDeckTags` and the existing `syncDeckTagsOnCard` re-render helper — no backend changes.

**Tech Stack:** Vanilla JS (`static/app.js`), HTML (`static/index.html`), CSS (`static/style.css`). No backend/DB changes.

**Spec:** `docs/superpowers/backlog/029-deck-quick-tag-keyboard.md`

## Global Constraints

- Shortcut key is `t`/`T`, currently unused on the deck page.
- No new positioning CSS — `.deck-tag-palette` joins the existing shared
  selector `.deck-add-palette, .deck-switch-palette` in `static/style.css:630`.
- Tag normalization must match `buildTagEditor`'s existing input handler
  exactly: `trim().toLowerCase().replace(/,/g, '')`, skip if empty or already
  present in the target card's `deck_tags`.
- Out of scope: removing a tag from this palette.
- Do not touch the `Enter` case (item 027) or `/`/`a` rebinding (item 028) —
  this worktree predates both; only add the `t`/`T` block and extend the
  existing `!deckSwitchPaletteOpen() && !addPaletteOpen()` guard.

---

### Task 1: Palette markup + CSS

**Files:**
- Modify: `static/index.html` (add palette markup after the `deck-switch-palette` block, around line 134)
- Modify: `static/style.css:630` (extend shared selector)

**Interfaces:**
- Produces DOM ids consumed by Task 2: `#deck-tag-palette`, `#deck-tag-palette-card`, `#deck-tag-input`, `#deck-tag-suggestions`.

- [x] **Step 1: Add palette markup to `static/index.html`**

Insert immediately after the `<!-- Deck-switch palette (decks page) -->` block (after its closing `</div>` at line 134):

```html
  <!-- Deck quick-tag palette (decks page) -->
  <div id="deck-tag-palette" class="deck-tag-palette hidden">
    <div id="deck-tag-palette-card" class="deck-tag-palette-card"></div>
    <input id="deck-tag-input" class="deck-search-input" list="deck-tag-suggestions" placeholder="Add tag…" autocomplete="off">
    <datalist id="deck-tag-suggestions"></datalist>
  </div>
```

- [x] **Step 2: Extend the shared palette selector in `static/style.css`**

Change:
```css
.deck-add-palette, .deck-switch-palette {
```
to:
```css
.deck-add-palette, .deck-switch-palette, .deck-tag-palette {
```

Add a small label style for the card-name element right after that rule block (after the closing `}` of `.deck-add-input-row`'s block area — anywhere near the palette rules is fine, e.g. directly after the `.deck-search-input::placeholder` rule at line 688):

```css
.deck-tag-palette-card {
  padding: 10px 12px 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  flex-shrink: 0;
}
```

- [x] **Step 3: Verify HTML/CSS are well-formed**

Run: `python3 -c "import re; s=open('static/index.html').read(); assert s.count('deck-tag-palette') >= 1; print('ok')"`
Expected: `ok`

- [x] **Step 4: Commit**

```bash
git add static/index.html static/style.css
git commit -m "feat: add deck quick-tag palette markup and styling"
```

---

### Task 2: Palette open/close logic + input handler in `static/app.js`

**Files:**
- Modify: `static/app.js` — add new functions near the existing palette helpers (a good spot is right after `closeDeckSwitchPalette()`, currently `static/app.js:1946-1953`, or alternatively grouped with `addPaletteOpen`/`openAddPalette`/`closeAddPalette` at `static/app.js:2503-2530`; place them together in one new section for readability).

**Interfaces:**
- Consumes: `deckState.currentDeckId`, `deckState.focusedCardId`, `deckState.deckCards` (existing), `API.listDeckTags(deckId)`, `API.addDeckTag(deckId, cardId, tag)` (existing, `static/app.js:147-166`), `syncDeckTagsOnCard(cardId, tags)` (existing, `static/app.js:1232-1235`), `esc()` (existing HTML-escape helper used throughout the file).
- Produces: `deckTagPaletteOpen()`, `openDeckTagPalette()`, `closeDeckTagPalette()` — consumed by Task 3 (global keydown block) and Task 4 (outside-click handler). Also tracks the palette's fixed target card id in module-level variable `deckTagPaletteCardId`.

- [x] **Step 1: Add the quick-tag palette section**

Add this new section to `static/app.js` (suggested location: immediately after `closeDeckSwitchPalette()` at line 1953, before `renderDeckSwitchResults`):

```javascript
// ── Deck quick-tag palette ───────────────────────────────────────────────────

let deckTagPaletteCardId = null;   // card the open palette targets; fixed for its lifetime

function deckTagPaletteOpen() {
  const p = document.getElementById('deck-tag-palette');
  return !!p && !p.classList.contains('hidden');
}

async function openDeckTagPalette() {
  if (!deckState.currentDeckId || !deckState.focusedCardId) return;
  const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
  if (!card) return;

  closeAddPalette();
  closeDeckSwitchPalette();

  deckTagPaletteCardId = card.id;

  const palette   = document.getElementById('deck-tag-palette');
  const cardLabel = document.getElementById('deck-tag-palette-card');
  const input     = document.getElementById('deck-tag-input');
  const datalist  = document.getElementById('deck-tag-suggestions');
  if (!palette || !cardLabel || !input || !datalist) return;

  cardLabel.textContent = card.name;
  input.value = '';

  let suggestions = [];
  try {
    suggestions = await API.listDeckTags(deckState.currentDeckId);
  } catch {
    suggestions = [];
  }
  if (!palette.isConnected) return;   // closed while the request was in flight
  datalist.innerHTML = suggestions.map(s => `<option value="${esc(s)}">`).join('');

  palette.classList.remove('hidden');
  input.focus();
}

function closeDeckTagPalette() {
  const palette = document.getElementById('deck-tag-palette');
  const input   = document.getElementById('deck-tag-input');
  if (input) { input.blur(); input.value = ''; }
  if (palette) palette.classList.add('hidden');
  deckTagPaletteCardId = null;
}

document.getElementById('deck-tag-input').addEventListener('keydown', async e => {
  if (e.key === 'Enter' || e.key === ',') {
    e.preventDefault();
    const input = e.target;
    const val = input.value.trim().toLowerCase().replace(/,/g, '');
    const card = deckState.deckCards.find(c => c.id === deckTagPaletteCardId);
    if (!val || !card || (card.deck_tags || []).includes(val)) { input.value = ''; return; }
    try {
      const updated = await API.addDeckTag(deckState.currentDeckId, card.id, val);
      syncDeckTagsOnCard(card.id, updated);
    } catch {
      // leave the input as-is on failure so the user can retry
      return;
    }
    input.value = '';
  } else if (e.key === 'Escape') {
    e.preventDefault();
    closeDeckTagPalette();
  }
});
```

Note: `syncDeckTagsOnCard` calls `renderDeckContent()`, which re-renders deck tiles/rows but does not touch `#deck-tag-palette`, so the palette and its input stay open/focused across the re-render — no re-focus step needed.

- [x] **Step 2: Sanity-check syntax with node**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output (exit code 0)

- [x] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: add deck quick-tag palette open/close and input handling"
```

---

### Task 3: Wire up the `t`/`T` shortcut and guard existing deck-page key handling

**Files:**
- Modify: `static/app.js:1291-1292` (Escape-key cascade)
- Modify: `static/app.js:1321-1343` (deck-page keydown block)

**Interfaces:**
- Consumes: `deckTagPaletteOpen()`, `openDeckTagPalette()`, `closeDeckTagPalette()` from Task 2.

- [x] **Step 1: Add quick-tag palette to the Escape cascade**

In the global keydown handler's `Escape` branch (`static/app.js:1282-1296`), add a check before the existing `deckSwitchPaletteOpen()` line so Escape closes the tag palette first if it's open:

Change:
```javascript
    if (deckSwitchPaletteOpen()) { closeDeckSwitchPalette(); return; }
    if (addPaletteOpen()) { closeAddPalette(); return; }
```
to:
```javascript
    if (deckTagPaletteOpen()) { closeDeckTagPalette(); return; }
    if (deckSwitchPaletteOpen()) { closeDeckSwitchPalette(); return; }
    if (addPaletteOpen()) { closeAddPalette(); return; }
```

(The tag palette's own input `keydown` listener from Task 2 also handles `Escape` directly and calls `e.preventDefault()`, so in practice that listener fires first when the input has focus. This global fallback keeps behavior correct if Escape is ever dispatched without the input focused.)

- [x] **Step 2: Extend the deck-page arrow-nav guard and add the `t`/`T` case**

Change (`static/app.js:1321-1343`):
```javascript
  if (decksActive && deckState.currentDeckId &&
      !deckSwitchPaletteOpen() && !addPaletteOpen()) {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea, select');
    const isArrow = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key);
    if (!typingInField && isArrow) {
      if (deckState.deckView === 'grid') handleDeckColumnNavKey(e, 'deck-grid-view');
      else handleDeckColumnNavKey(e, 'deck-text-view');
      return;
    }
    if (!typingInField && e.key === 'Backspace' && deckState.focusedCardId) {
      e.preventDefault();
      removeDeckCard(deckState.focusedCardId);
      return;
    }
    if (!typingInField && (e.key === 'c' || e.key === 'C') && deckState.focusedCardId) {
      const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
      if (card && !card.is_commander) {
        e.preventDefault();
        toggleConsidering(card.id);
      }
    }
  }
```
to:
```javascript
  if (decksActive && deckState.currentDeckId &&
      !deckSwitchPaletteOpen() && !addPaletteOpen() && !deckTagPaletteOpen()) {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea, select');
    const isArrow = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key);
    if (!typingInField && isArrow) {
      if (deckState.deckView === 'grid') handleDeckColumnNavKey(e, 'deck-grid-view');
      else handleDeckColumnNavKey(e, 'deck-text-view');
      return;
    }
    if (!typingInField && e.key === 'Backspace' && deckState.focusedCardId) {
      e.preventDefault();
      removeDeckCard(deckState.focusedCardId);
      return;
    }
    if (!typingInField && (e.key === 'c' || e.key === 'C') && deckState.focusedCardId) {
      const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
      if (card && !card.is_commander) {
        e.preventDefault();
        toggleConsidering(card.id);
      }
    }
    if (!typingInField && (e.key === 't' || e.key === 'T') && deckState.focusedCardId) {
      e.preventDefault();
      openDeckTagPalette();
      return;
    }
  }
```

- [x] **Step 3: Sanity-check syntax with node**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output (exit code 0)

- [x] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: wire up t/T shortcut to open the deck quick-tag palette"
```

---

### Task 4: Outside-click handling

**Files:**
- Modify: `static/app.js` — add a third `mousedown` listener alongside the existing two at the end of the file (`static/app.js:2849-2865`).

**Interfaces:**
- Consumes: `deckTagPaletteOpen()`, `closeDeckTagPalette()` from Task 2.

- [x] **Step 1: Add the outside-click listener**

Append after the existing second `mousedown` listener (after line 2865, the closing `});` for the deck-switch-palette outside-click handler):

```javascript

document.addEventListener('mousedown', e => {
  if (!deckTagPaletteOpen()) return;
  const palette = document.getElementById('deck-tag-palette');
  if (palette && palette.contains(e.target)) return;
  closeDeckTagPalette();
});
```

Note: unlike the other two palettes, the quick-tag palette has no dedicated "open" button to exempt (it opens only via the `t`/`T` shortcut while a card is focused), so the listener only needs the palette-containment check.

- [x] **Step 2: Sanity-check syntax with node**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output (exit code 0)

- [x] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: close deck quick-tag palette on outside click"
```

---

### Task 5: Manual verification against every acceptance criterion + regression checks

**Files:** none (verification only)

- [x] **Step 1: Trace each acceptance criterion against the code**

Re-read the final state of `static/app.js`, `static/index.html`, `static/style.css`
and confirm, by code inspection:

1. `t` with a card focused on the deck grid/list opens the palette showing
   that card's name (`openDeckTagPalette` reads `deckState.focusedCardId`,
   sets `cardLabel.textContent = card.name`, focuses `#deck-tag-input`).
2. `Enter` on a typed value applies the tag (`API.addDeckTag` + `syncDeckTagsOnCard`
   triggers `renderDeckContent()`, which redraws the chip), clears the input,
   and does not hide the palette.
3. Autocomplete: `datalist#deck-tag-suggestions` is populated from
   `API.listDeckTags(deckState.currentDeckId)` on every open.
4. `Escape` with an empty input closes without adding anything — the handler
   only calls `API.addDeckTag` on the `Enter`/`,` branch, never on `Escape`.
5. Outside click closes the palette (Task 4's `mousedown` listener).
6. Arrow keys go to the input while the palette is open — the deck-page
   arrow-nav block is now gated by `!deckTagPaletteOpen()`, so
   `handleDeckColumnNavKey` never fires; native `<input>` behavior handles
   arrow keys as cursor movement.
7. Duplicate tag is a no-op — `(card.deck_tags || []).includes(val)` check
   before calling `API.addDeckTag`, matching `buildTagEditor`'s dedupe.

- [x] **Step 2: Run the JS unit test suite as a regression check**

Run: `/opt/homebrew/bin/node tests/js/*.test.mjs` (or iterate each file under `tests/js/` individually if globbing doesn't expand in the shell used)
Expected: all existing tests pass (this feature's DOM-event code is unlikely
to be covered, per the task brief — this is a regression check, not new
coverage).

- [x] **Step 3: Run the backend test suite**

Run: `python3 -m pytest`
Expected: all pass. If `mtg.db` is an uninitialized stub, first run:
`python3 -c "import main; main.initialize_database(); main.migrate_database()"`

- [x] **Step 4: Final commit if any fixups were needed**

```bash
git add -A
git commit -m "fix: address issues found during quick-tag palette verification"
```

(Skip this commit if verification found no issues.)
