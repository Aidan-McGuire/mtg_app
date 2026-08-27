# Group Header Keyboard Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make collapsible `.group-header` elements (rendered by `renderGroupSection` in `static/app.js`) reachable via Tab and toggleable with Enter/Space, matching existing mouse-click behavior, with a visible focus ring and correct `aria-expanded` state.

**Architecture:** Pure frontend change in `static/app.js` (extract the existing click handler body into a named `toggleGroup()` function, add markup attributes and a `keydown` listener, only when `collapsedState` is passed) plus one new CSS rule in `static/style.css` for the focus ring. No backend/API changes.

**Tech Stack:** Vanilla JS (`static/app.js`), plain CSS (`static/style.css`), no build step, no new dependencies. `grep -rn "group-header" tests/` to check for existing JS tests covering this markup before assuming none exist. Verification: `/opt/homebrew/bin/node --check static/app.js` for syntax validity, `python3 -m pytest -q` for backend regression (this item touches no backend code, so this is a pure regression check), and manual code-path tracing against each acceptance criterion (no live browser session required, but use one if available).

**Spec:** `docs/superpowers/backlog/030-group-header-keyboard-toggle.md`

## Global Constraints

- Only headers rendered with `collapsedState` present in `opts` become keyboard-operable (`tabindex`, `role`, `aria-expanded`, `keydown` listener). Headers rendered without `collapsedState` (e.g. `static/app.js:2157` and `:2301`, the per-category deck groups under `groupBy !== 'none'`) must receive none of these additions — verified by inspection since they call `renderGroupedGrid(..., {})` with no `collapsedState` key.
- Toggling via `Enter` or `Space` must produce byte-identical DOM effects to today's click handler: `header.classList.toggle('collapsed')`, `body.classList.toggle('collapsed')`, and the group-reorder-to-end-of-list logic — achieved by literally sharing one function, not by duplicating logic.
- `Space` must call `e.preventDefault()` so the page does not scroll.
- No changes to `handleDeckColumnNavKey`/`deckNavGroups` arrow-key navigation — headers are Tab-reachable only, not part of the custom arrow-nav system.
- New CSS rule is additive only: `.group-header:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }`, matching the existing `.deck-card-tile.focused` convention (`static/style.css:815`).

---

## Current code (reference — read before editing)

`static/app.js:1557-1601` (`renderGroupSection`):
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

