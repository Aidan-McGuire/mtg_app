# Owned-card badge on Cards page

## Problem

The Cards page (`#card-grid`) shows every card in the database, owned or not.
The only current indicator of ownership is the quantity number in the qty
row below each tile turning gold/bold when `quantity > 0`
(`buildCardTile`, `static/app.js`). That's easy to miss while scanning a
grid of card art, since attention is on the images, not the small text
below them.

## Goal

Add a clear at-a-glance visual indicator directly on the card image so
owned cards stand out while browsing/scanning the grid.

## Approach

Frontend-only change. `state.collection` (card id → quantity, loaded by
`loadCollection()`) already has everything needed; `buildCardTile()`
already computes `qty(card.id)`.

### Badge markup

Inside `.card-img-wrap`, add a badge element as a sibling of the `<img>`
(or placeholder div), rendered only when `qty(card.id) > 0`:

```html
<div class="card-img-wrap">
  <div class="card-owned-badge" title="Owned">✓</div>
  <img ...>
</div>
```

When quantity is 0, the badge element is omitted entirely (not just
hidden), matching how other conditional bits of `buildCardTile` (e.g.
`tagChipsHtml`) already work.

### Styling

`.card-owned-badge`:
- Small circle, ~20px diameter
- `position: absolute; top: 6px; left: 6px;`
- Background `var(--accent)`, checkmark glyph in a dark color
  (`#111`, matching `.qty-btn:hover`'s accent/dark pairing)
- `.card-img-wrap` needs `position: relative` for the absolute badge to
  anchor correctly

This reuses the existing gold accent already associated with "owned" state
(`.qty-label.owned`, `.qty-btn:hover`) rather than introducing a new color.

### Live updates

`refreshQtyInDOM(cardId)` (app.js:488) already runs after every
increment/decrement and updates all `[data-qty-for="cardId"]` elements
across whichever tiles are currently rendered. Extend it to also find the
corresponding `.card-img-wrap` for each affected tile and add/remove the
`.card-owned-badge` element so the badge appears/disappears immediately,
without a full grid re-render — same live-update pattern already used for
the qty label.

Concretely: give each `.card-img-wrap` a `data-owned-wrap-for="${card.id}"`
attribute (mirroring `data-qty-for`) so `refreshQtyInDOM` can locate it
without re-querying the whole tile structure.

### Scope

**Revised after initial implementation and live review:** the badge shows
on the Cards page grid and on Deck view tiles. It does **not** show on the
Collection page grid — every tile there is owned by definition, so the
badge would be on 100% of tiles and convey nothing.

`buildCardTile()` is shared by the Cards grid and the Collection grid.
Give it an options parameter, `buildCardTile(card, { showOwnedBadge = true } = {})`:
- Cards grid (`appendCards`) calls it with the default (badge on).
- Collection grid (`renderCollectionGrid`, both the grouped and ungrouped
  branches) calls it with `{ showOwnedBadge: false }`.
- When `showOwnedBadge` is false, both the badge markup *and* the
  `data-owned-wrap-for` attribute are omitted — not just the badge. If the
  attribute were left on Collection tiles, `refreshQtyInDOM` would insert a
  badge into a Collection tile the next time any card's quantity changes
  while the Collection page happens to be rendered, silently reintroducing
  the badge there.

Deck view tiles (`buildDeckCardTile`) get their own, independent badge:
the badge reflects **collection ownership** (`qty(card.id) > 0`), not the
deck's own copy count (`card.quantity`, the number of copies of that card
in this deck — a different field, always shown in the deck tile's own qty
row regardless of collection ownership). Add the same
`data-owned-wrap-for="${card.id}"` attribute to `.deck-card-img-wrap`;
because `refreshQtyInDOM` already queries by this attribute name
document-wide, no change to `refreshQtyInDOM` itself is needed — deck
tiles are picked up automatically the same way Cards-grid tiles are.

Out of scope:
- The card detail modal (`openModal`, app.js:695) is built by separate
  markup, not `buildCardTile`/`buildDeckCardTile`, and already has an
  explicit "owned" text label next to its qty stepper. No change needed
  there.

## Testing

This is a frontend-only visual change with no new API endpoints or schema
changes, so no new automated backend tests apply (existing suite in
`tests/` covers API/DB behavior only). Verification is manual in the
browser:
- An owned card shows the checkmark badge on its image on the Cards page;
  an unowned card does not.
- Incrementing a card's quantity from 0 → 1 makes the badge appear live on
  any currently-rendered tile for that card (Cards grid or Deck view),
  without needing to reload/re-search.
- Decrementing a card's quantity to 0 makes the badge disappear live.
- The Collection page grid shows no badges at all (every tile is owned,
  so the badge would be redundant there).
- In Deck view, a card owned in the collection shows the badge regardless
  of how many copies are in the deck; a card in the deck that isn't owned
  in the collection shows no badge.
