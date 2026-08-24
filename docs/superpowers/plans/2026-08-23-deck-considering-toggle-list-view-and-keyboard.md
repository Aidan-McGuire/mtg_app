# Deck Considering Toggle: List View + Keyboard Shortcut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a considering-toggle button to deck list view (matching grid view's), plus a shared `c` keyboard shortcut that toggles Considering on the currently focused non-commander card in either view, with a `c` badge hint on the focused card.

**Architecture:** Pure frontend change to `static/app.js`. Reuse the existing `.deck-considering-btn` CSS and `.deck-considering-btn` click-wiring pattern already used by `buildDeckCardTile` (grid view), replicating it in `buildDeckTextRow` (list view). Reuse the existing `.deck-kbd-hint` CSS class (already generic — shows any `<kbd>` content when the parent tile/row has `.focused`) for the new `c` badge, so no new CSS is needed. Add one new branch to the deck page's existing keyboard-dispatch block, mirroring the `Backspace` binding already there.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), plain CSS (`static/style.css`, unchanged — reusing existing rules), static HTML (`static/index.html`, unchanged). Frontend unit tests are plain Node scripts under `tests/js/` that extract sentinel-comment-delimited *pure* functions out of `static/app.js` via string slicing + `new Function(...)` (see `tests/js/filter-decks.test.mjs`). Every function this plan touches (`buildDeckCardTile`, `buildDeckTextRow`, the global `keydown` handler) is DOM-wiring that reads `document`/`deckState`, not a pure function — consistent with the rest of the codebase's render functions, none of it gets sentinel-comment unit tests. There is no DOM/jsdom harness and no browser-automation tool available in this run, so verification is: (a) `node --check static/app.js` for syntax, (b) the full existing `tests/js/*.test.mjs` + `pytest` suites staying green (regression check — this plan doesn't touch anything those tests cover), and (c) careful line-by-line trace of the new/changed DOM code against every acceptance criterion in the spec.

**Spec:** `docs/superpowers/backlog/012-deck-considering-toggle-list-view-and-keyboard.md`

## Global Constraints

- Reuse the existing `.deck-considering-btn` CSS (style.css:850-865) as-is — no new styles.
- Reuse the existing `.deck-kbd-hint` CSS (style.css:928-930) as-is for the new `c` badge — it already shows any `<kbd class="deck-kbd-hint">` content when the ancestor `.deck-card-tile`/`.deck-text-row` has `.focused`, and hides it otherwise.
- `c`/`C` is the shortcut key (case-insensitive), unused elsewhere in the app.
- No change to `toggleConsidering` itself (app.js:2375), or to how Considering cards are rendered/grouped/counted.
- No keyboard shortcut or button for the commander toggle (`.deck-cmd-btn`) — out of scope.
- All three changes (list-view button, grid-view badge, keyboard binding) must independently preserve the commander guard: nothing Considering-related renders or fires for `card.is_commander === true`.

---

## Current code (reference — read before editing)

`buildDeckCardTile` (app.js:2120-2169) already renders, for non-commander cards, inside its `.deck-actions` div:
```js
const consideringBtnHtml = card.is_commander ? '' : `
    <button class="deck-considering-btn${card.is_considering ? ' active' : ''}"
            title="${card.is_considering ? 'Move back to deck' : 'Move to Considering'}">?</button>`;
```
and wires it with:
```js
const consideringBtn = div.querySelector('.deck-considering-btn');
if (consideringBtn) consideringBtn.addEventListener('click', e => { e.stopPropagation(); toggleConsidering(card.id); });
```

`buildDeckTextRow` (app.js:2171-2186) currently has no considering button at all:
```js
function buildDeckTextRow(card) {
  const row = document.createElement('div');
  row.className = 'deck-text-row' + (card.id === deckState.focusedCardId ? ' focused' : '');
  row.dataset.id = card.id;
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>
    ${tagChipsHtml(card.deck_tags, 'deck-tag')}
    <kbd class="deck-kbd-hint" title="Remove focused card">⌫</kbd>
    <button class="deck-remove-btn" title="Remove">×</button>`;
  row.querySelector('.deck-remove-btn').addEventListener('click', e => { e.stopPropagation(); removeDeckCard(card.id); });
  row.addEventListener('mouseenter', () => setDeckFocus(card.id, row));
  row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
  return row;
}
```

The deck page's keyboard-dispatch block (app.js:1263-1279):
```js
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
  }
