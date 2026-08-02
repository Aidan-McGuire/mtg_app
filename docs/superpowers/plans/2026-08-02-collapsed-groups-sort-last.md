# Collapsed groups sort to the bottom Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapsing a group in any grouped grid/list (Deck Grid view, Deck Text view, Collection page) moves it after all still-expanded groups, and it stays there across full re-renders — not just at the moment of the click.

**Architecture:** Single shared function change in `static/app.js` (`renderGroupSection`/`renderGroupedGrid`), the component all three grouped views already funnel through. No CSS changes — DOM order already determines visual order in every consumer.

**Tech Stack:** Vanilla JS, no build step.

## Global Constraints

- No backend changes — do not touch `app.py`, `main.py`, or the DB schema.
- Match existing code style: 2-space indent, semicolons, `esc()` for all HTML-interpolated text.
- Follow the approved design spec at `docs/superpowers/specs/2026-08-02-collapsed-groups-sort-last-design.md` exactly — it is the source of truth for behavior if this plan and the spec ever disagree.
- No JS test runner applies here — `renderGroupSection`/`renderGroupedGrid` are DOM-dependent (create/query/move real elements), so per this repo's established convention (sentinel-extraction pattern only covers fully self-contained pure functions with no `document` dependency) this task has no automated test. Verification is manual, in a running browser via `uvicorn app:app --reload`.

---

### Task 1: Collapsed-last ordering in `renderGroupSection`/`renderGroupedGrid`

