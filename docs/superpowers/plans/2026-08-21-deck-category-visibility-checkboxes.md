# Deck Page Category Visibility Checkboxes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace click-to-collapse for the deck page's grouped views (type / collection-tag / deck-tag) with a toolbar "Categories" checkbox panel that fully removes unchecked categories from the DOM, per-mode and independent of the Collection page's own (unchanged) click-to-collapse grouping.

**Architecture:** Add a new per-mode `deckHiddenCategories` state object (keyed by `groupBy`) alongside the existing `deckGroupCollapsed` Set. Filter groups against the active mode's hidden set before handing them to the existing render helpers. Convert `renderGroupSection`/`renderGroupedGrid`'s last parameter from a bare `collapsedState` Set to an `opts` object so the click-to-collapse chevron/reorder behavior becomes opt-in — the Collection page and the ungrouped deck view's "Considering" section keep passing `collapsedState` and are visually/behaviorally unchanged; the deck page's grouped views instead pre-filter their group list and pass no `collapsedState`. A new toolbar button+panel (mirroring the existing Filters button/panel pattern) toggles entries in the active mode's hidden set and re-renders.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), plain CSS (`static/style.css`), static HTML (`static/index.html`). Frontend unit tests are plain Node scripts under `tests/js/` that extract a sentinel-delimited pure function out of `static/app.js` via string slicing + `new Function(...)` (see `tests/js/sort-groups-by-collapsed.test.mjs`) — there is no DOM/jsdom harness, so DOM-wiring/rendering changes in this plan are verified by (a) `node --check static/app.js` for syntax, (b) the full existing `tests/js/*.test.mjs` + `pytest` suites staying green (regression coverage for the pure functions this touches: `sortGroupsByCollapsed`, `groupCardsByType`, `extractCommanderGroup`), and (c) careful line-by-line review of the new/changed DOM code against every acceptance criterion in the spec, since no human or browser-automation tool is available in this run to click through the UI manually.

**Spec:** `docs/superpowers/backlog/004-deck-category-visibility-checkboxes.md`

## Global Constraints

- Do NOT change the Collection page's grouped-by-tag view (`renderCollectionGrid` / `collectionGroupCollapsed`) — its click-to-collapse behavior must be pixel-for-pixel unchanged.
- Do NOT change the deck page's ungrouped view's trailing "Considering" section — it keeps click-to-collapse via `deckGroupCollapsed`/`resetDeckGroupCollapsed`, collapsed by default.
- No localStorage/persistence — hidden-category state lives only in memory, resets to all-visible on every deck (re)load, same lifecycle as today's `deckGroupCollapsed` reset in `selectDeck`.
- Hidden-category state is **independent per `groupBy` mode** and must NOT reset when `groupBy` changes (unlike `deckGroupCollapsed`, which continues to reset on every `groupBy` change for its own unrelated purpose).
- No "show all"/"hide all" bulk toggle — per-category checkboxes only.
- Hiding lands specifically and the `notes.md` idea about default land tagging are both out of scope for this item.

---

## Current-state reference (read before starting)

All of the following were verified against the current file contents as of this plan's authoring — line numbers may drift by a few lines if earlier tasks in this plan shift them, so re-`grep` if a line number below doesn't match:

