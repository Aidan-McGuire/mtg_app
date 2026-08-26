# Deck Text View Font Bump Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump the three main deck text view row text elements up by 1px each, so the row text (quantity, card name, mana cost) is slightly more legible.

**Architecture:** Pure CSS value change, no markup or JS changes. Three existing single-line rules in `static/style.css` each get their `font-size` value increased by 1px; every other property on those rules is left untouched.

**Tech Stack:** Plain CSS (`static/style.css`, no build step). No JS or markup changes. `grep -rn "deck-text-qty\|deck-text-name\|deck-text-mana" tests/` returns no matches, so there is no existing frontend test (`tests/js/*.test.mjs`) covering these selectors — none needs updating. Verification is: `python3 -m pytest -q` staying fully green (regression only — this item touches only a CSS file the Python suite doesn't exercise), a `git diff` review confirming only the three `font-size` values changed and no other property/selector was touched, and a best-effort manual/visual check if browser tooling is available.

**Spec:** `docs/superpowers/backlog/022-deck-text-view-font-bump.md`

## Global Constraints

- Only the `font-size` value on each of the three rules changes. `color`, `min-width`, `font-weight`, and `flex` must remain byte-for-byte identical.
- No other deck text view selector (tag chips, keyboard hint elements, the considering-toggle button, or any other rule) may be touched.
- No JS or HTML changes — this is a CSS-only item.

---

## Current code (reference — read before editing)

`static/style.css:947-949`:
```css
.deck-text-qty  { font-size: 12px; color: var(--muted); min-width: 22px; }
.deck-text-name { font-size: 13px; font-weight: 500; flex: 1; }
.deck-text-mana { font-size: 11px; color: var(--muted); }
```

---

## Task 1: CSS — bump the three font-size values

**Files:**
- Modify: `static/style.css:947-949`

**Interfaces:**
- Consumes: nothing new.
- Produces: `.deck-text-qty` at 13px, `.deck-text-name` at 14px, `.deck-text-mana` at 12px — no other consumers of these rules exist beyond the deck text view row markup, which is unchanged.

- [ ] **Step 1: Edit the CSS**

Replace `static/style.css:947-949`:
```css
.deck-text-qty  { font-size: 12px; color: var(--muted); min-width: 22px; }
.deck-text-name { font-size: 13px; font-weight: 500; flex: 1; }
.deck-text-mana { font-size: 11px; color: var(--muted); }
```

with:
```css
.deck-text-qty  { font-size: 13px; color: var(--muted); min-width: 22px; }
.deck-text-name { font-size: 14px; font-weight: 500; flex: 1; }
.deck-text-mana { font-size: 12px; color: var(--muted); }
```

- [ ] **Step 2: Confirm no other property changed**

Run: `git diff static/style.css`
Expected: exactly three changed lines, each with only the `font-size` number differing (12→13, 13→14, 11→12); `color`, `min-width`, `font-weight`, `flex` identical on both sides of the diff.

- [ ] **Step 3: Regression check — Python suite still green**

Run: `python3 -m pytest -q`
Expected: all tests pass, unaffected (this item touches only a CSS file).

- [ ] **Step 4: Commit**

```bash
git add static/style.css
git commit -m "style: bump deck text view row font sizes by 1px"
```

---

## Task 2: Acceptance-criteria walkthrough and manual verification

**Files:** none (verification only)

- [ ] **Step 1: Trace the CSS diff against each acceptance criterion**

Re-read `docs/superpowers/backlog/022-deck-text-view-font-bump.md`'s "## Acceptance criteria" against the final diff:
1. "`.deck-text-qty` renders at 13px" — satisfied by Task 1.
2. "`.deck-text-name` renders at 14px" — satisfied by Task 1.
3. "`.deck-text-mana` renders at 12px" — satisfied by Task 1.
4. "No other properties on these three rules changed" — confirmed via `git diff static/style.css` in Task 1 Step 2.
5. "No other deck text view elements (tags, kbd hints, considering button) changed size" — confirmed: the diff touches only the three named selectors, nothing else in the file.
6. "Rows still lay out without visual overflow/clipping at the new sizes (check a card with a long name and a full tag list)" — verify via manual check (Step 2 below) if browser tooling is available; otherwise note as a code-level-only check in the final report, since a 1px bump on `13px→14px` text with `flex: 1` on the name and no fixed-width container is very unlikely to cause overflow.

- [ ] **Step 2: Manual visual check (best-effort, do not block on this)**

If browser-automation tooling is available: start the dev server (`uvicorn app:app --reload --port 8002` from the worktree root, using the worktree's own `mtg.db`), open a deck's text view, and visually confirm the row text (quantity, card name, mana cost) is slightly larger than before with no overflow/clipping — check a card with a long name and a full set of tags. If no browser tool is available, skip this step and rely on the code-level diff review in Step 1, noting this explicitly in the final report.

- [ ] **Step 3: Final diff review**

Run: `git diff main --stat` and `git log --oneline main..HEAD`
Expected: only `static/style.css` changed (plus the claim/plan doc commits), across the single commit from Task 1, nothing unrelated staged.
