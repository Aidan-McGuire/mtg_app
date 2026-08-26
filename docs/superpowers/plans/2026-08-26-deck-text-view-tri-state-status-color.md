# Deck Text View Tri-State Status Color Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the deck text view's two unrelated ownership signals — the
subtle gold `.deck-text-row.owned` left-edge highlight (item 013) and the
separate red `⚠` `.deck-text-locked` inline glyph (item 020) — with a single
left-edge highlight whose color communicates one of three mutually
exclusive, exhaustive states per row: green (owned, at least one copy free),
yellow (owned, all copies locked elsewhere), red (not owned at all).

**Architecture:** Pure frontend change, scoped entirely to the deck text
view. `buildDeckTextRow(card)` (`static/app.js`) computes `owned` (existing
`qty(card.id) > 0` check) and `locked` (existing `isLockedElsewhere(card.id)`
check, itself already gated on `owned`), derives one of three status class
strings (`unowned` / `owned-locked` / `owned-free`), and sets it on
`row.className` in place of the old `owned` class. The old inline
`<span class="deck-text-locked">⚠</span>` is removed from the row's
`innerHTML` template — the edge color now carries that meaning — and a
`title` attribute is set on the row itself so the removed glyph's tooltip
isn't lost. `static/style.css` gains three paired state rules (each with a
`.focused` variant, following the exact `box-shadow: inset 2px 0 0 <color>`
pattern the old `.owned` rule already used) and loses the old `.owned`
pair. The combined `.deck-text-locked, .dsearch-locked` CSS rule is split so
`.dsearch-locked` (used by the unrelated "Add cards" search results view)
keeps its styling unchanged while the now-dead `.deck-text-locked` selector
is removed.

**Tech Stack:** Vanilla JS (`static/app.js`, no build step, no framework),
plain CSS (`static/style.css`). Frontend unit tests are plain Node scripts
under `tests/js/` that extract sentinel-comment-delimited *pure* functions
out of `static/app.js` via string slicing + `new Function(...)` (see
`tests/js/filter-decks.test.mjs`). `buildDeckTextRow` is DOM-wiring that
reads `document`/`deckState` and calls sibling functions (`qty`,
`isLockedElsewhere`, `esc`, `tagChipsHtml`, `setDeckFocus`, `openModal`,
event listeners) — consistent with every other render function in this
codebase (`buildDeckCardTile`, `renderDeckText`, etc.), it has no
sentinel-comment block and got no new unit test when its `owned` class was
first added in item 013 (see
`docs/superpowers/plans/2026-08-26-deck-text-owned-indicator.md`, Task 1)
— this item follows that same established precedent and adds no new test
file. Verification is: (a) `node --check static/app.js` for syntax, (b) the
full existing `tests/js/*.test.mjs` + `python3 -m pytest` suites staying
green (regression check — neither suite covers `buildDeckTextRow` or this
CSS), and (c) a careful line-by-line trace of the new/changed code against
every acceptance criterion in the spec, plus a manual browser check if
browser-automation tooling turns out to be available in this run.

**Spec:** `docs/superpowers/backlog/021-deck-text-view-tri-state-status-color.md`

## Global Constraints

- Scoped to the deck text view only: `buildDeckTextRow` (app.js) and
  `.deck-text-row` rules (style.css). Do not touch `buildDeckCardTile`,
  `OWNED_BADGE_HTML`, `.card-owned-badge`, or `renderDeckSearchResults` /
  `.dsearch-locked`'s styling.
- Every row must end up with exactly one of `unowned` / `owned-locked` /
  `owned-free` — never zero, never more than one, and the old `owned` class
  must be gone entirely.
- The `<span class="deck-text-locked">...</span>` glyph must be removed
  from the row's `innerHTML` entirely, not just hidden.
- `.dsearch-locked`'s existing styling (`color: #e74c3c; font-size: 12px;`)
  must be preserved unchanged after the selector split.
- New colors: green `#2ecc71` (owned-free), yellow `#f1c40f`
  (owned-locked); reuse existing red `#e74c3c` (unowned) — same flat, muted
  palette family the file's existing danger colors already use.

---

## Current code (reference — read before editing)

