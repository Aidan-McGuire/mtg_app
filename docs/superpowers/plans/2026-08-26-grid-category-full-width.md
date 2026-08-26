# Grid-View Categories Span Full Width Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every `.group-section` (grouped-category block) in the card browser, collection browser, and deck grid view span the full grid width and render its cards in a multi-column flow, instead of being auto-placed into a single narrow ~240px grid track.

**Architecture:** Pure CSS + one JS class-list cleanup, no layout-logic changes. `.group-section` is a direct child of a `display: grid` container (`.card-grid` / `.deck-grid-view`, `grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))`). Adding `grid-column: 1 / -1;` to the base `.group-section` rule makes every section occupy the full row instead of one auto-fill track, so each section's own nested `.group-body` grid gets the full container width to lay out multiple cards per row. This makes the existing `.group-section-full` rule (currently applied only to the deck grid view's trailing "Considering" section) redundant, so it and its one call site are removed.

**Tech Stack:** Plain CSS (`static/style.css`, no build step), vanilla JS (`static/app.js`, no framework). No existing frontend test (`tests/js/*.test.mjs`) references `renderGroupedGrid`, `group-section`, or `group-section-full` (verified via `grep -rln "renderGroupedGrid\|group-section" tests/` — no matches), and all functions touched (`renderGroupSection`, the deck grid render branch) are DOM-wiring functions that read `document`, not pure functions extractable via the sentinel-comment pattern used elsewhere in `tests/js/` — consistent with how the rest of the codebase's render functions are (not) tested. Verification is: `node --check static/app.js` for syntax, the full existing `tests/js/*.test.mjs` + `pytest` suites staying green (regression only — this item touches no code any existing test covers), a `grep` confirming zero remaining `group-section-full` references, and a careful trace of the new CSS/JS against every acceptance criterion in the spec.

**Spec:** `docs/superpowers/backlog/015-grid-category-full-width.md`

## Global Constraints

- `#deck-text-view .group-body`'s existing fixed 2-column row override and `.deck-text-view`'s `display: flex; flex-direction: column` (not `display: grid`) must NOT be touched — deck text view is explicitly out of scope and must remain visually unchanged.
- `renderGroupedGrid`'s and `renderGroupSection`'s structure (`.group-section` > `.group-header` + `.group-body`) is unchanged — only which grid track(s) the section occupies changes.
- Collapsing/expanding a category via `.group-header` click (`.group-header.collapsed` / `.group-body.collapsed`) must keep working exactly as before — no changes to that logic.
- Zero remaining references to `group-section-full` (class or CSS selector) anywhere in `static/app.js` or `static/style.css` when done.

---

## Current code (reference — read before editing)

`static/style.css:1167-1215`:
```css
/* ── Group sections ────────────────────────────────────────────────────────── */
.group-section { margin-bottom: 20px; }

/* Used only for the single trailing Considering section appended below the
   flat (ungrouped) deck grid, so it spans the full grid width instead of
   being auto-placed into one ~240px column. Do NOT apply to grouped-by-tag
   sections (Deck or Collection) — those intentionally render as columns. */
.group-section-full { grid-column: 1 / -1; }

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

.group-header-label {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent);
}
.group-header-count {
  font-size: 12px;
  color: var(--muted);
}
.group-header-chevron {
  font-size: 10px;
  color: var(--muted);
  transition: transform 0.15s;
  margin-left: auto;
}
.group-header.collapsed .group-header-chevron { transform: rotate(-90deg); }

.group-body {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  grid-auto-rows: max-content;
  gap: 10px;
  align-items: start;
}
.group-body.collapsed { display: none; }
```