```

`deckState.deckCards` (app.js:1841 area) is the array `.find`-searched elsewhere in this file (see the `Backspace` handler's sibling `removeDeckCard`, and `toggleConsidering` at app.js:2375-2382) — `deckState.deckCards.find(c => c.id === id)` is the established lookup pattern.

---

## Task 1: Add the considering button to list view

**Files:**
- Modify: `static/app.js:2171-2186` (`buildDeckTextRow`)

**Interfaces:**
- Consumes: `toggleConsidering(cardId)` (app.js:2375, existing, unchanged), `deckState.focusedCardId` (existing), `card.is_commander`/`card.is_considering` (existing fields already present on deck card objects, used identically by `buildDeckCardTile`).
- Produces: nothing new consumed elsewhere — this is a leaf render function.

- [ ] **Step 1: Edit `buildDeckTextRow` to add the considering button**

Replace the full function body (app.js:2171-2186) with:

```js
function buildDeckTextRow(card) {
  const row = document.createElement('div');
  row.className = 'deck-text-row' + (card.id === deckState.focusedCardId ? ' focused' : '');
  row.dataset.id = card.id;

  // A commander can't be Considering, so the toggle is pointless on this row.
  const consideringBtnHtml = card.is_commander ? '' : `
    <button class="deck-considering-btn${card.is_considering ? ' active' : ''}"
            title="${card.is_considering ? 'Move back to deck' : 'Move to Considering'}">?</button>`;

  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>
    ${tagChipsHtml(card.deck_tags, 'deck-tag')}
    ${consideringBtnHtml}
    <kbd class="deck-kbd-hint" title="Remove focused card">⌫</kbd>
    <button class="deck-remove-btn" title="Remove">×</button>`;
  const consideringBtn = row.querySelector('.deck-considering-btn');
  if (consideringBtn) consideringBtn.addEventListener('click', e => { e.stopPropagation(); toggleConsidering(card.id); });
  row.querySelector('.deck-remove-btn').addEventListener('click', e => { e.stopPropagation(); removeDeckCard(card.id); });
  row.addEventListener('mouseenter', () => setDeckFocus(card.id, row));
  row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
  return row;
}
```

- [ ] **Step 2: Syntax check**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Regression check — existing suites still green**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: every `.test.mjs` file prints its all-passing summary; pytest reports all passing. (Regression only — nothing in this task touches code any existing test covers.)

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: add considering-toggle button to deck list view"
```

---

## Task 2: Add the `c` keyboard-hint badge to both views

**Files:**
- Modify: `static/app.js:2136-2138` (`buildDeckCardTile`'s `consideringBtnHtml`)
- Modify: `static/app.js` (the `consideringBtnHtml` block added in Task 1, inside `buildDeckTextRow`)

**Interfaces:**
- Consumes: `.deck-kbd-hint` CSS class (style.css:928-930, existing — already shows/hides based on ancestor `.focused`, no changes needed there).
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Add the badge in `buildDeckCardTile`**

In app.js, change the `consideringBtnHtml` inside `buildDeckCardTile` (currently app.js:2136-2138) from:

```js
  const consideringBtnHtml = card.is_commander ? '' : `
    <button class="deck-considering-btn${card.is_considering ? ' active' : ''}"
            title="${card.is_considering ? 'Move back to deck' : 'Move to Considering'}">?</button>`;
```

to:

```js
  const consideringBtnHtml = card.is_commander ? '' : `
    <button class="deck-considering-btn${card.is_considering ? ' active' : ''}"
            title="${card.is_considering ? 'Move back to deck' : 'Move to Considering'}">?</button>
    <kbd class="deck-kbd-hint" title="Toggle Considering">c</kbd>`;
```

- [ ] **Step 2: Add the same badge in `buildDeckTextRow`**

Apply the identical change to the `consideringBtnHtml` block added in Task 1 (inside `buildDeckTextRow`) — same before/after diff as Step 1, same string.

- [ ] **Step 3: Syntax check**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 4: Trace against acceptance criteria**

Confirm by reading the edited code:
- The `c` `<kbd>` is inside the `card.is_commander ? '' : ...` ternary in both functions, so it never renders for the commander — matches "A `c` badge appears ... only on the currently focused, non-commander card."
- `.deck-kbd-hint { display: none }` plus `.deck-card-tile.focused .deck-kbd-hint, .deck-text-row.focused .deck-kbd-hint { display: inline-block }` (style.css:928-930) means the badge is invisible unless the tile/row currently has `.focused` — which `buildDeckCardTile`/`buildDeckTextRow` only add when `card.id === deckState.focusedCardId` (app.js:2126, 2173) and `setDeckFocus` (app.js:2112-2118) is the sole place that mutates `.focused` classes, always removing all existing `.focused` markers first. So the badge disappears when focus moves elsewhere, with no new CSS needed.

- [ ] **Step 5: Regression check**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green (regression only).

- [ ] **Step 6: Commit**

```bash
git add static/app.js
git commit -m "feat: show a c keyboard-hint badge on the focused considering-toggle"
```

---

## Task 3: Shared `c` keyboard shortcut

**Files:**
- Modify: `static/app.js:1263-1279` (deck page keyboard-dispatch block)

**Interfaces:**
- Consumes: `deckState.focusedCardId`, `deckState.deckCards` (existing), `toggleConsidering(cardId)` (app.js:2375, existing, unchanged).
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Add the `c` binding**

In app.js, inside the `if (decksActive && deckState.currentDeckId && ...)` block, immediately after the existing `Backspace` branch (app.js:1274-1278), add:

```js
    if (!typingInField && (e.key === 'c' || e.key === 'C') && deckState.focusedCardId) {
      const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
      if (card && !card.is_commander) {
        e.preventDefault();
        toggleConsidering(card.id);
      }
    }
```

So the full block (app.js:1263-1279) reads:

```js
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

- [ ] **Step 2: Syntax check**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Trace against acceptance criteria**

Confirm by reading the edited code:
- `typingInField` guards `input, textarea, select` — matches "Pressing `c` while focus is in a text input/textarea/select does not trigger the toggle."
- The branch requires `deckState.focusedCardId` truthy, and looks the card up fresh from `deckState.deckCards` (same pattern `Backspace` and `toggleConsidering` itself use) — works identically regardless of which view (`grid`/`text`) is active, since `deckState.focusedCardId` is shared and set by both `buildDeckCardTile` and `buildDeckTextRow`'s `mouseenter` handlers and by `handleDeckColumnNavKey`'s arrow-nav (both views call `setDeckFocus`).
- `if (card && !card.is_commander)` — matches "Pressing `c` while the commander is focused does nothing" (no `preventDefault`, no `toggleConsidering` call).
- No `return` after this branch (unlike `Backspace`) is intentional — nothing below this block in the `keydown` handler reads `e.key === 'c'`/`'C'` (confirmed via `grep -n "e.key ===" static/app.js`; the only other key-driven logic below is gated by `browserActive`, which is false whenever `decksActive` is true), so a fallthrough is harmless either way, and the spec's approach snippet has no trailing `return`.

- [ ] **Step 4: Regression check**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green (regression only).

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: add c keyboard shortcut to toggle deck Considering state"
```

---

## Task 4: Full acceptance-criteria walkthrough

**Files:** none (verification only)

- [ ] **Step 1: Re-read the spec's acceptance criteria and map each to the change that satisfies it**

Walk `docs/superpowers/backlog/012-deck-considering-toggle-list-view-and-keyboard.md`'s "## Acceptance criteria" list end to end against the final diff:
1. List view rows show a considering-toggle button, hidden for the commander, matching grid view's button (icon `?`, `.active` class, `title` text) → Task 1.
2. Clicking the list-view button calls `toggleConsidering(card.id)`, identical to grid view's handler → Task 1.
3. `c` toggles Considering on the focused non-commander card in either view → Task 3 (shared `deckState.focusedCardId`, works from both `buildDeckCardTile` and `buildDeckTextRow` focus paths).
4. `c` on the commander does nothing; `c` while typing in a field does nothing → Task 3's guards.
5. `c` badge shows only on the focused, non-commander card in both views, disappears on focus change or commander → Task 2.
6. Toggling via keyboard or list button updates deck count / re-groups the card the same way the grid button does → all three tasks call the unchanged `toggleConsidering`, which already does this (app.js:2375-2382, out of scope per spec).

- [ ] **Step 2: Full test suite**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: syntax check silent; every `.test.mjs` prints its all-passing summary; pytest reports all passing.

- [ ] **Step 3: Final diff review**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Expected: only `static/app.js` changed, across the three commits from Tasks 1-3, nothing unrelated staged.
