# Deck Text Owned Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the deck text/list view a row-level visual indicator for cards the player owns (collection quantity > 0), mirroring the grid view's green `OWNED_BADGE_HTML` badge without adding a new DOM element.

**Architecture:** Pure frontend change. `buildDeckTextRow(card)` (`static/app.js`) gains an `owned` class on its row `className`, derived once per render from the existing `qty(card.id) > 0` check (same helper already used by the grid tile and by `applyFilters`). `static/style.css` gets one new rule, `.deck-text-row.owned`, giving the row a subtle green-tinted treatment reusing `--accent` (the same color already used by `.qty-label.owned` and `.card-owned-badge`) via a thin left border, layered so it coexists with the existing `.deck-text-row.focused` box-shadow-based left accent without visually colliding.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework), plain CSS (`static/style.css`). Frontend unit tests are plain Node scripts under `tests/js/` that extract sentinel-comment-delimited *pure* functions out of `static/app.js` via string slicing + `new Function(...)` (see `tests/js/filter-decks.test.mjs`). `buildDeckTextRow` is DOM-wiring that reads `document`/`deckState` and calls sibling functions (`qty`, `esc`, `tagChipsHtml`, `setDeckFocus`, `openModal`, event listeners) — consistent with every other render function in this codebase (`buildDeckCardTile`, `renderDeckText`, etc.), it has no sentinel-comment block and gets no new unit test. There is no DOM/jsdom harness in this repo, and no browser-automation tool is connected in this run (`mcp__claude-in-chrome__tabs_context_mcp` returned "No tab group exists" and this is an unattended background worker with no display to drive), so verification is: (a) `node --check static/app.js` for syntax, (b) the full existing `tests/js/*.test.mjs` + `python3 -m pytest` suites staying green (regression check — this plan doesn't touch anything those suites cover), and (c) careful line-by-line trace of the new/changed code against every acceptance criterion in the spec, including a manual CSS specificity/cascade check for the `.focused` co-occurrence requirement.

**Spec:** `docs/superpowers/backlog/013-deck-text-owned-indicator.md`

## Global Constraints

- No new DOM element in `buildDeckTextRow`'s template — only `row.className` changes.
- No changes to `renderDeckText`, the grid view, `refreshQtyInDOM`, or `qty()` itself.
- Reuse `--accent` (style.css:8, `#c89b3c`) — the same color `.qty-label.owned` (style.css:223) and `.card-owned-badge` (style.css:226) already use — don't invent a new color.
- The new `.deck-text-row.owned` rule must not visually fight with `.deck-text-row.focused` (style.css:919, `box-shadow: inset 2px 0 0 var(--accent)` — already a left-edge accent in the same color) when both classes are present on the same row.

---

## Current code (reference — read before editing)

`buildDeckTextRow` (app.js:2179-2204) currently sets `className` as:
```js
row.className = 'deck-text-row' + (card.id === deckState.focusedCardId ? ' focused' : '');
```

`qty(cardId)` (app.js:535) is the existing collection-quantity lookup helper, already used elsewhere (grid tile owned badge, `applyFilters`).

`.deck-text-row` rules today (style.css:901-919):
```css
.deck-text-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 2px 8px;
  padding: 3px 4px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.1s;
}
.deck-text-row .tag-chips-row { display: contents; }
.deck-text-row:hover { background: var(--surface2); }
.deck-text-row.focused { background: var(--surface2); box-shadow: inset 2px 0 0 var(--accent); }
```

`--accent: #c89b3c;` (style.css:8). `.qty-label.owned { color: var(--accent); font-weight: 700; }` (style.css:223). `.card-owned-badge` (style.css:226-239) uses `background: var(--accent)` on a small circular badge.

---

## Task 1: Add the `owned` class to `buildDeckTextRow`

**Files:**
- Modify: `static/app.js:2181` (`buildDeckTextRow`'s `row.className` line)

**Interfaces:**
- Consumes: `qty(cardId)` (app.js:535, existing, unchanged), `card.id` (existing).
- Produces: an `owned` class on `.deck-text-row` elements, consumed by the new CSS rule added in Task 2.

- [ ] **Step 1: Edit the `className` assignment**

Change (app.js:2181):
```js
  row.className = 'deck-text-row' + (card.id === deckState.focusedCardId ? ' focused' : '');
```
to:
```js
  row.className = 'deck-text-row'
    + (card.id === deckState.focusedCardId ? ' focused' : '')
    + (qty(card.id) > 0 ? ' owned' : '');
```

- [ ] **Step 2: Syntax check**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Regression check — existing suites still green**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: every `.test.mjs` file prints its all-passing summary; pytest reports all passing (128 tests, unaffected — this task touches only `static/app.js`, no Python).

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: add owned class to deck text-view rows"
```

---

## Task 2: Add the `.deck-text-row.owned` CSS rule

**Files:**
- Modify: `static/style.css` (new rule near `.deck-text-row.focused`, style.css:919)

**Interfaces:**
- Consumes: the `owned` class produced by Task 1, `--accent` custom property (style.css:8, existing, unchanged).
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Add the rule**

Immediately after the existing `.deck-text-row.focused` rule (style.css:919), add:

```css
.deck-text-row.owned { box-shadow: inset 2px 0 0 var(--accent); }
.deck-text-row.owned.focused { background: var(--surface2); box-shadow: inset 2px 0 0 var(--accent); }
```

Rationale: `.deck-text-row.focused` already uses `box-shadow: inset 2px 0 0 var(--accent)` as its left-edge accent — the exact same visual language this spec asks for ("thin left border ... in the same green"). Giving `.owned` the identical `box-shadow` means:
- Owned-but-not-focused rows get a subtle accent-colored left edge (the "owned" signal), no background change — reads as understated, matching "subtle" in the spec.
- Focused-but-not-owned rows are unchanged (existing `.focused` rule alone still applies).
- Rows that are both `owned` and `focused` render with exactly the same left-edge accent as `.focused` alone (not doubled, not conflicting) plus the existing `.focused` background tint — so the two states visually coincide instead of fighting. The explicit `.owned.focused` rule is a no-op restatement included for clarity/future-proofing (equal specificity to `.focused` alone, same declarations, so cascade order doesn't matter here) — mainly documents the intended coexistence for the next reader.
- No change at all to `.deck-text-row:hover` or unfocused/unowned rows.

- [ ] **Step 2: Trace against acceptance criteria**

Confirm by reading the edited CSS and `buildDeckTextRow`:
- "cards with collection quantity > 0 are visually distinguishable from cards with quantity 0" — owned rows get the left accent border via `.deck-text-row.owned`; non-owned rows don't. Satisfied.
- "does not visually conflict with `.focused` ... when combined" — `.deck-text-row.owned.focused` produces the same left-edge accent as `.focused` alone (no doubled border, no color clash) plus the existing focused background tint. Satisfied.
- "`.is-commander`, or considering-row styling" — those classes (`.deck-card-tile.is-commander`/`.is-considering`, style.css:789-790) are grid-view-only, applied to `.deck-card-tile`, never to `.deck-text-row` (confirmed via `grep -n "is-commander\|is-considering" static/app.js static/style.css` — both only appear in `buildDeckCardTile`'s tile `className`, app.js:2131-2132). Text view has no such classes on its rows at all, so there is nothing for `.deck-text-row.owned` to conflict with there; N/A for text view, satisfied vacuously.
- "Grid view's existing owned badge behavior is unchanged" — Task 1/2 touch only `buildDeckTextRow` and a new `.deck-text-row.owned` selector; `buildDeckCardTile`, `OWNED_BADGE_HTML`, `.card-owned-badge`, and `refreshQtyInDOM` are untouched. Satisfied.
- "No new elements added to the row's DOM structure" — Task 1's diff is confined to the `row.className` line; `row.innerHTML` template is untouched. Satisfied.

- [ ] **Step 3: Regression check**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green (regression only — CSS-only change, no test suite covers styling).

- [ ] **Step 4: Commit**

```bash
git add static/style.css
git commit -m "style: add subtle owned indicator to deck text-view rows"
```

---

## Task 3: Full acceptance-criteria walkthrough

**Files:** none (verification only)

- [ ] **Step 1: Re-read the spec's acceptance criteria and map each to the change that satisfies it**

Walk `docs/superpowers/backlog/013-deck-text-owned-indicator.md`'s "## Acceptance criteria" list end to end against the final diff:
1. Owned vs. non-owned rows visually distinguishable in text view → Task 1 (class) + Task 2 (rule).
2. No visual conflict with `.focused`/`.is-commander`/considering-row styling → Task 2 Step 2's trace (`.focused` combination verified directly; the other two classes don't apply to text-view rows at all).
3. Grid view's owned badge behavior unchanged → neither task touches `buildDeckCardTile`, `OWNED_BADGE_HTML`, or `refreshQtyInDOM`.
4. No new DOM elements, only a class-name change → Task 1's diff is a single-line `className` edit; `innerHTML` untouched.

- [ ] **Step 2: Full test suite**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: syntax check silent; every `.test.mjs` prints its all-passing summary; pytest reports all 128 passing.

- [ ] **Step 3: Final diff review**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Expected: only `static/app.js` and `static/style.css` changed (plus the plan/backlog doc commits), across the two implementation commits from Tasks 1-2, nothing unrelated staged.
