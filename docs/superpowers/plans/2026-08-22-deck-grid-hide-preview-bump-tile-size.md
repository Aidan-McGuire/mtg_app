# Deck Grid View: Hide Preview Panel, Bump Tile Size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Deck page, hide the hover/focus preview panel while in grid view (redundant with tile art) and use the freed width to enlarge grid tiles from 240px to 280px minimum. Text view is unaffected.

**Architecture:** One JS change (`renderDeckContent` in `static/app.js`) toggles a `.hidden` class on `#deck-preview-panel` alongside its existing grid/text view toggling. Two CSS rules (`.deck-grid-view` and a new `#deck-grid-view .group-body` override) bump the tile minimum width. `.deck-content-col`'s existing `flex: 1` already absorbs the freed space when the panel is hidden, so no other layout CSS changes are needed.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), plain CSS (`static/style.css`), static HTML (`static/index.html`, unchanged). Frontend unit tests are plain Node scripts under `tests/js/` that extract sentinel-comment-delimited pure functions out of `static/app.js` via string slicing + `new Function(...)` and run under plain `node` (see `tests/js/apply-filters.test.mjs`). `renderDeckContent` is DOM-wiring (reads `deckState`, mutates the live DOM), not a pure function, and has no sentinel-comment block — consistent with the rest of `static/app.js`'s render functions, it has no unit test coverage. Verification for this plan is: (a) `node --check static/app.js` for syntax, (b) the full existing `tests/js/*.test.mjs` + `pytest` suites staying green (regression check — nothing in this plan touches code any existing test covers), and (c) a live browser check via `mcp__claude-in-chrome__*` tools against the running `uvicorn` dev server, walking every acceptance criterion in the spec.

**Spec:** `docs/superpowers/backlog/008-deck-grid-view-hide-preview-bump-tile-size.md`

## Global Constraints

- Hide `#deck-preview-panel` only while `deckState.deckView === 'grid'`. Text view keeps it visible and behaving exactly as today.
- Leave `renderDeckPreviewPanel()`, `setDeckFocus`, hover handlers, and `deckState.focusedCardId` completely unchanged — they keep running and updating the panel's content even while it's hidden in grid view.
- `.deck-grid-view`'s own rule: `minmax(240px, 1fr)` → `minmax(280px, 1fr)`.
- The shared `.group-body` rule (used by both Deck and Collection grouped views) must NOT change its 240px minimum — add a `#deck-grid-view`-scoped override instead, so Collection's grouped tiles are untouched.
- No changes to Collection page tile sizing (ungrouped or grouped), or to the preview panel's own width/content/focus-tracking logic.

---

### Task 1: Hide the preview panel in grid view

**Files:**
- Modify: `static/app.js:1975-1996` (`renderDeckContent`)

**Interfaces:**
- Consumes: `deckState.deckView` (existing), `document.getElementById('deck-preview-panel')` (existing DOM element, id already present in `static/index.html`).
- Produces: `#deck-preview-panel` carries the `.hidden` class whenever `deckState.deckView === 'grid'`, and never carries it in text view. Task 3's live browser check verifies this end to end.

- [ ] **Step 1: Edit `renderDeckContent`**

In `static/app.js`, change:

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
```

to:

```js
  const previewPanel = document.getElementById('deck-preview-panel');
  if (deckState.deckView === 'grid') {
    renderDeckGrid();
    document.getElementById('deck-grid-view').classList.remove('hidden');
    document.getElementById('deck-text-view').classList.add('hidden');
    previewPanel.classList.add('hidden');
  } else {
    renderDeckText();
    document.getElementById('deck-text-view').classList.remove('hidden');
    document.getElementById('deck-grid-view').classList.add('hidden');
    previewPanel.classList.remove('hidden');
  }
  renderDeckPreviewPanel();
```

- [ ] **Step 2: Syntax-check and run full suites**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: syntax check passes silently; every `.test.mjs` file prints its all-passing summary; pytest reports all tests passing. (Regression check only — `renderDeckContent` has no existing unit coverage; new-behavior verification happens live in Task 3.)

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat(deck): hide preview panel while in grid view"
```

---

