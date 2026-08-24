# Deck Removal Scoping and List-View Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Deck page, stop showing the (wrong) global collection +/− stepper in the card modal, give list view a remove-from-deck button matching grid view's ×, and add a `Backspace` keyboard shortcut (with a per-card `⌫` hint badge) to remove the currently focused card from the deck in either view.

**Architecture:** All changes live in `static/app.js` (four small, independent edits) plus a couple of new CSS rules in `static/style.css` for the new hint badge. No backend/API changes — this only touches which UI is rendered and which existing mutation functions (`removeDeckCard`, already used by the grid's × button) get a second caller.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), plain CSS (`static/style.css`), static HTML (`static/index.html`, unchanged). Frontend unit tests are plain Node scripts under `tests/js/` that extract sentinel-comment-delimited *pure* functions out of `static/app.js` via string slicing + `new Function(...)` (see `tests/js/filter-decks.test.mjs`). Every function this plan touches (`openModal`, `buildDeckCardTile`, `buildDeckTextRow`, the global `keydown` handler) is DOM-wiring that reads `document`/`deckState`, not a pure function — consistent with the rest of the codebase's render functions, none of it gets sentinel-comment unit tests. There is no DOM/jsdom harness and no browser-automation tool available in this session, so verification is: (a) `node --check static/app.js` for syntax, (b) the full existing `tests/js/*.test.mjs` + `pytest` suites staying green (regression check), and (c) careful line-by-line trace of the new/changed DOM code against every acceptance criterion in the spec.

**Spec:** `docs/superpowers/backlog/010-deck-removal-scoping-and-list-view-parity.md`

## Global Constraints

- No change to Cards page or Collection page modal/tile behavior — their collection-quantity controls (tile-level and modal-level) must stay exactly as-is.
- No qty +/−, commander, or considering controls added to list view rows — remove-only.
- No change to `incDeckCard`/`decDeckCard`/`removeDeckCard` themselves, or to the deck-quantity API.
- No undo for the new keyboard shortcut — removal is immediate, matching the existing × button's behavior/risk level.
- `Backspace` is the chosen key (present on every keyboard, unlike forward-`Delete`; not already bound to anything in this app).

---

### Task 1: Stop rendering the collection stepper when the modal is opened from the Deck page

**Files:**
- Modify: `static/app.js:808-852` (`openModal`)

**Interfaces:**
- Consumes: `openModal(card, deckContext = null)` — `deckContext` is already passed as `{ deckId: deckState.currentDeckId }` from both `buildDeckCardTile` (app.js:2152) and `buildDeckTextRow` (app.js:2167); `null`/omitted from Cards page (`handleGridKey`, app.js:800) and Collection page call sites.
- Produces: no new exports — this is a self-contained edit to `openModal`'s existing body.

**Current code (app.js:808-852):**

```js
function openModal(card, deckContext = null) {
  state.modalCard = card;
  const q = qty(card.id);

  const imgSrc = card.image_uri ? API.imageUrl(card.image_uri) : null;
  const imgHtml = imgSrc
    ? `<img id="modal-main-img" src="${imgSrc}" alt="${esc(card.name)}">`
    : `<div class="modal-img-placeholder">${esc(card.name)}</div>`;

  const contentEl = document.getElementById('modal-content');
  contentEl.innerHTML = `
    <div class="modal-left">
      <div class="modal-img" id="modal-img-wrap">${imgHtml}</div>
      <button id="modal-flip-btn" class="modal-flip-btn hidden" title="Flip card (F)">⟲ Back face</button>
      <div class="modal-art-strip" id="modal-art-strip">
        <span style="font-size:12px;color:var(--muted)">Loading art options…</span>
      </div>
    </div>
    <div class="modal-details">
      <div class="modal-name">${esc(card.name)}</div>
      <div class="modal-mana">${esc(card.mana_cost || '—')}</div>
      <div class="modal-type">${esc(card.type_line || '')}</div>
      <div class="modal-oracle">${esc(card.oracle_text || '')}</div>
      <div class="modal-collection">
        <button class="qty-btn" data-action="dec" title="Remove (-)">−</button>
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <button class="qty-btn" data-action="inc" title="Add (+)">+</button>
        <span class="qty-owned-label">owned</span>
      </div>
      <div id="modal-tags-section"></div>
      <div id="modal-decks-section"></div>
    </div>`;

  contentEl.querySelector('[data-action="inc"]').addEventListener('click', () => increment(card.id));
  contentEl.querySelector('[data-action="dec"]').addEventListener('click', () => decrement(card.id));

  document.getElementById('modal-overlay').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  document.getElementById('modal-close').focus();

  // Fetch and render art options asynchronously
  loadPrintings(card);
  loadModalTags(card, deckContext);
  loadModalDecks(card);
}
```

- [x] **Step 1: Wrap the `.modal-collection` markup in a `deckContext` check**

Replace the `<div class="modal-collection">...</div>` block with a conditional expression assigned to a local variable, then interpolate that variable in its place:

```js
function openModal(card, deckContext = null) {
  state.modalCard = card;
  const q = qty(card.id);

  const imgSrc = card.image_uri ? API.imageUrl(card.image_uri) : null;
  const imgHtml = imgSrc
    ? `<img id="modal-main-img" src="${imgSrc}" alt="${esc(card.name)}">`
    : `<div class="modal-img-placeholder">${esc(card.name)}</div>`;

  // Collection-quantity editing belongs on the Cards/Collection pages only —
  // the Deck page has its own deck-quantity controls on each tile, and
  // showing this too is a second, easily-confused quantity control.
  const collectionHtml = deckContext ? '' : `
      <div class="modal-collection">
        <button class="qty-btn" data-action="dec" title="Remove (-)">−</button>
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <button class="qty-btn" data-action="inc" title="Add (+)">+</button>
        <span class="qty-owned-label">owned</span>
      </div>`;

  const contentEl = document.getElementById('modal-content');
  contentEl.innerHTML = `
    <div class="modal-left">
      <div class="modal-img" id="modal-img-wrap">${imgHtml}</div>
      <button id="modal-flip-btn" class="modal-flip-btn hidden" title="Flip card (F)">⟲ Back face</button>
      <div class="modal-art-strip" id="modal-art-strip">
        <span style="font-size:12px;color:var(--muted)">Loading art options…</span>
      </div>
    </div>
    <div class="modal-details">
      <div class="modal-name">${esc(card.name)}</div>
      <div class="modal-mana">${esc(card.mana_cost || '—')}</div>
      <div class="modal-type">${esc(card.type_line || '')}</div>
      <div class="modal-oracle">${esc(card.oracle_text || '')}</div>
      ${collectionHtml}
      <div id="modal-tags-section"></div>
      <div id="modal-decks-section"></div>
    </div>`;

  if (!deckContext) {
    contentEl.querySelector('[data-action="inc"]').addEventListener('click', () => increment(card.id));
    contentEl.querySelector('[data-action="dec"]').addEventListener('click', () => decrement(card.id));
  }

  document.getElementById('modal-overlay').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  document.getElementById('modal-close').focus();

  // Fetch and render art options asynchronously
  loadPrintings(card);
  loadModalTags(card, deckContext);
  loadModalDecks(card);
}
```

Note: `q` is still computed unconditionally (cheap, and `qty()` has no side effects) — only its use in the markup is now conditional. This keeps the diff minimal and avoids restructuring unrelated code.

- [x] **Step 2: Syntax-check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit code 0.

- [x] **Step 3: Manually trace both call paths against the acceptance criterion**

Trace 1 (Cards page): `handleGridKey` (app.js:800) calls `openModal(c)` — `deckContext` defaults to `null`, so `collectionHtml` renders the stepper and the two `inc`/`dec` listeners attach. Unchanged from before.

Trace 2 (Deck page): `buildDeckCardTile`/`buildDeckTextRow` call `openModal(card, { deckId: deckState.currentDeckId })` — `deckContext` is a truthy object, so `collectionHtml` is `''` (no stepper rendered) and the listener-attachment block is skipped (no `querySelector('[data-action="inc"]')` call against markup that no longer contains that element, so no runtime error).

Confirm both traces hold by re-reading the edited `openModal` function.

- [x] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "fix: hide collection stepper in deck-page card modal"
```

---

### Task 2: Add a remove button to deck list view rows

**Files:**
- Modify: `static/app.js:2157-2169` (`buildDeckTextRow`)

**Interfaces:**
- Consumes: `removeDeckCard(cardId)` (app.js:2337, already defined, async, no return value used by callers) — same function the grid tile's × button already calls (app.js:2148).
- Produces: no new exports.

**Current code (app.js:2157-2169):**

```js
function buildDeckTextRow(card) {
  const row = document.createElement('div');
  row.className = 'deck-text-row' + (card.id === deckState.focusedCardId ? ' focused' : '');
  row.dataset.id = card.id;
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>
    ${tagChipsHtml(card.deck_tags, 'deck-tag')}`;
  row.addEventListener('mouseenter', () => setDeckFocus(card.id, row));
  row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
  return row;
}
```

- [x] **Step 1: Add the `.deck-remove-btn` markup and its click listener**

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

The `<kbd class="deck-kbd-hint">` is added here (not in a later task) because it belongs to the same row markup — Task 4 only adds the CSS that shows/hides it. It's harmless to have it in the DOM now (Task 4's CSS defaults it to `display: none`; until that CSS lands it's an inert always-visible `⌫`, fixed within this same plan before commit-worthy state, so add both together — see Step 2 below, which pulls Task 4's CSS forward for this row so nothing renders broken between tasks).

- [x] **Step 2: Add the same default-hidden CSS rule now (shared with Task 4, written once)**

Open `static/style.css`. After the `.deck-text-mana` rule (style.css:923), add:

```css
.deck-kbd-hint { display: none; }
.deck-card-tile.focused .deck-kbd-hint,
.deck-text-row.focused .deck-kbd-hint { display: inline-block; }
```

This is the same CSS Task 4 needs for the grid tile's badge; writing it once here means list view never renders an unstyled/always-visible badge, and Task 4 simply confirms it already covers the grid tile selector too (it does, since both selectors are added together).

- [x] **Step 3: Syntax-check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit code 0.

- [x] **Step 4: Manually trace against acceptance criteria**

- List view rows now render a `×` button (`.deck-remove-btn`, reusing the existing grid-tile CSS class — same visual style, no new CSS needed for the button itself).
- Its click handler calls `e.stopPropagation()` first (so it doesn't also trigger the row's own `click` → `openModal(...)`), then `removeDeckCard(card.id)` — the exact same function the grid tile's × button calls, so deck card count and preview panel update identically (per `removeDeckCard`, app.js:2337, which calls `syncDeckCount()` and `renderDeckContent()`).
- The new `<kbd class="deck-kbd-hint">⌫</kbd>` defaults to `display: none` per the Step 2 CSS, and only becomes visible when its row has class `.focused` — which `setDeckFocus` (app.js:2099) already toggles via `classList`, so no extra wiring is needed here for it to track focus correctly.

- [x] **Step 5: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: add remove button to deck list view rows"
```

---

### Task 3: `Backspace` keyboard shortcut removes the focused deck card

**Files:**
- Modify: `static/app.js:1255-1266` (global `keydown` listener, deck-page arrow-nav block)

**Interfaces:**
- Consumes: `deckState.focusedCardId` (existing state field, set by `setDeckFocus`), `removeDeckCard(cardId)` (app.js:2337).
- Produces: no new exports.

**Current code (app.js:1255-1266):**

```js
  // Deck page: arrow-key focus navigation drives the preview panel.
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
  }