- `static/app.js:1351-1357` — `collectionGroupCollapsed`, `deckGroupCollapsed`, `resetDeckGroupCollapsed()`.
- `static/app.js:1458-1505` — `renderGroupSection(container, group, buildTileFn, collapsedState, allGroups = [group])` and `renderGroupedGrid(container, groups, buildTileFn, collapsedState)`.
- `static/app.js:1589` — Collection grid call site: `renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), collectionGroupCollapsed);`
- `static/app.js:1876-1904` — `selectDeck(id)`; `resetDeckGroupCollapsed()` is called at line 1883.
- `static/app.js:1948-1967` — `renderDeckContent()`.
- `static/app.js:1969-2012` — `renderDeckGrid()`; grouped branch at 1981-1987, ungrouped branch's Considering section at 1997-2010.
- `static/app.js:2086-2126` — `renderDeckText()`; grouped branch at 2101-2107, ungrouped branch's Considering section at 2117-2124.
- `static/app.js:1405-1411` — `groupMainCardsForRender(mainCards, groupBy)` (shared grouping logic, reused by the new toolbar control to compute the full category list).
- `static/app.js:2557-2561` — the `#deck-group-by` `change` listener; calls `resetDeckGroupCollapsed()` then `renderDeckContent()`. Do NOT add `resetDeckHiddenCategories()` here.
- `static/app.js:382-385` — `buildFilterControls` sets `container.className = 'filter-bar'` on its container; this plan's new toolbar control follows the same pattern so it participates in the existing `.filter-bar`-scoped outside-click-closes-panel handling for free.
- `static/app.js:1203` and `static/app.js:1274` — the Escape-key and outside-click panel-closing logic, both matching on `.filter-panel:not(.hidden)`.
- `static/index.html:64-79` — `.deck-editor-acts`, containing `#deck-group-by` (line 68) and `#deck-filter-controls` (line 74).
- `static/style.css:1209-1226` — `.filter-bar`, `.filter-panel`, `.filter-panel.hidden`, `.check-pill` (all reused as-is or extended by selector list, no duplication).
- `static/style.css:760` — `.deck-empty-msg` (reused for the all-hidden empty state).

---

### Task 1: Per-mode hidden-category state

**Files:**
- Modify: `static/app.js:1351-1357` (add new state next to `deckGroupCollapsed`)
- Modify: `static/app.js:1883` (`selectDeck`, add reset call)

**Interfaces:**
- Produces: `deckHiddenCategories` — object `{ type: Set<string>, 'collection-tag': Set<string>, 'deck-tag': Set<string> }`, keyed by the exact string values `deckState.groupBy` takes (confirm against `static/index.html:70-72` option values `type`/`collection-tag`/`deck-tag`).
- Produces: `resetDeckHiddenCategories()` — clears all three sets, no return value.

- [ ] **Step 1: Add the state and reset function**

In `static/app.js`, immediately after the existing `resetDeckGroupCollapsed` function (currently lines 1354-1357), add:

```js
const deckHiddenCategories = { type: new Set(), 'collection-tag': new Set(), 'deck-tag': new Set() };

function resetDeckHiddenCategories() {
  for (const key of Object.keys(deckHiddenCategories)) deckHiddenCategories[key].clear();
}
```

- [ ] **Step 2: Wire the reset into `selectDeck`**

In `static/app.js`, in `selectDeck` (around line 1883), directly after the existing `resetDeckGroupCollapsed();` call, add:

```js
  resetDeckGroupCollapsed();              // Considering starts collapsed for every freshly loaded deck
  resetDeckHiddenCategories();            // every category starts visible for every freshly loaded deck
```

