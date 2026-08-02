# Owned-card badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a checkmark badge on the card image of any card that's owned (quantity > 0 in the collection). Shown on the Cards page grid and on Deck view tiles; NOT shown on the Collection page grid (every tile there is owned by definition, so it'd be redundant). Updates live on increment/decrement.

**Architecture:** Frontend-only change to the shared `buildCardTile()` tile renderer, `buildDeckCardTile()`, and their live-update sibling `refreshQtyInDOM()` in `static/app.js`, plus new CSS in `static/style.css`. No backend, API, or schema changes.

**Tech Stack:** Vanilla JS, plain CSS. No JS test runner exists in this repo — verification is manual in the browser (see spec at `docs/superpowers/specs/2026-08-01-owned-card-badge-design.md`).

## Global Constraints

- Badge is a checkmark ("✓"), not a quantity count.
- Badge appears on the Cards grid and on Deck view tiles. Badge does NOT appear on the Collection grid — `buildCardTile(card, { showOwnedBadge: false })` suppresses both the badge markup and the `data-owned-wrap-for` attribute there, so live updates never re-add it.
- On deck tiles, the badge reflects collection ownership (`qty(card.id) > 0`), which is independent of the deck's own per-card quantity (`card.quantity`, shown separately in the deck tile's qty row).
- Do not modify the modal (`openModal`, app.js:695) — out of scope per spec.
- Reuse the existing gold `var(--accent)` color already associated with "owned" state (`.qty-label.owned`, `.qty-btn:hover`) rather than introducing a new color.
- Badge element must be entirely omitted from markup when quantity is 0 (not just hidden via CSS) — matches how `tagChipsHtml()` already conditionally omits markup in the same function.

## Revision Note (post-Task-1)

Task 1 (below) shipped the badge on both the Cards grid and the Collection
grid, with no deck-tile support — that was the originally approved scope.
After live testing, the requirement changed: no badge on Collection,
badge added to Deck view instead. Task 2 carries that revision. Task 1's
text is left as-executed, for history.

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

---

### Task 2: Move the badge from Collection to Deck view

**Files:**
- Modify: `static/app.js` — `buildCardTile()`, its two Collection-grid call sites, and `buildDeckCardTile()`
- Modify: `static/style.css` — `.deck-card-img-wrap` rule