Note: the existing click handler references `body`, which is declared with `const` *after* the handler is attached — this works today only because the handler runs later (on click), after `body` has been assigned in the enclosing closure. The refactor must preserve this ordering (declare `toggleGroup` before use is fine since it's a function declaration/expression referencing `body` by closure, but `body` itself must still be declared before either listener can ever fire — trivially true since both listeners are user-triggered, after the whole function has run).

Callers with `collapsedState` (must gain keyboard support): `static/app.js:1693`, `:1697` (Collection grouped grid), `:2172` (deck grid "Considering" section), `:2316` (deck text/list view "Considering" section).

Callers without `collapsedState` (must NOT gain any new attributes/listeners): `static/app.js:2157`, `:2301` (deck grid/list per-category groups when `groupBy !== 'none'`).

`static/style.css:815`: `.deck-card-tile.focused { outline: 2px solid var(--accent); outline-offset: 2px; }` — the focus-ring convention to match.

`static/style.css:1200-1211`:
```css
.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
  color: var(--muted);
}
.group-header:hover { color: var(--text); }
```

---

## Task 1: Make `renderGroupSection` headers keyboard-operable

**Files:**
- Modify: `static/app.js:1557-1601`

**Interfaces:**
- Consumes: nothing new (same `container`, `group`, `buildTileFn`, `opts`, `allGroups` params).
- Produces: no signature change to `renderGroupSection` — callers are unaffected. New behavior is purely inside the function body.

- [ ] **Step 1: Rewrite `renderGroupSection`**

Replace the full function body at `static/app.js:1557-1601` with:

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
    header.setAttribute('tabindex', '0');
    header.setAttribute('role', 'button');
    header.setAttribute('aria-expanded', String(!isCollapsed));

    const toggleGroup = () => {
      if (collapsedState.has(group.label)) {
        collapsedState.delete(group.label);
      } else {
        collapsedState.add(group.label);
      }
      const nowCollapsed = header.classList.toggle('collapsed');
      body.classList.toggle('collapsed');
      header.setAttribute('aria-expanded', String(!nowCollapsed));

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
    };

    header.addEventListener('click', toggleGroup);
    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
        e.preventDefault();
        toggleGroup();
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

Notes on this diff vs. the original:
- `header.classList.toggle('collapsed')` return value is captured as `nowCollapsed` (the toggle method returns the new state) to drive `aria-expanded` — no behavior change to the class itself.
- `' '` is the standard `e.key` value for Space in modern browsers; `'Spacebar'` is kept for older-engine compatibility, matching defensive patterns already acceptable in this codebase (harmless extra check).
- `body` is still declared with `const` after `toggleGroup` is defined and attached — safe because `toggleGroup` is only ever invoked later, asynchronously, from an event, by which point `body` has been assigned (identical timing guarantee as the original code, which had the same forward reference in its click handler).

- [ ] **Step 2: Syntax check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: make group headers keyboard-operable (Tab + Enter/Space)"
```

---

## Task 2: Focus-visible style for `.group-header`

**Files:**
- Modify: `static/style.css:1200-1211`

**Interfaces:**
- Consumes: `var(--accent)` (already defined and used by `.deck-card-tile.focused`).
- Produces: nothing new consumed elsewhere; purely visual.

- [ ] **Step 1: Add the focus-visible rule**

After the existing `.group-header:hover { color: var(--text); }` line (`static/style.css:1211`), add:

```css
.group-header:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

- [ ] **Step 2: Confirm diff is additive only**

Run: `git diff static/style.css`
Expected: one new line added, nothing else changed.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "style: add focus ring for keyboard-focused group headers"
```

---

## Task 3: Verification against acceptance criteria

**Files:** none (verification only)

- [ ] **Step 1: Backend regression check**

Run: `python3 -m pytest -q`
Expected: all tests pass (this item touches no backend code — pure regression check).

- [ ] **Step 2: Trace each acceptance criterion against the final diff**

1. "Each collapsible group header can be reached via Tab and toggled with Enter or Space, in the deck grid view, deck list view, and Collection page's grouped grid" — satisfied: `tabindex="0"` + `keydown` listener added whenever `collapsedState` is passed; confirmed callers at `static/app.js:1693`, `:1697`, `:2172`, `:2316` all pass `collapsedState`.
2. "Toggling via keyboard produces the same visual result as mouse click" — satisfied: both listeners call the same `toggleGroup()` function, so DOM mutations (class toggles, reorder) are identical regardless of trigger.
3. "`aria-expanded` reflects current collapsed/expanded state" — satisfied: set on initial render (`String(!isCollapsed)`) and updated inside `toggleGroup()` after every toggle (`String(!nowCollapsed)`).
4. "A focused header shows a visible focus ring" — satisfied by Task 2's `:focus-visible` rule.
5. "Groups rendered without `collapsedState` are unaffected" — satisfied: all new attribute/listener code is inside the existing `if (collapsedState)` block; confirmed non-collapsedState callers at `static/app.js:2157`, `:2301` are untouched by this change (they pass `{}`, so `collapsedState` is `undefined` and the `if` block is skipped entirely).

- [ ] **Step 3: Manual/browser check (best-effort)**

If browser tooling is available: start the dev server, open the Collection page (grouped view) and a deck (grid view with cards in the Considering section, and list/text view), Tab to a group header, confirm a visible outline appears, press Enter then Space and confirm the section collapses/expands and reorders to the end when collapsed, and inspect `aria-expanded` in devtools. If unavailable, rely on the code trace in Step 2 and note this in the final report.

- [ ] **Step 4: Final diff review**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Expected: `static/app.js` and `static/style.css` changed (plus plan/claim doc commits), nothing unrelated staged.