**Files:**
- Modify: `static/app.js:1378-1412` (`renderGroupSection`, `renderGroupedGrid`)
- Modify: `static/app.js:1872-1877` (deck Grid ungrouped branch's standalone Considering call)
- Modify: `static/app.js:1993-1998` (deck Text ungrouped branch's standalone Considering call)

**Interfaces:**
- `renderGroupSection(container, group, buildTileFn, collapsedState, allGroups)` — gains a required 5th parameter, `allGroups`: the full ordered list of `{label, cards}` group objects this section belongs to (used only to compute where to reinsert the section on toggle). Every existing call site must pass it.
- `renderGroupedGrid(container, groups, buildTileFn, collapsedState)` — signature unchanged; internally now sorts `groups` collapsed-last before building, and passes the *original* (not sorted) `groups` array through to each `renderGroupSection` call as `allGroups`, so `allGroups` always reflects true group order regardless of current collapse state.

- [x] **Step 1: Add `sortGroupsByCollapsed` and update `renderGroupSection`/`renderGroupedGrid`**

In `static/app.js`, replace:

```js
function renderGroupSection(container, group, buildTileFn, collapsedState) {
  const section = document.createElement('div');
  section.className = 'group-section';

  const isCollapsed = collapsedState.has(group.label);
  const header = document.createElement('div');
  header.className = 'group-header' + (isCollapsed ? ' collapsed' : '');
  header.innerHTML = `
    <span class="group-header-label">${esc(group.label)}</span>
    <span class="group-header-count">${group.cards.length}</span>
    <span class="group-header-chevron">▾</span>`;
  header.addEventListener('click', () => {
    if (collapsedState.has(group.label)) {
      collapsedState.delete(group.label);
    } else {
      collapsedState.add(group.label);
    }
    header.classList.toggle('collapsed');
    body.classList.toggle('collapsed');
  });

  const body = document.createElement('div');
  body.className = 'group-body' + (isCollapsed ? ' collapsed' : '');

  for (const card of group.cards) body.appendChild(buildTileFn(card));

  section.appendChild(header);
  section.appendChild(body);
  container.appendChild(section);
}

function renderGroupedGrid(container, groups, buildTileFn, collapsedState) {
  container.innerHTML = '';
  for (const group of groups) renderGroupSection(container, group, buildTileFn, collapsedState);
}
```

with:

```js
/**
 * Expanded groups first (in their original order), then collapsed groups
 * (in their original order) — "minimized categories go to the bottom."
 */
function sortGroupsByCollapsed(groups, collapsedState) {
  const expanded  = groups.filter(g => !collapsedState.has(g.label));
  const collapsed = groups.filter(g => collapsedState.has(g.label));
  return [...expanded, ...collapsed];
}

function renderGroupSection(container, group, buildTileFn, collapsedState, allGroups) {
  const section = document.createElement('div');
  section.className = 'group-section';
  section.dataset.label = group.label;

  const isCollapsed = collapsedState.has(group.label);
  const header = document.createElement('div');
  header.className = 'group-header' + (isCollapsed ? ' collapsed' : '');
  header.innerHTML = `
    <span class="group-header-label">${esc(group.label)}</span>
    <span class="group-header-count">${group.cards.length}</span>
    <span class="group-header-chevron">▾</span>`;
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
      ? container.querySelector(`.group-section[data-label="${CSS.escape(nextLabel)}"]`)
      : null;
    if (nextEl) container.insertBefore(section, nextEl);
    else container.appendChild(section);
  });

  const body = document.createElement('div');
  body.className = 'group-body' + (isCollapsed ? ' collapsed' : '');

  for (const card of group.cards) body.appendChild(buildTileFn(card));

  section.appendChild(header);
  section.appendChild(body);
  container.appendChild(section);
}

function renderGroupedGrid(container, groups, buildTileFn, collapsedState) {
  container.innerHTML = '';
  const ordered = sortGroupsByCollapsed(groups, collapsedState);
  for (const group of ordered) renderGroupSection(container, group, buildTileFn, collapsedState, groups);
}
```

Note `renderGroupedGrid` passes the *original* `groups` (not `ordered`) as `allGroups` to each call — `allGroups` must always reflect true group order so `sortGroupsByCollapsed` inside the click handler computes correctly regardless of how many toggles have happened since the last full render.

- [x] **Step 2: Update the deck Grid ungrouped branch's standalone call**

In `static/app.js`, inside `renderDeckGrid`'s ungrouped (`else`) branch, replace:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        deckGroupCollapsed
      );
```

with:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        deckGroupCollapsed,
        [{ label: 'Considering' }]
      );
```

(A single-element `allGroups` list — there's nothing else to sort this section against, so toggling it is always a no-op reposition, same as it visually already is today.)

- [x] **Step 3: Update the deck Text ungrouped branch's standalone call**

In `static/app.js`, inside `renderDeckText`'s ungrouped (`else`) branch, replace:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckTextRow,
        deckGroupCollapsed
      );
```

with:

```js
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckTextRow,
        deckGroupCollapsed,
        [{ label: 'Considering' }]
      );
```

- [x] **Step 4: Syntax check**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [x] **Step 5: Manual verification**

Run `uvicorn app:app --reload` from the repo root, open `http://localhost:8000`.

*Deck Grid view* — open a deck, set Group-by to "Card type" (or a tag mode) with at least 3 non-empty groups plus at least one card in Considering:
- Collapse the middle group: confirm it instantly moves to sit just before the Considering group (or to the very end if there's no Considering group), with no flicker/reload of the other groups' tiles/images.
- Expand it again: confirm it returns to its original position among the still-expanded groups.
- Collapse two different groups (not adjacent): confirm both end up at the bottom, in their original relative order.
- Change the sort-order dropdown (triggers a full re-render) while a group is still collapsed: confirm it's still at the bottom afterward.
- Increment a card's quantity (another full-re-render trigger): same check.

*Deck Text view* — repeat the same checks (group-by a tag/type mode, collapse/expand, full-re-render persistence).

*Collection page* — group by a collection tag with 3+ groups, repeat the collapse/expand/re-render checks.

*Ungrouped Considering-only case* — in either deck view with Group-by "None" and at least one Considering card: confirm collapsing/expanding the trailing Considering section still works exactly as before (it's the only section, so nothing to reorder against).

- [x] **Step 6: Commit**

```bash
git add static/app.js
git commit -m "feat: sort collapsed groups to the bottom in grouped grids/lists"
```