```

- [x] **Step 1: Add a sibling `Backspace` branch inside the same guarded block**

```js
  // Deck page: arrow-key focus navigation drives the preview panel.
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

This reuses the existing `typingInField` guard (`input, textarea, select`) and the existing `decksActive`/`currentDeckId`/palette-closed gate, so it only fires on the Deck page, only when a deck is open, only when no palette is open, and never while the user is typing in a field. Because `deckState.focusedCardId` is shared by both grid and list view (set by the same `setDeckFocus` call from either view's row/tile), this one branch works for both views without any view-specific branching.

- [x] **Step 2: Syntax-check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit code 0.

- [x] **Step 3: Manually trace against acceptance criteria**

- With a card focused (via hover or arrow nav — both go through `setDeckFocus`, which sets `deckState.focusedCardId`), pressing `Backspace` while not typing in a field calls `removeDeckCard(deckState.focusedCardId)` — same function as the × buttons, so deck count/preview panel update the same way.
- If focus is inside an `input`/`textarea`/`select` (e.g. deck search box, a tag-input field), `typingInField` is `true`, so the branch is skipped entirely and `Backspace` behaves as normal text editing.
- If no card is focused (`deckState.focusedCardId` is falsy — e.g. right after switching to a freshly-loaded deck before any hover/arrow-nav), the `&& deckState.focusedCardId` guard prevents calling `removeDeckCard(undefined)`.

- [x] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: add Backspace shortcut to remove focused deck card"
```

---

### Task 4: `⌫` focus badge on the grid tile

**Files:**
- Modify: `static/app.js:2107-2155` (`buildDeckCardTile`)

**Interfaces:**
- Consumes: `deckState.focusedCardId` (read-only here), the `.deck-kbd-hint` CSS class already added by Task 2 Step 2 (`display: none` by default, `display: inline-block` when the tile/row has `.focused`).
- Produces: no new exports.

**Current code (app.js:2107-2155), relevant excerpt:**

```js
  div.innerHTML = `
    <div class="deck-card-img-wrap" data-owned-wrap-for="${card.id}">${ownedBadgeHtml}${imgHtml}</div>
    <div class="deck-card-info">
      <div class="deck-card-name">${esc(card.name)}</div>
      <div class="deck-card-row">
        <button class="qty-btn" data-action="dec" title="−">−</button>
        <span class="qty-label owned">${card.quantity}</span>
        <button class="qty-btn" data-action="inc" title="+">+</button>
        <div class="deck-actions">
          ${consideringBtnHtml}
          <button class="deck-cmd-btn${card.is_commander ? ' active' : ''}" title="Toggle commander">♛</button>
          <button class="deck-remove-btn" title="Remove">×</button>
        </div>
      </div>
      ${tagChipsHtml(card.collection_tags, 'collection-tag')}
      ${tagChipsHtml(card.deck_tags, 'deck-tag')}
    </div>`;
```

- [x] **Step 1: Add the `<kbd>` badge immediately before the remove button, inside `.deck-actions`**

```js
        <div class="deck-actions">
          ${consideringBtnHtml}
          <button class="deck-cmd-btn${card.is_commander ? ' active' : ''}" title="Toggle commander">♛</button>
          <kbd class="deck-kbd-hint" title="Remove focused card">⌫</kbd>
          <button class="deck-remove-btn" title="Remove">×</button>
        </div>
```

This uses the *unconditional* markup + CSS-visibility approach (already established for list view in Task 2), not a `card.id === deckState.focusedCardId ? ... : ''` conditional in the template string. That's a deliberate deviation from a literal reading of the spec's illustrative snippet: `setDeckFocus` (app.js:2099) changes focus by toggling the `.focused` class directly on existing DOM nodes via `classList` — it does **not** rebuild tile/row `innerHTML` on every hover or arrow-key move (that would be a full re-render per keystroke/hover, which the codebase deliberately avoids — see `setDeckFocus`'s own implementation). A conditional baked into `innerHTML` would only reflect the focus state at the moment the tile was *built*, then go stale (badge stuck on whichever card was focused at build time) every time focus changes afterward without a full `renderDeckContent()`. Making the badge always-present in markup and toggling its visibility purely via the already-correct `.focused` class (CSS added in Task 2 Step 2) produces the behavior the acceptance criteria actually describe — appears/disappears as focus moves — using the mechanism this codebase already relies on for the `.focused` outline/background styling itself (style.css:791, 919).

- [x] **Step 2: Syntax-check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit code 0.

- [x] **Step 3: Confirm the CSS from Task 2 Step 2 already covers this tile**

Re-read `static/style.css` around the rule added in Task 2 Step 2:

```css
.deck-kbd-hint { display: none; }
.deck-card-tile.focused .deck-kbd-hint,
.deck-text-row.focused .deck-kbd-hint { display: inline-block; }
```

`.deck-card-tile.focused` is exactly the class `buildDeckCardTile` already applies (app.js:2113: `(card.id === deckState.focusedCardId ? ' focused' : '')`) and that `setDeckFocus` toggles at runtime — no further CSS change needed.

- [x] **Step 4: Manually trace against acceptance criteria**

- On initial render, the grid tile whose `card.id === deckState.focusedCardId` has class `focused` (existing logic, app.js:2113, unchanged) → its `.deck-kbd-hint` is visible; every other tile's badge is `display: none`.
- On hover, `setDeckFocus(card.id, div)` (app.js:2151, unchanged) removes `.focused` from whichever tile/row had it and adds it to the newly-hovered one (app.js:2101-2103) → the badge visually moves with focus, in both grid and list view, without any re-render.
- On arrow-key nav, `handleDeckColumnNavKey` → `setDeckFocus` (app.js:2252) — same mechanism, same result.
- Badge appears "next to the remove button" in both views: grid places it directly before `.deck-remove-btn` inside `.deck-actions` (Task 4 Step 1); list view places it directly before `.deck-remove-btn` at the end of the row (Task 2 Step 1).

- [x] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: show Backspace-removal hint badge on focused deck card"
```

---

### Task 5: Full regression pass

**Files:** none (verification only)

- [x] **Step 1: Run the full existing JS test suite**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; /opt/homebrew/bin/node "$f" || exit 1; done`
Expected: every file prints its passing test output; script exits 0. (None of these tests touch the functions this plan modifies — this is a pure regression check that nothing else broke.)

- [x] **Step 2: Run the Python test suite**

Run: `python3 -m pytest -q`
Expected: all tests pass. (This plan makes no backend/API changes, so this is a regression check only.)

- [x] **Step 3: Final syntax check of the full file**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit code 0.

- [x] **Step 4: Walk every acceptance criterion from the spec one more time against the final diff**

Run: `git diff main --stat` then `git diff main` to review the complete set of changes across all four tasks together, and re-check each bullet in the spec's "## Acceptance criteria" section:

1. Deck-page modal (grid or list) shows no collection stepper; Cards/Collection page modals unchanged — Task 1.
2. List view rows show a working × remove button — Task 2.
3. `Backspace` removes the focused card in either view; no-op while typing in a field — Task 3.
4. `⌫` badge shows only on the focused card, in both views, and moves with focus — Task 2 + Task 4.
5. Keyboard/list-view removal updates deck count and preview panel the same way the grid × button does — Task 2 Step 1 and Task 3 Step 1 both call the shared `removeDeckCard`.
6. Cards/Collection page tile-level +/− controls unaffected — nothing in this plan touches `buildCardTile` (app.js:630) or the Cards/Collection page render paths.

- [x] **Step 5: Commit if Step 4 turned up any final fixups (otherwise nothing to commit — this task is verification-only)**