**Interfaces:**
- Consumes: `qty(cardId)` (unchanged), the `data-owned-wrap-for` attribute and `.card-owned-badge` CSS class from Task 1 (unchanged — reused as-is), `refreshQtyInDOM()` (unchanged — no edits needed; it already queries `[data-owned-wrap-for="cardId"]` document-wide, so once deck tiles carry that attribute they're picked up automatically).
- Produces: `buildCardTile(card, { showOwnedBadge = true } = {})` — an options parameter callers can pass to suppress the badge.

- [ ] **Step 1: Add the `showOwnedBadge` option to `buildCardTile()`**

Find `buildCardTile()` (as left by Task 1):

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

Change the signature and the `card-img-wrap` line so the badge markup and the tracking attribute are both conditional on `showOwnedBadge`:

```js
function buildCardTile(card, { showOwnedBadge = true } = {}) {
  const q = qty(card.id);
  const div = document.createElement('div');
  div.className = 'card-tile';
  div.dataset.id = card.id;
  div.tabIndex = -1;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  const ownedBadgeHtml = (showOwnedBadge && q > 0) ? `<div class="card-owned-badge" title="Owned">✓</div>` : '';
  const ownedWrapAttr = showOwnedBadge ? ` data-owned-wrap-for="${card.id}"` : '';

  const meta = [card.mana_cost, card.cmc != null ? `${card.cmc} CMC` : null]
    .filter(Boolean).join(' · ');

  div.innerHTML = `
    <div class="card-img-wrap"${ownedWrapAttr}>${ownedBadgeHtml}${imgHtml}</div>
    <div class="card-info">
```

Leave the rest of the function unchanged. Leave the Cards-grid call site (`appendCards`, calls `buildCardTile(card)` with no second argument) unchanged — it gets the default `showOwnedBadge: true`.

- [ ] **Step 2: Suppress the badge on both Collection-grid call sites**

There are two places `buildCardTile` is invoked for the Collection grid, in `renderCollectionGrid()`:

```js
  if (collectionState.groupBy !== 'none') {
    const groups = groupCards(filtered, 'collection_tags');
    renderGroupedGrid(grid, groups, buildCardTile, collectionGroupCollapsed);
  } else {
    const frag = document.createDocumentFragment();
    for (const card of filtered) frag.appendChild(buildCardTile(card));
    grid.appendChild(frag);
  }
```

Change both to pass `{ showOwnedBadge: false }`. `renderGroupedGrid` calls its `buildTileFn` argument as `buildTileFn(card)` (one argument), so the grouped branch needs a wrapping arrow function:

```js
  if (collectionState.groupBy !== 'none') {
    const groups = groupCards(filtered, 'collection_tags');
    renderGroupedGrid(grid, groups, card => buildCardTile(card, { showOwnedBadge: false }), collectionGroupCollapsed);
  } else {
    const frag = document.createDocumentFragment();
    for (const card of filtered) frag.appendChild(buildCardTile(card, { showOwnedBadge: false }));
    grid.appendChild(frag);
  }
```

- [ ] **Step 3: Add the badge to `buildDeckCardTile()`**

Currently:

```js
function buildDeckCardTile(card) {
  const div = document.createElement('div');
  div.className = 'deck-card-tile' + (card.is_commander ? ' is-commander' : '');
  div.dataset.id = card.id;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  div.innerHTML = `
    <div class="deck-card-img-wrap">${imgHtml}</div>
    <div class="deck-card-info">
```

Change it to compute collection quantity and add the same badge markup and tracking attribute used on the Cards grid:

```js
function buildDeckCardTile(card) {
  const q = qty(card.id);
  const div = document.createElement('div');
  div.className = 'deck-card-tile' + (card.is_commander ? ' is-commander' : '');
  div.dataset.id = card.id;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  const ownedBadgeHtml = q > 0 ? `<div class="card-owned-badge" title="Owned">✓</div>` : '';

  div.innerHTML = `
    <div class="deck-card-img-wrap" data-owned-wrap-for="${card.id}">${ownedBadgeHtml}${imgHtml}</div>
    <div class="deck-card-info">
```

Leave the rest of the function (the `deck-card-info` block, event listeners, return) unchanged. Do NOT touch `card.quantity` or the tile's own `qty-label` — that field is the deck's copy count, a separate concept from collection ownership, and stays as-is.

Do not modify `refreshQtyInDOM()` — it already does `document.querySelectorAll('[data-owned-wrap-for="${cardId}"]')` across the whole document, so it will find and update these new deck-tile wraps with no changes.

- [ ] **Step 4: Add `position: relative` to `.deck-card-img-wrap`**

Open `static/style.css`, find:

```css
.deck-card-img-wrap {
```

Add `position: relative;` to that rule's declaration block (same reasoning as Task 1's change to `.card-img-wrap`: the badge is `position: absolute` and needs a positioned ancestor to anchor to).

- [ ] **Step 5: Manually verify in the browser**

Run: `uvicorn app:app --reload` (from the project root; make sure the DB has imported card data — run `python importer.py` first if `mtg.db` is freshly initialized and empty)

Then in a browser:
1. Cards page: confirm badges still show/hide correctly on owned/unowned cards (regression check for Task 1 behavior, now gated by the new parameter).
2. Collection page: confirm NO tile shows a badge, even though every tile there has quantity > 0.
3. Open (or create) a deck and add a card you own (quantity > 0 in the collection) — confirm its deck tile shows the badge.
4. Add a card to the deck that you do NOT own (quantity 0 in the collection) — confirm its deck tile shows no badge, even though its deck quantity (copies in the deck) is 1 or more.
5. From the Cards or Collection page, increment a card that's also currently in the open deck — confirm the badge appears live on its deck tile too, without navigating away and back.
6. Open the card detail modal from a deck tile — confirm it's unchanged (no badge), matching Task 1's modal exclusion.

If any check fails, fix the code before proceeding — there is no automated test to fall back on for this change.

- [ ] **Step 6: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: move owned badge from Collection grid to Deck view"
```