- [ ] **Step 3: Verify syntax**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat(deck): add per-mode hidden-category state"
```

---

### Task 2: Make click-to-collapse optional in the shared render helpers

**Files:**
- Modify: `static/app.js:1458-1505` (`renderGroupSection`, `renderGroupedGrid`)
- Modify: `static/app.js:1589` (Collection grid call site)
- Modify: `static/app.js:1997-2010` (deck grid, ungrouped branch's Considering section — NOT the grouped branch, that's Task 3)
- Modify: `static/app.js:2117-2124` (deck text, ungrouped branch's Considering section — NOT the grouped branch, that's Task 3)

**Interfaces:**
- Consumes: nothing new from Task 1.
- Produces: `renderGroupSection(container, group, buildTileFn, opts = {}, allGroups = [group])` — `opts.collapsedState` (optional `Set<string>`) replaces the old bare 4th param. When `opts.collapsedState` is falsy: no chevron span, no click handler, `isCollapsed` is always `false`.
- Produces: `renderGroupedGrid(container, groups, buildTileFn, opts = {})` — `opts.collapsedState` (optional). When falsy, groups render in their given order (no `sortGroupsByCollapsed` reordering) and `renderGroupSection` is called with `opts` (so no click-to-collapse).
- Later tasks (Task 3, Task 4) rely on being able to call `renderGroupedGrid(el, visibleGroups, buildFn, {})` for the deck page's grouped views with no collapse behavior.

- [ ] **Step 1: Rewrite `renderGroupSection` to take an opts object**

In `static/app.js`, replace the current `renderGroupSection` function (lines 1458-1499) with:

```js
function renderGroupSection(container, group, buildTileFn, opts = {}, allGroups = [group]) {
  const { collapsedState } = opts;
  const section = document.createElement('div');
  section.className = 'group-section';
  section.dataset.label = group.label;

  const isCollapsed = collapsedState ? collapsedState.has(group.label) : false;
  const header = document.createElement('div');
  header.className = 'group-header' + (isCollapsed ? ' collapsed' : '');
  header.innerHTML = `
    <span class="group-header-label">${esc(group.label)}</span>
    <span class="group-header-count">${group.cards.length}</span>
    ${collapsedState ? '<span class="group-header-chevron">▾</span>' : ''}`;
  if (collapsedState) {
    header.addEventListener('click', () => {
      if (collapsedState.has(group.label)) {
        collapsedState.delete(group.label);
      } else {
        collapsedState.add(group.label);
      }
      header.classList.toggle('collapsed');
      body.classList.toggle('collapsed');

      const ordered = sortGroupsByCollapsed(allGroups, collapsedState);
      const idx = ordered.findIndex(g => g.label === group.label);
      const nextLabel = ordered[idx + 1]?.label;
      const nextEl = nextLabel
        ? container.querySelector(`:scope > .group-section[data-label="${CSS.escape(nextLabel)}"]`)
        : null;
      if (section.nextElementSibling !== nextEl) {
        if (nextEl) container.insertBefore(section, nextEl);
        else container.appendChild(section);
      }
    });
  }

  const body = document.createElement('div');
  body.className = 'group-body' + (isCollapsed ? ' collapsed' : '');

  for (const card of group.cards) body.appendChild(buildTileFn(card));

  section.appendChild(header);
  section.appendChild(body);
  container.appendChild(section);
}
```

(This preserves the exact click-handler body from today's implementation — only the parameter shape and the two `collapsedState` guards are new.)

- [ ] **Step 2: Rewrite `renderGroupedGrid` to take an opts object**

Immediately below, replace the current `renderGroupedGrid` function (lines 1501-1505) with:

```js
function renderGroupedGrid(container, groups, buildTileFn, opts = {}) {
  container.innerHTML = '';
  const ordered = opts.collapsedState ? sortGroupsByCollapsed(groups, opts.collapsedState) : groups;
  for (const group of ordered) renderGroupSection(container, group, buildTileFn, opts, groups);
}
```

- [ ] **Step 3: Update the Collection grid call site**

In `static/app.js` around line 1589, change:

```js
    renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), collectionGroupCollapsed);
```

to:

```js
    renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), { collapsedState: collectionGroupCollapsed });
```

- [ ] **Step 4: Update the deck-grid ungrouped Considering call site**

In `static/app.js`, in `renderDeckGrid` (around lines 1997-2003), change:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        deckGroupCollapsed
      );
```

to:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        { collapsedState: deckGroupCollapsed }
      );
```

- [ ] **Step 5: Update the deck-text ungrouped Considering call site**

In `static/app.js`, in `renderDeckText` (around lines 2117-2123), change:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckTextRow,
        deckGroupCollapsed
      );
```

to:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckTextRow,
        { collapsedState: deckGroupCollapsed }
      );
```

- [ ] **Step 6: Verify syntax**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 7: Run existing JS unit tests (regression check)**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done`
Expected: every file prints `all N checks passing` (or equivalent all-ok summary), exit code 0. (`sort-groups-by-collapsed.test.mjs` and `group-cards-by-type.test.mjs` are the ones whose functions this task's neighbors touch; none of `renderGroupSection`/`renderGroupedGrid` themselves are under test since they're DOM-wiring, not pure functions — this is expected and matches the file list, not a gap introduced by this task.)

- [ ] **Step 8: Commit**

```bash
git add static/app.js
git commit -m "refactor(deck): make renderGroupSection/renderGroupedGrid collapse behavior opt-in via opts object"
```