### Task 2: Enlarge grid tiles

**Files:**
- Modify: `static/style.css:769-775` (`.deck-grid-view`)
- Modify: `static/style.css:1201-1207` (`.group-body`) — add a new scoped override immediately after this rule, do not edit the shared rule itself

**Interfaces:**
- Consumes: none (pure CSS constant change).
- Produces: `.deck-grid-view` and any `.group-body` rendered inside `#deck-grid-view` (by `renderGroupedGrid`, called when `deckState.groupBy !== 'none'`) use a 280px tile minimum. `#collection-grid .group-body` (Collection's grouped views) keeps the unchanged 240px minimum from the shared rule, since the new override is scoped to `#deck-grid-view` only.

- [ ] **Step 1: Bump the ungrouped deck grid's tile minimum**

In `static/style.css`, change:

```css
.deck-grid-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  grid-auto-rows: max-content;
  gap: 10px;
  align-items: start;
}
```

to:

```css
.deck-grid-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  grid-auto-rows: max-content;
  gap: 10px;
  align-items: start;
}
```

- [ ] **Step 2: Add a scoped override for grouped deck grids**

In `static/style.css`, immediately after the `.group-body.collapsed { display: none; }` rule (currently line 1208), add:

```css
#deck-grid-view .group-body {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
```

- [ ] **Step 3: Verify the Collection page's grouped rule is untouched**

Run: `grep -n "group-body" static/style.css`
Expected: the shared `.group-body { ... minmax(240px, 1fr) ... }` rule (~line 1201-1207) is unchanged; only the new `#deck-grid-view .group-body` rule after it sets 280px.

- [ ] **Step 4: Syntax-check and run full suites**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green (pure CSS change, no test file covers pixel widths — regression check only).

- [ ] **Step 5: Commit**

```bash
git add static/style.css
git commit -m "style(deck): enlarge grid tiles to 280px min in grid view"
```

---

### Task 3: Live browser verification against every acceptance criterion

**Files:** none (verification only; may produce fix commits if a criterion fails)

**Interfaces:**
- Consumes: Task 1 and Task 2's changes.
- Produces: confirmation that every acceptance criterion in `docs/superpowers/backlog/008-deck-grid-view-hide-preview-bump-tile-size.md` holds against the running app.

- [ ] **Step 1: Start the dev server if not already running**

`uvicorn app:app --reload` (background it or use a separate terminal).

- [ ] **Step 2: Walk every acceptance criterion using `mcp__claude-in-chrome__*` tools**

Navigate to the local app's Deck page, open a deck with several cards (including at least one grouped-by-type or grouped-by-tag deck if `groupBy` isn't already `none`), and confirm:

1. In grid view, the preview panel (`#deck-preview-panel`) is not visible and the card grid occupies the full width of `.deck-editor-body`.
2. Switch to text view: the preview panel reappears immediately, showing whatever card is currently focused/hovered (hover a row first, then switch, to confirm it reflects the right card without needing a fresh hover).
3. Switch back to grid view: the panel hides again.
4. In grid view, card tiles are noticeably larger than before (~280px minimum vs. the old ~240px) — check both the ungrouped grid and at least one grouped-by-type and grouped-by-tag section (cycle `groupBy` to confirm each).
5. In text view, hovering/clicking a row still updates the preview panel exactly as before this change.
6. Navigate to the Collection page: its ungrouped grid and grouped (tag, and type if item 007 has landed) tile sizes are visually unchanged from before this change.

If any step fails, fix the underlying code (not the test) and re-run Task 1 Step 2 / Task 2 Step 4 before re-verifying.

- [ ] **Step 3: Run the full suites one final time**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green.

- [ ] **Step 4: Update the backlog item's acceptance criteria checkboxes**

Edit `docs/superpowers/backlog/008-deck-grid-view-hide-preview-bump-tile-size.md`, checking off every `- [ ]` under "## Acceptance criteria" that was just verified live in Step 2 (all seven should now be satisfied).

```bash
git add docs/superpowers/backlog/008-deck-grid-view-hide-preview-bump-tile-size.md
git commit -m "docs(backlog): check off item 008 acceptance criteria"
```
