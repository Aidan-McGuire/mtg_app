---
id: 026
title: Detail modal shows read-only owned count when opened from a deck
priority: medium
status: queued
branch:
created: 2026-08-27
---

## Problem

`openModal(card, deckContext)` in `static/app.js` only renders the
`.modal-collection` block (owned-count display + `+`/`−` stepper) when
`deckContext` is falsy:

```js
const collectionHtml = deckContext ? '' : `
    <div class="modal-collection">
      <button class="qty-btn" data-action="dec" title="Remove (-)">−</button>
      <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
      <button class="qty-btn" data-action="inc" title="Add (+)">+</button>
      <span class="qty-owned-label">owned</span>
    </div>`;
```

This is deliberate — the deck page already has its own quantity control on
each tile/row, and showing a second editable stepper in the modal would be a
confusing duplicate control. But the tradeoff is that opening a card's
detail modal from within a deck (grid tile or list row click) shows *no*
owned-count information at all today, unlike opening the same card's modal
from the Cards or Collection page.

## Approach

When `deckContext` is set, render a read-only variant of `.modal-collection`
— same `qty-label`/`qty-owned-label` markup, same `data-qty-for="${card.id}"`
attribute (so it stays live-synced by the existing `refreshQtyInDOM`, which
already updates every element matching that selector on any quantity
change), just without the two `.qty-btn` buttons and without attaching their
click handlers:

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

The existing `if (!deckContext) { ...attach qty-btn listeners... }` guard
already skips button wiring for the deck-context case, so no JS changes are
needed there beyond the markup swap above.

**Out of scope:** no change to non-deck-context modal behavior, no new
CSS beyond whatever spacing `.modal-collection-readonly` needs to look right
without buttons (likely none, `.modal-collection`'s existing
`display:flex; gap:8px` already accommodates just the two spans).

## Acceptance criteria

- [ ] Opening a card's detail modal from a deck (grid tile or list row) shows
      a read-only "N owned" indicator using the same visual style as the
      Cards/Collection-page modal's owned label (bold/accent-colored when
      `N > 0`).
- [ ] No `+`/`−` buttons appear in the deck-context modal's owned-count area.
- [ ] Incrementing/decrementing that card's owned count elsewhere (e.g. from
      the Collection page in another tab, or via collection import) while
      the deck-context modal is open updates the displayed count live,
      matching existing `refreshQtyInDOM` behavior.
- [ ] Opening the modal from the Cards or Collection page is unchanged
      (still shows the editable stepper).
