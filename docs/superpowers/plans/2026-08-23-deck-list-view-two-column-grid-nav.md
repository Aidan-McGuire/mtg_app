# Deck list view two-column grid + shared column-aware nav Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make deck list view (`#deck-text-view`) render cards in a 2-column grid instead of one column, and share grid view's full 2D column-aware arrow-key navigation between both deck views instead of list view having its own simpler (category-jumping) nav.

**Architecture:** Entirely frontend (`static/style.css`, `static/app.js`), no backend/schema changes. CSS: change the `#deck-text-view .group-body` override from a vertical flex column to a 2-column CSS grid (row-major fill), matching the visual model grid view already uses. JS: generalize `handleDeckGridKey` into a container-agnostic `handleDeckColumnNavKey(e, containerId)`, delete the now-redundant `handleDeckListKey`, and point both deck-view branches of the keydown dispatch at the shared function. `deckNavGroups`, `groupColumnCount`, and `findTileIndex` are already container/tile-shape agnostic and need no changes — `groupColumnCount` measures columns from actual rendered layout via `getBoundingClientRect`, so it will correctly detect 2 columns for list view's rows automatically.

**Tech Stack:** Vanilla JS (`static/app.js`), plain CSS (`static/style.css`), no build step. There is no DOM/jsdom test harness in this repo — only pure, dependency-free functions get automated Node tests under `tests/js/` (sentinel-extraction pattern). `handleDeckColumnNavKey` depends on `document`, `deckState`, and sibling functions, so it is out of scope for that harness; it's verified by running the dev server (`uvicorn app:app --reload`) and checking rendered HTML structure via `curl` (for the CSS grid layout) plus careful manual code-trace verification against grid view's existing (already-shipped, unmodified-by-this-plan) navigation logic.

**Spec:** `docs/superpowers/backlog/009-deck-list-view-two-column-grid-nav.md`

## Global Constraints

- No backend changes — do not touch `app.py`, `main.py`, or the DB schema.
- Match existing code style in touched files: 2-space indent, semicolons.
- Fixed 2-column layout for list view — not configurable.
- No change to grid view's own visual layout/column count, or to how categories are computed, hidden, sorted, or collapsed.
- `handleDeckListKey` must no longer exist in `static/app.js` after this plan (spec acceptance criterion).

---

### Task 1: CSS — two-column grid for deck list view group bodies

**Files:**
- Modify: `static/style.css:893-897` (the `#deck-text-view .group-body` rule)

**Interfaces:** None — pure CSS, no JS/HTML interface changes. Grid view's `#deck-grid-view .group-body` rule (style.css:1210) is untouched.

- [ ] **Step 1: Change the rule**

In `static/style.css`, replace:

```css
#deck-text-view .group-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
```

with:

```css
#deck-text-view .group-body {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2px 8px;
}
```

Leave the preceding comment (lines 890-892, explaining why this ID-scoped override exists) and the following `#deck-text-view .group-body.collapsed { display: none; }` rule (line 899) unchanged.

- [ ] **Step 2: Verify row-major fill in the browser**

Start the dev server if not already running: `uvicorn app:app --reload` (from the project root). Open the app, go to the Decks page, select a deck with a list view category that has at least 3 cards (odd count) and one with an even count (or view "All"/whatever category groupings exist), switch to list/text view (the non-grid deck view toggle). Confirm cards lay out in 2 columns, row-major (item 1 top-left, item 2 top-right, item 3 wraps to next row left), for both an odd-count and an even-count category.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "style: deck list view group bodies use a 2-column grid"
```

---

### Task 2: JS — share column-aware nav between grid and list views

**Files:**
- Modify: `static/app.js:2255-2273` (delete `handleDeckListKey`)
- Modify: `static/app.js:2289-2329` (rename/generalize `handleDeckGridKey` into `handleDeckColumnNavKey`)
- Modify: `static/app.js:1262` (dispatch site)

**Interfaces:**
- Consumes (unchanged, already defined earlier in `app.js`): `deckNavGroups(container)` → `Array<Array<Element>>`; `findTileIndex(groups, cardId)` → `{g, i} | null`; `groupColumnCount(tiles)` → `number`; `focusDeckTile(el)`; `deckState.focusedCardId`; `deckState.deckView` (`'grid' | 'list'`, or whatever the non-grid value is — read from the existing ternary at app.js:1262 rather than assumed).
- Produces: `handleDeckColumnNavKey(e, containerId)` — takes the keydown event and the DOM id of the container to navigate within (`'deck-grid-view'` or `'deck-text-view'`), does full 2D grid navigation (Left/Right within a row, Down/Up crossing into the next/previous category at row boundaries, clamped to that category's own column count), calling `e.preventDefault()` and `focusDeckTile(...)` as needed. No other function in this codebase should reference `handleDeckGridKey` or `handleDeckListKey` after this task.

- [ ] **Step 1: Delete `handleDeckListKey`**

In `static/app.js`, delete the entire function at lines 2255-2273:

```js
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

