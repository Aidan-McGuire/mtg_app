# Deck Enter Opens Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the deck page, pressing `Enter` opens the detail modal for the currently keyboard-focused deck card (`deckState.focusedCardId`), mirroring the existing `Backspace`/`c` handlers in the same keydown block.

**Architecture:** Pure JS change, one new `if` branch added inside the existing deck-page keydown block in `static/app.js` (the block guarded by `decksActive && deckState.currentDeckId && !deckSwitchPaletteOpen() && !addPaletteOpen()`, immediately after the existing `Backspace` and `c`/`C` cases). No changes to `openModal`, `setDeckFocus`, or any other handler.

**Tech Stack:** Plain vanilla JS (`static/app.js`, no build step, no framework, no tests directory covering keydown handlers per `grep -rn "focusedCardId" tests/` — none needs updating). Verification is: careful code reading against the four acceptance criteria, `node --check static/app.js` (or full parse via `/opt/homebrew/bin/node`) for syntax validity, and `python3 -m pytest -q` staying fully green (regression only — this item touches only frontend JS the Python suite doesn't exercise).

**Spec:** `docs/superpowers/backlog/027-deck-enter-opens-modal.md`

## Global Constraints

- Change is scoped to exactly one new `if` block inserted after the existing `c`/`C` handler (`static/app.js:1336-1342`) and before the closing `}` of the outer deck-page block (`static/app.js:1343`). No other lines in this block may be touched, since sibling backlog items 028/029 touch the same block and will be merged after this one.
- Reuse the `typingInField` variable already computed at `static/app.js:1323-1324` (covers `input, textarea, select`) rather than redefining it — this already matches the acceptance criterion about not firing while typing in the content search box or a tag input.
- No change to `openModal`, `setDeckFocus`, grid/list click handlers, or the Cards-page `Enter` handler (`static/app.js:1352`).

---

## Current code (reference — read before editing)

`static/app.js:1331-1343`:
```js
    if (!typingInField && e.key === 'Backspace' && deckState.focusedCardId) {
      e.preventDefault();
      removeDeckCard(deckState.focusedCardId);
      return;
    }
    if (!typingInField && (e.key === 'c' || e.key === 'C') && deckState.focusedCardId) {
      const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
      if (card && !card.is_commander) {
        e.preventDefault();
        toggleConsidering(card.id);
      }
    }
  }
```

---

## Task 1: Add the Enter handler

**Files:**
- Modify: `static/app.js:1336-1343`

**Interfaces:**
- Consumes: `deckState.focusedCardId`, `deckState.deckCards`, `deckState.currentDeckId`, `openModal(card, opts)` — all pre-existing, unchanged signatures.
- Produces: no new exports; purely adds a keydown side effect.

- [ ] **Step 1: Insert the Enter case**

Insert immediately after the `c`/`C` block (after line 1342's closing `}`, before line 1343's closing `}` of the outer `if`):

```js
    if (!typingInField && e.key === 'Enter' && deckState.focusedCardId) {
      e.preventDefault();
      const card = deckState.deckCards.find(c => c.id === deckState.focusedCardId);
      if (card) openModal(card, { deckId: deckState.currentDeckId });
    }
```

- [ ] **Step 2: Verify against acceptance criteria by code reading**

Walk through each:
- Grid view: card gets `focusedCardId` set via `setDeckFocus` (hover/arrow-nav, `static/app.js:2179`) in both grid and list view identically — confirm `handleDeckColumnNavKey` and `setDeckFocus` are view-agnostic (used for both `deck-grid-view` and `deck-text-view`, line 1327-1328). Enter reuses the same `openModal(card, { deckId })` call as the existing tile/row click handlers (`static/app.js:2236`, `2270`), so deck-context modal (no quantity stepper) is preserved.
- Typing guard: `typingInField` (line 1323-1324) matches `input, textarea, select`, covering the content search box and tag inputs — Enter is a no-op while any of those has focus.
- No focus guard: `deckState.focusedCardId` is `null` by default and reset to `null` on deck switch (`static/app.js:1992`) — the `&& deckState.focusedCardId` condition short-circuits, matching Backspace/`c` behavior exactly.

- [ ] **Step 3: Syntax check**

Run: `/opt/homebrew/bin/node --check static/app.js` (fallback: any working `node --check static/app.js`)
Expected: no output, exit code 0.

- [ ] **Step 4: Backend regression check**

Run: `python3 -m pytest -q`
Expected: full pass, same as before this change (this item touches no backend code).

- [ ] **Step 5: Diff review**

Run: `git diff static/app.js`
Expected: exactly one new 5-line block added inside the deck-page keydown handler; no other lines changed.
