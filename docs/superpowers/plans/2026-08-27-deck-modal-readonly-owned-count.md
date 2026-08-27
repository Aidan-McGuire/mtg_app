# Deck Modal Read-Only Owned Count Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the card detail modal is opened from within a deck (grid tile
or list row), show a read-only "N owned" indicator instead of no
owned-count information at all.

**Architecture:** `openModal(card, deckContext)` in `static/app.js` currently
renders `''` for `collectionHtml` when `deckContext` is truthy. Replace that
with a read-only markup variant reusing the existing `qty-label`/
`qty-owned-label` classes and the `data-qty-for` attribute so
`refreshQtyInDOM` (static/app.js:630) keeps it live-synced. Omit the two
`.qty-btn` buttons and don't attach their click handlers — the existing
`if (!deckContext) { ... }` guard around the listener wiring already does
that.

**Tech Stack:** Vanilla JS, no build step. Pure presentational change to a
template-literal string; no backend/API/CSS changes anticipated.

**Spec:** `docs/superpowers/backlog/026-deck-modal-readonly-owned-count.md`

## Global Constraints

- No change to non-deck-context modal behavior (still shows editable
  stepper with `+`/`−` buttons).
- No JS changes to the `if (!deckContext) { ... }` listener-attachment
  guard at static/app.js:904-907 — it already correctly skips attaching
  `qty-btn` listeners when `deckContext` is set, and there are no buttons
  to attach listeners to in the read-only markup anyway.
- No new CSS unless visually necessary (existing `.modal-collection { display:flex; align-items:center; gap:8px }` in static/style.css:418 already accommodates two spans with no buttons).

---

### Task 1: Render read-only owned-count markup in deck-context modal

**Files:**
- Modify: `static/app.js:877-883` (the `collectionHtml` ternary inside `openModal`)

**Interfaces:**
- Consumes: `deckContext` (truthy object with `deckId` when opened from a
  deck, `null`/falsy otherwise — existing parameter), `q` (existing local
  `const q = qty(card.id)` at static/app.js:867), `card.id`.
- Produces: `collectionHtml` string used at static/app.js:899, unchanged
  variable name and insertion point.

- [ ] **Step 1: Replace the `collectionHtml` ternary**

Change static/app.js:877-883 from:

```js
  const collectionHtml = deckContext ? '' : `
      <div class="modal-collection">
        <button class="qty-btn" data-action="dec" title="Remove (-)">−</button>
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <button class="qty-btn" data-action="inc" title="Add (+)">+</button>
        <span class="qty-owned-label">owned</span>
      </div>`;
```

to:

```js
  const collectionHtml = deckContext ? `
      <div class="modal-collection modal-collection-readonly">
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <span class="qty-owned-label">owned</span>
      </div>` : `
      <div class="modal-collection">
        <button class="qty-btn" data-action="dec" title="Remove (-)">−</button>
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <button class="qty-btn" data-action="inc" title="Add (+)">+</button>
        <span class="qty-owned-label">owned</span>
      </div>`;
```

Leave the `if (!deckContext) { ... }` block at static/app.js:904-907
untouched — it already only attaches `qty-btn` listeners in the non-deck
case, and the read-only markup has no `qty-btn` elements for it to find.

- [ ] **Step 2: Syntax-check the file**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit code 0 (avoid `/usr/local`'s node — it's known
dead in this environment).

- [ ] **Step 3: Manually trace the four acceptance criteria against the diff**

Read through the edited `openModal` function and confirm by inspection:
1. Deck-context open renders `.modal-collection-readonly` with a
   `qty-label` (bold/accent via existing `.qty-label.owned` CSS rule at
   static/style.css:223 when `q > 0`) and a `qty-owned-label` span — no
   `.qty-btn` elements.
2. No click listeners reference nonexistent buttons (the
   `if (!deckContext)` guard prevents `querySelector('[data-action="inc"]')`
   / `[data-action="dec"]` from ever running against the read-only markup).
3. `data-qty-for="${card.id}"` is present on the read-only `qty-label`
   span, so `refreshQtyInDOM` (static/app.js:630-636, which does
   `document.querySelectorAll('[data-qty-for="' + cardId + '"]')` and
   updates `textContent`/`className` on every match) will update it live
   on any quantity change while the modal is open.
4. The non-deck-context branch of the ternary is byte-for-byte identical
   to the original markup, so Cards/Collection-page modal behavior is
   unchanged.

- [ ] **Step 4: Run the backend test suite**

Run: `python3 -m pytest`
Expected: all tests pass (this change touches only frontend JS template
strings, so the full backend suite should be unaffected).

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "fix: show read-only owned count in deck-context detail modal"
```