At this point the deck page's *grouped* branches (`renderDeckGrid`/`renderDeckText`, `deckState.groupBy !== 'none'`) still pass a bare `deckGroupCollapsed` Set as the 4th positional argument, which is now interpreted as `opts` — i.e. `opts.collapsedState` will be `undefined` (since a Set has no `.collapsedState` property), so those branches will silently lose click-to-collapse behavior at the end of this task. That's fine: Task 3 rewrites those two call sites entirely (filtering + no collapse) before this is user-visible in any committed, "done" state, and each task is independently syntax/test-verified. If this plan is ever paused between Task 2 and Task 3, the grouped deck views would render un-collapsible but otherwise correctly (no crash — `opts.collapsedState` undefined is handled by both functions) until Task 3 lands.

---

### Task 3: Filter hidden groups before rendering (deck grid + deck text)

**Files:**
- Modify: `static/app.js:1969-2012` (`renderDeckGrid`)
- Modify: `static/app.js:2086-2126` (`renderDeckText`)

**Interfaces:**
- Consumes: `deckHiddenCategories` (Task 1), `renderGroupedGrid(container, groups, buildTileFn, opts = {})` (Task 2).
- Produces: both functions now render a `deck-empty-msg` when every group in the current mode is hidden, instead of an empty grid/text area.

- [ ] **Step 1: Update `renderDeckGrid`'s grouped branch**

In `static/app.js`, in `renderDeckGrid`, replace:

```js
  if (deckState.groupBy !== 'none') {
    const groups = groupMainCardsForRender(mainCards, deckState.groupBy);
    for (const g of groups) g.cards.sort(cmp);
    if (consideringCards.length) {
      groups.push({ label: 'Considering', cards: [...consideringCards].sort(cmp) });
    }
    renderGroupedGrid(el, groups, buildDeckCardTile, deckGroupCollapsed);
  } else {
```

with:

```js
  if (deckState.groupBy !== 'none') {
    const groups = groupMainCardsForRender(mainCards, deckState.groupBy);
    for (const g of groups) g.cards.sort(cmp);
    if (consideringCards.length) {
      groups.push({ label: 'Considering', cards: [...consideringCards].sort(cmp) });
    }
    const hidden = deckHiddenCategories[deckState.groupBy];
    const visibleGroups = groups.filter(g => !hidden.has(g.label));
    if (!visibleGroups.length) {
      el.innerHTML = '<div class="deck-empty-msg">All categories hidden — check a category above to show cards.</div>';
      return;
    }
    renderGroupedGrid(el, visibleGroups, buildDeckCardTile, {});
  } else {
```

- [ ] **Step 2: Update `renderDeckText`'s grouped branch**

In `static/app.js`, in `renderDeckText`, replace:

```js
  if (deckState.groupBy !== 'none') {
    const groups = groupMainCardsForRender(mainCards, deckState.groupBy);
    for (const g of groups) g.cards.sort(cmp);
    if (consideringCards.length) {
      groups.push({ label: 'Considering', cards: [...consideringCards].sort(cmp) });
    }
    renderGroupedGrid(el, groups, buildDeckTextRow, deckGroupCollapsed);
  } else {
```

with:

```js
  if (deckState.groupBy !== 'none') {
    const groups = groupMainCardsForRender(mainCards, deckState.groupBy);
    for (const g of groups) g.cards.sort(cmp);
    if (consideringCards.length) {
      groups.push({ label: 'Considering', cards: [...consideringCards].sort(cmp) });
    }
    const hidden = deckHiddenCategories[deckState.groupBy];
    const visibleGroups = groups.filter(g => !hidden.has(g.label));
    if (!visibleGroups.length) {
      el.innerHTML = '<div class="deck-empty-msg">All categories hidden — check a category above to show cards.</div>';
      return;
    }
    renderGroupedGrid(el, visibleGroups, buildDeckTextRow, {});
  } else {
```

- [ ] **Step 3: Verify syntax**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 4: Run existing JS unit tests (regression check)**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done`
Expected: all pass, exit code 0.

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat(deck): filter hidden categories out of grouped grid/text rendering"
```

---

### Task 4: Toolbar "Categories" checkbox panel

**Files:**
- Modify: `static/index.html` (add container div inside `.deck-editor-acts`)
- Modify: `static/app.js` (new `renderDeckCategoryControls` function; wire into `renderDeckContent`; extend Escape/outside-click selectors)
- Modify: `static/style.css` (extend `.filter-panel`/`.filter-panel.hidden` selectors to cover `.categories-panel`)

