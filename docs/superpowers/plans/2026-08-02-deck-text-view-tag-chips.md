# Deck tags on the Text view Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deck Text view rows show each card's deck-tag chips inline, at the end of the row, reusing the existing chip markup/styling from Grid view — untagged cards render unchanged.

**Architecture:** Two small, related changes: `buildDeckTextRow` (`static/app.js`) appends the existing `tagChipsHtml()` helper's output to its row markup; `static/style.css` gets a scoped override so the helper's wrapper div participates as inline flex items instead of a below-content block, plus `flex-wrap: wrap` on the row as an overflow safety net.

**Tech Stack:** Vanilla JS, no build step.

## Global Constraints

- No backend changes — do not touch `app.py`, `main.py`, or the DB schema.
- Match existing code style: 2-space indent, semicolons, `esc()` for all HTML-interpolated text (already handled inside the reused `tagChipsHtml` helper — no new interpolation is introduced by this change).
- Follow the approved design spec at `docs/superpowers/specs/2026-08-02-deck-text-view-tag-chips-design.md` exactly if anything is ambiguous.
- No JS test applies — this is markup/CSS only, no new pure-function logic to sentinel-wrap.

---

### Task 1: Inline deck-tag chips on Text view rows

**Files:**
- Modify: `static/app.js:1971-1982` (`buildDeckTextRow`)
- Modify: `static/style.css:896-906` (`.deck-text-row`)

**Interfaces:** None — reuses the existing `tagChipsHtml(tags, type)` (`static/app.js:528-533`) unchanged; no new functions, classes, or call sites elsewhere.

- [ ] **Step 1: Append deck-tag chips to the row markup**

In `static/app.js`, inside `buildDeckTextRow`, replace:

```js
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>`;
```

with:

```js
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>
    ${tagChipsHtml(card.deck_tags, 'deck-tag')}`;
```

(`tagChipsHtml` already returns `''` when `card.deck_tags` is empty/undefined, so untagged cards get no extra markup.)

- [ ] **Step 2: Make the chips lay out inline on the row, and let the row wrap if needed**

In `static/style.css`, replace:

```css
.deck-text-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 3px 4px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.1s;
}
```

with:

```css
.deck-text-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  padding: 3px 4px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.1s;
}
/* tagChipsHtml() wraps its chips in a `.tag-chips-row` block built for a
   below-content layout (Grid tile, modal); here it needs to disappear
   from the box model so its `.tag-chip` children become ordinary inline
   flex items of `.deck-text-row` instead. */
.deck-text-row .tag-chips-row {
  display: contents;
}
```

(Only `flex-wrap: wrap;` is added to `.deck-text-row`, and the new `.deck-text-row .tag-chips-row` rule is added after it. The `:hover`/`.focused` rules immediately following are untouched.)

- [ ] **Step 3: Manual verification**

Run `uvicorn app:app --reload` from the repo root, open `http://localhost:8000`, open a deck in Text view.

- A card with one or more deck tags: confirm its chips render inline after the mana cost, same chip colors/style as Grid view's deck-tag chips.
- A card with no deck tags: confirm its row is pixel-identical to before this change (no empty gap, no layout shift).
- A card with several deck tags (add a few via the modal's tag editor if none exist yet): confirm the row wraps onto a second line rather than overflowing horizontally, and hover/click on the row still work correctly with the wrapped layout.
- Confirm collection tags still do NOT appear on Text view (out of scope, unchanged).
- Confirm Grid view and the modal's tag chips are visually unaffected (the CSS change is scoped to `.deck-text-row .tag-chips-row` only).

- [ ] **Step 4: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: show deck tags inline on deck Text view rows"
```