`buildDeckTextRow` (app.js:2241-2261 or nearby) currently:
```js
function buildDeckTextRow(card) {
  const row = document.createElement('div');
  row.className = 'deck-text-row'
    + (card.id === deckState.focusedCardId ? ' focused' : '')
    + (qty(card.id) > 0 ? ' owned' : '');
  row.dataset.id = card.id;

  const consideringBtnHtml = card.is_commander ? '' : `...`;

  const lockedHtml = isLockedElsewhere(card.id)
    ? '<span class="deck-text-locked" title="All owned copies are in other built decks">⚠</span>'
    : '';
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    ${lockedHtml}
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>
    ...
  `;
  ...
}
```

`isLockedElsewhere(cardId)` (app.js:590-594, existing, unchanged):
```js
function isLockedElsewhere(cardId) {
  const owned = qty(cardId);
  if (owned <= 0) return false;
  return owned <= (deckState.allocatedElsewhere[cardId] || 0);
}
```

`.deck-text-row` rules today (style.css:925-945):
```css
.deck-text-row.focused { background: var(--surface2); box-shadow: inset 2px 0 0 var(--accent); }
.deck-text-row.owned { box-shadow: inset 2px 0 0 var(--accent); }
.deck-text-row.owned.focused { background: var(--surface2); box-shadow: inset 2px 0 0 var(--accent); }
```

`.deck-text-locked, .dsearch-locked` rule today (style.css:259-262):
```css
.deck-text-locked, .dsearch-locked {
  color: #e74c3c;
  font-size: 12px;
}
```

---

## Task 1: Compute the 3-way status class and title in `buildDeckTextRow`

**Files:**
- Modify: `static/app.js` (`buildDeckTextRow`'s `row.className` assignment
  and the `lockedHtml`/`innerHTML` block)

**Interfaces:**
- Consumes: `qty(card.id)` (existing, unchanged), `isLockedElsewhere(card.id)`
  (existing, unchanged), `card.id`, `deckState.focusedCardId`.
- Produces: one of `unowned` / `owned-locked` / `owned-free` classes on
  `.deck-text-row` elements (consumed by the new CSS rules in Task 2); a
  `row.title` attribute; no more `.deck-text-locked` span in the DOM.

- [ ] **Step 1: Replace the `className` assignment and remove the locked span**

Change:
```js
  row.className = 'deck-text-row'
    + (card.id === deckState.focusedCardId ? ' focused' : '')
    + (qty(card.id) > 0 ? ' owned' : '');
  row.dataset.id = card.id;
```
to:
```js
  const owned = qty(card.id) > 0;
  const locked = owned && isLockedElsewhere(card.id);
  const statusClass = !owned ? 'unowned' : (locked ? 'owned-locked' : 'owned-free');
  row.className = 'deck-text-row'
    + (card.id === deckState.focusedCardId ? ' focused' : '')
    + ' ' + statusClass;
  row.title = locked ? 'All owned copies are in other built decks' : (!owned ? 'Not owned' : '');
  row.dataset.id = card.id;