- [ ] **Step 2: Rename `handleDeckGridKey` to `handleDeckColumnNavKey` and parameterize the container id**

Replace the `handleDeckGridKey` function (now a few lines up after Step 1's deletion) — originally:

```js
function handleDeckGridKey(e) {
  const groups = deckNavGroups(document.getElementById('deck-grid-view'));
```

with:

```js
function handleDeckColumnNavKey(e, containerId) {
  const groups = deckNavGroups(document.getElementById(containerId));
```

Leave every other line of the function body (the `isArrow` check, `pos`/`tiles`/`cols`/`col` computation, and all four `ArrowRight`/`ArrowLeft`/`ArrowDown`/`ArrowUp` branches) byte-for-byte unchanged — this is a signature generalization only, not a logic change.

- [ ] **Step 3: Update the dispatch site**

In `static/app.js` at (originally) line 1262, replace:

```js
      if (deckState.deckView === 'grid') handleDeckGridKey(e); else handleDeckListKey(e);
```

with:

```js
      if (deckState.deckView === 'grid') handleDeckColumnNavKey(e, 'deck-grid-view');
      else handleDeckColumnNavKey(e, 'deck-text-view');
```

- [ ] **Step 4: Confirm no leftover references**

```bash
grep -n "handleDeckGridKey\|handleDeckListKey" static/app.js
```

Expected: no output (both names fully removed; only `handleDeckColumnNavKey` remains).

- [ ] **Step 5: Manual verification pass in the browser**

With the dev server running (`uvicorn app:app --reload`), open the Decks page for a deck with at least 2 categories, each with 3+ cards (so both column-crossing and category-crossing paths exercise), and at least one collapsed category, and at least one untagged card (so it falls into an "Untagged" category).

In **grid view** (should be unchanged from before this plan):
- ArrowRight/ArrowLeft move within a row; no-op at row edges.
- ArrowDown/ArrowUp move down/up a column; crossing the last/first row moves into the next/previous category, landing in the same column (clamped to that category's column count).
- Collapsed categories are skipped.

In **list view** (new behavior from this plan):
- ArrowRight/ArrowLeft move focus between the two columns of the same row; no-op (no wrap) at the left/right edge.
- ArrowDown/ArrowUp move down/up a column; crossing the last/first row of a category moves into the next/previous category, landing in the same column (clamped).
- Collapsed categories are skipped.
- The "Untagged" category is reachable via the same nav as any other category.

- [ ] **Step 6: Commit**

```bash
git add static/app.js
git commit -m "refactor: share column-aware deck nav between grid and list views"
```

---

### Task 3: Final acceptance pass

**Files:** None (verification only).

- [ ] **Step 1: Re-check every acceptance criterion from the spec against the running app**

Using the same dev-server session as Task 2 Step 5, walk the full acceptance criteria list in `docs/superpowers/backlog/009-deck-list-view-two-column-grid-nav.md`:
- 2-column row-major grid in list view, for even and odd category card counts.
- List view Left/Right move within a row, no wrap at edges.
- List view Up/Down cross categories at row boundaries, landing in the same (clamped) column — matches grid view exactly.
- Grid view arrow-key behavior is unchanged.
- Untagged cards appear in an "Untagged" category in list view and are nav-reachable.
- Collapsed categories are skipped by nav in both views.
- `handleDeckListKey` no longer exists in `static/app.js` (re-run the grep from Task 2 Step 4).

- [ ] **Step 2: Commit if any fixups were needed**

If Step 1 surfaced no issues, there is nothing to commit here. If it did, fix, re-verify, and commit:

```bash
git add static/app.js static/style.css
git commit -m "fix: address deck list-view nav acceptance gaps"
```