**Interfaces:**
- Consumes: `deckHiddenCategories` (Task 1), `groupMainCardsForRender` (existing, `static/app.js:1405`), `deckState.deckCards`/`deckState.groupBy` (existing globals).
- Produces: `renderDeckCategoryControls()` — no params, no return value; reads/writes `deckHiddenCategories[deckState.groupBy]` and rebuilds `#deck-category-controls`'s contents. Called once per render from `renderDeckContent()`.

- [ ] **Step 1: Add the toolbar container to `index.html`**

In `static/index.html`, inside `.deck-editor-acts` (currently lines 64-79), immediately after the `#deck-group-by` `<select>` (line 68-73) and before `<div id="deck-filter-controls"></div>` (line 74), add:

```html
                <div id="deck-category-controls"></div>
```

- [ ] **Step 2: Add `renderDeckCategoryControls` to `app.js`**

In `static/app.js`, immediately after the `renderDeckContent` function definition (currently ending at line 1967, right before `renderDeckGrid`), add:

```js
function renderDeckCategoryControls() {
  const container = document.getElementById('deck-category-controls');
  container.className = 'filter-bar';
  if (deckState.groupBy === 'none') { container.innerHTML = ''; return; }

  const mainCards = deckState.deckCards.filter(c => !c.is_considering);
  const groups = groupMainCardsForRender(mainCards, deckState.groupBy);
  if (deckState.deckCards.some(c => c.is_considering)) groups.push({ label: 'Considering', cards: [] });

  const hidden = deckHiddenCategories[deckState.groupBy];
  container.innerHTML = '';

  const btn = document.createElement('button');
  btn.className = 'categories-btn action-btn';
  btn.textContent = 'Categories';
  const panel = document.createElement('div');
  panel.className = 'categories-panel hidden';
  btn.addEventListener('click', () => panel.classList.toggle('hidden'));

  for (const g of groups) {
    const lab = document.createElement('label');
    lab.className = 'check-pill';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = !hidden.has(g.label);
    cb.addEventListener('change', () => {
      if (cb.checked) hidden.delete(g.label); else hidden.add(g.label);
      renderDeckContent();
    });
    lab.appendChild(cb);
    lab.appendChild(document.createTextNode(g.label));
    panel.appendChild(lab);
  }

  container.appendChild(btn);
  container.appendChild(panel);
}
```

Note: `container.className = 'filter-bar'` (not a new class) is deliberate — it reuses the existing `.filter-bar { position: relative }` CSS and, more importantly, makes this container satisfy the existing outside-click-closes-panel guard at `static/app.js:1272-1276`, which only closes panels when the click target is *outside* `.filter-bar`. Without this, clicking a checkbox inside `.categories-panel` would immediately close the panel via that handler, since `#deck-category-controls` would otherwise be outside any `.filter-bar`-classed ancestor.

- [ ] **Step 3: Call it from `renderDeckContent`**

In `static/app.js`, in `renderDeckContent` (currently lines 1948-1967), add a call right after the deck name/total block and before the `if (deckState.deckView === 'grid')` branch:

```js
  document.getElementById('deck-editor-name').textContent =
    deck ? `${deck.name} (${total})` : `(${total})`;

  renderDeckCategoryControls();

  if (deckState.deckView === 'grid') {
```

- [ ] **Step 4: Extend the Escape-key panel-closing selector**

In `static/app.js`, at line 1203, change:

```js
    const openPanel = document.querySelector('.filter-panel:not(.hidden)');
```

to:

```js
    const openPanel = document.querySelector('.filter-panel:not(.hidden), .categories-panel:not(.hidden)');
```

- [ ] **Step 5: Extend the outside-click panel-closing selector**

In `static/app.js`, at line 1274, change:

```js
    document.querySelectorAll('.filter-panel:not(.hidden)').forEach(p => p.classList.add('hidden'));
```

to:

```js
    document.querySelectorAll('.filter-panel:not(.hidden), .categories-panel:not(.hidden)').forEach(p => p.classList.add('hidden'));
```

- [ ] **Step 6: Add `.categories-panel` to the reused filter-panel CSS**

In `static/style.css`, at line 1215-1219, change:

```css
.filter-panel { position: absolute; top: 110%; left: 0; z-index: 20;
  background: #1e1e24; border: 1px solid #444; border-radius: 6px; padding: 12px;
  display: flex; flex-direction: column; gap: 10px; min-width: 340px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4); }
.filter-panel.hidden { display: none; }
```