```

Then remove the `lockedHtml` variable entirely and the `${lockedHtml}`
interpolation from the `innerHTML` template (delete that line from the
template literal), leaving `row.innerHTML` starting directly with
`deck-text-qty` / `deck-text-name` / `deck-text-mana` as before, just
without the glyph span between them.

- [ ] **Step 2: Syntax check**

Run: `node --check static/app.js`
Expected: no output, exit code 0.

- [ ] **Step 3: Grep for stale references**

Run: `grep -n "deck-text-locked\|lockedHtml\|'.\?owned'" static/app.js`
Expected: no `deck-text-locked` or `lockedHtml` hits; no bare `' owned'`
class-string hits left in `buildDeckTextRow` (the grid view's unrelated
`OWNED_BADGE_HTML`/badge logic, if it matches `owned` some other way, is
out of scope and should be left alone — inspect any hits to confirm they
aren't in `buildDeckTextRow`).

- [ ] **Step 4: Regression check — existing suites still green**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: every `.test.mjs` file prints its all-passing summary; pytest
reports all passing (unaffected — this task touches only `static/app.js`,
and none of the `tests/js/*.test.mjs` sentinel-extracted functions include
`buildDeckTextRow`).

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: replace deck text-view owned/locked signals with 3-state status class"
```

---

## Task 2: Add the three paired CSS status rules and split the locked-color rule

**Files:**
- Modify: `static/style.css` (replace the `.deck-text-row.owned` pair near
  `.deck-text-row.focused`; split the `.deck-text-locked, .dsearch-locked`
  rule)

**Interfaces:**
- Consumes: the `owned-free` / `owned-locked` / `unowned` classes produced
  by Task 1.
- Produces: nothing new consumed elsewhere.

- [ ] **Step 1: Replace the owned rule pair with three state rule pairs**

Replace:
```css
.deck-text-row.owned { box-shadow: inset 2px 0 0 var(--accent); }
.deck-text-row.owned.focused { background: var(--surface2); box-shadow: inset 2px 0 0 var(--accent); }
```
with:
```css
.deck-text-row.owned-free { box-shadow: inset 2px 0 0 #2ecc71; }
.deck-text-row.owned-free.focused { background: var(--surface2); box-shadow: inset 2px 0 0 #2ecc71; }
.deck-text-row.owned-locked { box-shadow: inset 2px 0 0 #f1c40f; }
.deck-text-row.owned-locked.focused { background: var(--surface2); box-shadow: inset 2px 0 0 #f1c40f; }
.deck-text-row.unowned { box-shadow: inset 2px 0 0 #e74c3c; }
.deck-text-row.unowned.focused { background: var(--surface2); box-shadow: inset 2px 0 0 #e74c3c; }
```

- [ ] **Step 2: Split the locked-color rule**

Replace:
```css
.deck-text-locked, .dsearch-locked {
  color: #e74c3c;
  font-size: 12px;
}
```
with:
```css
.dsearch-locked {
  color: #e74c3c;
  font-size: 12px;
}
```

- [ ] **Step 3: Grep for stale references**

Run: `grep -n "deck-text-locked\|deck-text-row.owned\b" static/style.css`
Expected: no hits (bare `.deck-text-row.owned` gone; only the new
`.owned-free`/`.owned-locked` selectors, which don't match this pattern,
remain).

- [ ] **Step 4: Trace against acceptance criteria**

Confirm by reading the edited CSS and `buildDeckTextRow` together:
- Owned + free copy → `owned-free` → green edge. Satisfied.
- Owned + all copies locked elsewhere → `owned-locked` → yellow edge, no
  separate glyph (removed in Task 1). Satisfied.
- Not owned at all → `unowned` → red edge. Satisfied.
- Exactly one state per row → `statusClass` in Task 1 is computed via a
  single ternary chain with no fallthrough gaps; every row gets exactly one
  of the three literal strings appended to `className`. Satisfied.
- `.focused` background tint still applies under any edge color — each of
  the three `.focused` variant rules explicitly sets
  `background: var(--surface2)` alongside its own edge color, mirroring the
  old `.owned.focused` rule's pattern exactly. Satisfied.
- Grid view badge (`buildDeckCardTile`/`OWNED_BADGE_HTML`/
  `.card-owned-badge`) and "Add cards" search `.dsearch-locked` indicator
  are untouched by either task. Satisfied — confirm via
  `git diff main -- static/app.js static/style.css` showing no hunks
  touching those symbols.
- No remaining `.deck-text-locked` or `.deck-text-row.owned` references —
  confirmed by Task 1 Step 3 and Task 2 Step 3 greps.

- [ ] **Step 5: Regression check**

Run: `for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: all green (regression only — CSS-only change, no test suite
covers styling).

- [ ] **Step 6: Commit**

```bash
git add static/style.css
git commit -m "style: give deck text-view rows a 3-state status color"
```

---

## Task 3: Full acceptance-criteria walkthrough and (if available) browser verification

**Files:** none (verification only)

- [ ] **Step 1: Re-read the spec's acceptance criteria and map each to the change that satisfies it**

Walk `docs/superpowers/backlog/021-deck-text-view-tri-state-status-color.md`'s
"## Acceptance criteria" list end to end against the final diff (see Task 2
Step 4's mapping above for each one).

- [ ] **Step 2: Full test suite**

Run: `node --check static/app.js && for f in tests/js/*.test.mjs; do echo "== $f =="; node "$f" || exit 1; done && python3 -m pytest -q`
Expected: syntax check silent; every `.test.mjs` prints its all-passing
summary; pytest reports all passing.

- [ ] **Step 3: Browser verification (if browser-automation tooling is available) or careful code trace (if not)**

If browser tooling is connected: start `uvicorn app:app --reload --port 8001`
from this worktree (its own `mtg.db`), open the deck builder's text view,
and confirm visually: a freely-owned card shows a green left edge, a card
owned but fully allocated to another `built` deck shows yellow (construct
this by marking a second deck `built` and allocating the card's only copy
there), an unowned card shows red, and the old `⚠` glyph is gone from the
text view (while `.dsearch-locked`'s `⚠` in the "Add cards" search results
is unaffected).

If no browser tooling is available: perform a careful code-level trace
instead (re-read the final `buildDeckTextRow` and the three CSS rule pairs
side by side against each acceptance criterion) and say so explicitly in
the final report.

- [ ] **Step 4: Check off acceptance criteria and commit**

```bash
git add docs/superpowers/backlog/021-deck-text-view-tri-state-status-color.md
git commit -m "docs(backlog): check off item 021 acceptance criteria"
```

- [ ] **Step 5: Final diff review**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Expected: only `static/app.js` and `static/style.css` changed for the
implementation (plus the plan/backlog/claim/finish doc commits), across the
two implementation commits from Tasks 1-2, nothing unrelated staged.
