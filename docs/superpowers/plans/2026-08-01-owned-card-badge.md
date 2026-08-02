# Owned-card badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a checkmark badge on the card image of any card that's owned (quantity > 0), on both the Cards page grid and Collection page grid, updating live on increment/decrement.

**Architecture:** Frontend-only change to the shared `buildCardTile()` tile renderer and its live-update sibling `refreshQtyInDOM()` in `static/app.js`, plus new CSS in `static/style.css`. No backend, API, or schema changes.

**Tech Stack:** Vanilla JS, plain CSS. No JS test runner exists in this repo — verification is manual in the browser (see spec at `docs/superpowers/specs/2026-08-01-owned-card-badge-design.md`).

## Global Constraints

- Badge is a checkmark ("✓"), not a quantity count.
- Badge appears wherever `buildCardTile()` renders a tile (Cards grid and Collection grid) — do not special-case it away on the Collection grid.
- Do not modify the modal (`openModal`, app.js:695) or deck tiles (`buildDeckCardTile`) — out of scope per spec.
- Reuse the existing gold `var(--accent)` color already associated with "owned" state (`.qty-label.owned`, `.qty-btn:hover`) rather than introducing a new color.
- Badge element must be entirely omitted from markup when quantity is 0 (not just hidden via CSS) — matches how `tagChipsHtml()` already conditionally omits markup in the same function.

---

### Task 1: Owned badge on card tiles, with live updates

**Files:**
- Modify: `static/app.js` — `buildCardTile()` (currently app.js:515-551) and `refreshQtyInDOM()` (currently app.js:488-495)
- Modify: `static/style.css` — `.card-img-wrap` rule (currently style.css:145-151) and the quantity-controls section (around style.css:190-220)

**Interfaces:**
- Consumes: existing `qty(cardId)` (app.js:450-452, returns `state.collection[cardId] || 0`), existing `esc()` helper, existing `data-qty-for` attribute pattern used for live updates.
- Produces: new `data-owned-wrap-for="${card.id}"` attribute on the `.card-img-wrap` element inside every tile built by `buildCardTile()`. No other task depends on this, since this is the only task in the plan.

This is a single cohesive task — the badge markup, its CSS, and its live-update wiring all have to land together for any of it to be meaningfully testable (a badge that renders but never updates, or updates but has no CSS, isn't a working deliverable on its own).

- [ ] **Step 1: Add the badge markup to `buildCardTile()`**

Open `static/app.js` and find `buildCardTile()`. Currently:

```js
function buildCardTile(card) {
  const q = qty(card.id);
  const div = document.createElement('div');
  div.className = 'card-tile';
  div.dataset.id = card.id;
  div.tabIndex = -1;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  const meta = [card.mana_cost, card.cmc != null ? `${card.cmc} CMC` : null]
    .filter(Boolean).join(' · ');

  div.innerHTML = `
    <div class="card-img-wrap">${imgHtml}</div>
    <div class="card-info">
```

Change the `card-img-wrap` line to add the `data-owned-wrap-for` attribute and conditionally include the badge:

```js
function buildCardTile(card) {
  const q = qty(card.id);
  const div = document.createElement('div');
  div.className = 'card-tile';
  div.dataset.id = card.id;
  div.tabIndex = -1;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  const ownedBadgeHtml = q > 0 ? `<div class="card-owned-badge" title="Owned">✓</div>` : '';

  const meta = [card.mana_cost, card.cmc != null ? `${card.cmc} CMC` : null]
    .filter(Boolean).join(' · ');

  div.innerHTML = `
    <div class="card-img-wrap" data-owned-wrap-for="${card.id}">${ownedBadgeHtml}${imgHtml}</div>
    <div class="card-info">
```

Leave the rest of the function (the `card-info` block, event listeners, return) unchanged.

- [ ] **Step 2: Extend `refreshQtyInDOM()` to add/remove the badge live**

Currently:

```js
function refreshQtyInDOM(cardId) {
  const q = qty(cardId);
  // Update all qty labels for this card (tile + modal)
  document.querySelectorAll(`[data-qty-for="${cardId}"]`).forEach(el => {
    el.textContent = q;
    el.className = 'qty-label' + (q > 0 ? ' owned' : '');
  });
}
```

Change it to also sync the badge on every matching `.card-img-wrap`:

```js
function refreshQtyInDOM(cardId) {
  const q = qty(cardId);
  // Update all qty labels for this card (tile + modal)
  document.querySelectorAll(`[data-qty-for="${cardId}"]`).forEach(el => {
    el.textContent = q;
    el.className = 'qty-label' + (q > 0 ? ' owned' : '');
  });
  // Add/remove the owned badge on every rendered tile for this card
  document.querySelectorAll(`[data-owned-wrap-for="${cardId}"]`).forEach(wrap => {
    let badge = wrap.querySelector('.card-owned-badge');
    if (q > 0 && !badge) {
      badge = document.createElement('div');
      badge.className = 'card-owned-badge';
      badge.title = 'Owned';
      badge.textContent = '✓';
      wrap.prepend(badge);
    } else if (q === 0 && badge) {
      badge.remove();
    }
  });
}
```

- [ ] **Step 3: Add CSS for the badge**

Open `static/style.css`. Find the `.card-img-wrap` rule (around line 145):

```css
.card-img-wrap {
  width: 100%;
  flex: 1;
  min-height: 0;
  background: var(--surface2);
  overflow: hidden;
}
```

Add `position: relative;` so the badge can anchor to it:

```css
.card-img-wrap {
  width: 100%;
  flex: 1;
  min-height: 0;
  background: var(--surface2);
  overflow: hidden;
  position: relative;
}
```

Then add a new rule for the badge itself. Place it directly after the quantity-controls section (after the `.qty-label.owned` rule, around line 220):

```css
.card-owned-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent);
  color: #111;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  pointer-events: none;
}
```

- [ ] **Step 4: Manually verify in the browser**

Run: `uvicorn app:app --reload` (from the project root)

Then in a browser at `http://localhost:8000`:
1. On the Cards page, search for a card you know has quantity 0 (or any card, if the collection is empty) — confirm no badge appears on its tile.
2. Click the `+` button on that card's tile to increment its quantity to 1 — confirm the checkmark badge appears immediately in the top-left corner of the card image, with no page reload.
3. Click `−` to bring it back to 0 — confirm the badge disappears immediately.
4. Switch to the Collection page (only cards with quantity > 0 appear there) — confirm every tile shows the badge.
5. Open the card detail modal (click a tile) — confirm the modal is unchanged (still just the text "owned" label, no badge), since the modal is out of scope.

If any check fails, fix the code before proceeding — there is no automated test to fall back on for this change.

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: show owned badge on card tiles"
```