`static/app.js:2099-2116` (deck grid render branch, inside the function that builds `.deck-grid-view`'s flat/ungrouped-by-tag path):
```js
    const frag = document.createDocumentFragment();
    for (const card of sorted) frag.appendChild(buildDeckCardTile(card));
    el.appendChild(frag);
    if (consideringCards.length) {
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        { collapsedState: deckGroupCollapsed }
      );
      // Full grid width for this single trailing section — it sits below the
      // flat card grid, not alongside it as another narrow column. Scoped to
      // this ungrouped-branch section only; the grouped-by-tag branch above
      // intentionally keeps all sections (including its own Considering
      // group) as narrow columns and must not get this class.
      el.lastElementChild.classList.add('group-section-full');
    }
```

`static/app.js:1500-1503` (`renderGroupSection`, shared by all three grouped grid views):
```js
function renderGroupSection(container, group, buildTileFn, opts = {}, allGroups = [group]) {
  const { collapsedState } = opts;
  const section = document.createElement('div');
  section.className = 'group-section';
```

---

## Task 1: CSS — make `.group-section` always span full grid width

**Files:**
- Modify: `static/style.css:1167-1174`

**Interfaces:**
- Consumes: nothing new.
- Produces: `.group-section` now includes `grid-column: 1 / -1;` unconditionally — Task 2 relies on this to safely drop the `group-section-full` class addition without any visual change to the trailing Considering section.

- [ ] **Step 1: Edit the CSS**

Replace `static/style.css:1167-1174`:
```css
/* ── Group sections ────────────────────────────────────────────────────────── */
.group-section { margin-bottom: 20px; }

/* Used only for the single trailing Considering section appended below the
   flat (ungrouped) deck grid, so it spans the full grid width instead of
   being auto-placed into one ~240px column. Do NOT apply to grouped-by-tag
   sections (Deck or Collection) — those intentionally render as columns. */
.group-section-full { grid-column: 1 / -1; }
```

with:
```css
/* ── Group sections ────────────────────────────────────────────────────────── */
.group-section { margin-bottom: 20px; grid-column: 1 / -1; }
```

- [ ] **Step 2: Confirm no other CSS references `.group-section-full`**

Run: `grep -n "group-section-full" static/style.css`
Expected: no output (no matches).

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "fix: make grouped grid-view categories span full width"
```

---

## Task 2: JS — remove the now-redundant `group-section-full` class addition

**Files:**
- Modify: `static/app.js:2109-2114`

**Interfaces:**
- Consumes: Task 1's unconditional `grid-column: 1 / -1` on `.group-section` — the trailing Considering section already gets full-width layout from its base class now, so this call site can be deleted with no visual change.
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Edit the JS**

Replace `static/app.js:2102-2115`:
```js
    if (consideringCards.length) {
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        { collapsedState: deckGroupCollapsed }
      );
      // Full grid width for this single trailing section — it sits below the
      // flat card grid, not alongside it as another narrow column. Scoped to
      // this ungrouped-branch section only; the grouped-by-tag branch above
      // intentionally keeps all sections (including its own Considering
      // group) as narrow columns and must not get this class.
      el.lastElementChild.classList.add('group-section-full');
    }
```

with:
```js
    if (consideringCards.length) {
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        { collapsedState: deckGroupCollapsed }
      );
    }
```

- [ ] **Step 2: Syntax check**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Confirm zero remaining references anywhere**

Run: `grep -rn "group-section-full" static/`
Expected: no output (no matches) — satisfies the spec's explicit acceptance criterion.

- [ ] **Step 4: Regression check — existing suites still green**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: every `.test.mjs` file prints its all-passing summary; pytest reports all passing (128 passed, unaffected — this item touches only frontend files).

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "fix: drop redundant group-section-full class from deck grid view"
```

---

## Task 3: Full acceptance-criteria walkthrough and manual verification

**Files:** none (verification only)

- [ ] **Step 1: Trace the CSS/JS diff against each acceptance criterion**

Re-read `docs/superpowers/backlog/015-grid-category-full-width.md`'s "## Acceptance criteria" against the final diff:
1. "Each category spans the full grid width, with multiple cards per row" — satisfied by Task 1: `.group-section { grid-column: 1 / -1 }` makes every section (card browser `#card-grid`, collection browser `#collection-grid`, deck grid view `.deck-grid-view` — all three use the same `renderGroupSection`/`renderGroupedGrid` code path and the same `.group-section`/`.group-body` classes) occupy the full row of its outer grid, so `.group-body`'s own `repeat(auto-fill, minmax(240px, 1fr))` now has the full container width to place multiple 240px+ tiles per row instead of one ~240px track.
2. "The deck grid view's trailing Considering section still renders correctly (full width)" — satisfied: it already got `grid-column: 1 / -1` before via the explicit class; now it gets the identical CSS declaration unconditionally from the base `.group-section` rule (Task 1), and Task 2 just removes the now-redundant class addition — no visual change.
3. "Deck text view's grouped rendering (2-column row layout) is visually unchanged" — untouched: `#deck-text-view .group-body`'s separate override and `.deck-text-view`'s `display: flex` are not modified by either task, and `grid-column` is a no-op on a non-grid-item (flex child), so adding it to the base `.group-section` rule has zero effect there.
4. "Collapsing/expanding a category still works" — untouched: `renderGroupSection`'s collapse/expand logic (`.group-header` click handler, `.group-header.collapsed`, `.group-body.collapsed`) is not modified by either task.
5. "No remaining references to `.group-section-full`" — confirmed via `grep -rn "group-section-full" static/` in Task 2 Step 3 (zero matches).

- [ ] **Step 2: Full test suite**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: syntax check silent; every `.test.mjs` prints its all-passing summary; pytest reports 128 passed.

- [ ] **Step 3: Manual visual check (best-effort, do not block on this)**

If a browser-automation tool is available, start the dev server (`uvicorn app:app --reload` from the worktree root, using the worktree's own `mtg.db`), open the card browser, group by a category (e.g. Type), and visually confirm categories stack full-width with multiple cards per row; repeat for the collection browser and deck grid view (including its "Considering" section). If no browser tool is available, skip this step — the CSS/JS trace in Step 1 plus the automated suites are the primary verification.

- [ ] **Step 4: Final diff review**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Expected: only `static/style.css` and `static/app.js` changed (plus the claim/plan doc commits), across the commits from Tasks 1-2, nothing unrelated staged.