to:

```css
.filter-panel, .categories-panel { position: absolute; top: 110%; left: 0; z-index: 20;
  background: #1e1e24; border: 1px solid #444; border-radius: 6px; padding: 12px;
  display: flex; flex-direction: column; gap: 10px; min-width: 340px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4); }
.filter-panel.hidden, .categories-panel.hidden { display: none; }
```

(`.check-pill` and `.action-btn` are reused unmodified — no new CSS needed for those.)

- [ ] **Step 7: Verify syntax**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 8: Run existing JS unit tests (regression check)**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done`
Expected: all pass, exit code 0.

- [ ] **Step 9: Commit**

```bash
git add static/index.html static/app.js static/style.css
git commit -m "feat(deck): add Categories toolbar checkbox panel for per-mode category visibility"
```

---

### Task 5: Full verification against acceptance criteria

**Files:** none (verification only — read-only review + test runs).

- [ ] **Step 1: Run the full automated test suite**

Run: `python3 -m pytest -q && for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done`
Expected: all pytest tests pass; every `.test.mjs` file prints its all-passing summary; exit code 0 overall.

- [ ] **Step 2: Static review against each acceptance criterion**

No browser automation tool is available in this environment, so confirm each criterion by reading the final state of the touched code (not by re-deriving intent from the spec):

  - "Categories" button/panel appears for `type`/`collection-tag`/`deck-tag`, not for `none` — confirm via the `if (deckState.groupBy === 'none') { container.innerHTml = ''; return; }` guard in `renderDeckCategoryControls`.
  - All checkboxes checked by default on a fresh deck load — confirm `resetDeckHiddenCategories()` runs in `selectDeck` (Task 1) and `cb.checked = !hidden.has(g.label)` reads an empty Set right after.
  - Unchecking removes the whole section immediately, no reorder artifact, no lingering header — confirm `visibleGroups = groups.filter(...)` (Task 3) means hidden groups are never passed into `renderGroupedGrid`/`renderGroupSection` at all, so no DOM node for them is created.
  - Re-checking restores natural order — confirm `visibleGroups` preserves `groups`' original order (a `.filter()`, not a re-sort), and `renderGroupedGrid` with `opts.collapsedState` falsy renders `ordered = groups` as-is (Task 2 Step 2).
  - Independent state per mode, including same-named categories (e.g. "Commander") — confirm `deckHiddenCategories` is keyed by `deckState.groupBy` (three separate `Set`s), so `.type`'s "Commander" entry is a different Set entry than `['collection-tag']`'s.
  - All-hidden empty state shows a message, not a blank area — confirm the `if (!visibleGroups.length) { ...deck-empty-msg...; return; }` branches in both `renderDeckGrid` and `renderDeckText` (Task 3).
  - Ungrouped "Considering" section still collapsed-by-default with working click-to-collapse — confirm its call sites still pass `{ collapsedState: deckGroupCollapsed }` (Task 2 Steps 4-5) and `deckGroupCollapsed` still seeds `'Considering'` (untouched Task 1 code).
  - Collection page's `Group: Tag` view still click-to-collapse — confirm its call site still passes `{ collapsedState: collectionGroupCollapsed }` (Task 2 Step 3) and nothing in `renderCollectionGrid` was touched.
  - Reload/switch-deck-and-back resets every mode to all-visible — confirm `resetDeckHiddenCategories()` in `selectDeck` (Task 1 Step 2).
  - Switching `groupBy` away and back preserves hide/show choices within a session — confirm the `#deck-group-by` `change` listener (`static/app.js:2557-2561`) was NOT modified to call `resetDeckHiddenCategories()`.

- [ ] **Step 3: Fix any criterion that doesn't check out**

If Step 2 surfaces a mismatch, fix it in the relevant task's code, re-run Step 1, and re-verify the specific criterion before proceeding. Do not proceed to Step 4 with a known-failing criterion.

- [ ] **Step 4: Final commit if any fixes were made in Step 3**

```bash
git add -A
git commit -m "fix(deck): address acceptance-criteria review findings for category visibility"
```

(Skip this step entirely if Step 2 found nothing to fix.)
