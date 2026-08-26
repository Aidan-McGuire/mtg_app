---
id: 019
title: Collection filter to hide cards fully allocated to built decks
priority: medium
status: in-progress
branch: item/19-collection-filter-to-hide-cards-fully-allocated-to-built-decks
created: 2026-08-26
---

## Problem

Once a deck can be marked "built" (item 018), the collection view has no
way to show only cards that are actually free to use — i.e. hide a card
if every owned copy is already committed to a built deck, but keep
showing it if you own more copies than are allocated. This is useful for
seeing what's actually available when planning a new deck.

**Depends on item 018** (the `decks.built` column) — implement 018 first;
this item's queries reference `decks.built` and `deck_cards.is_considering`,
neither of which is meaningful without it.

"Allocated" only counts a built deck's main-deck cards, not its
Considering section — Considering cards are speculative and shouldn't
lock up a copy from appearing free elsewhere (see item 018's design
discussion; `deck_cards.is_considering` already distinguishes this).

## Approach

- `app.py`, `get_collection()` (`GET /api/collection`): add an
  `allocated_qty` column to the `SELECT`, computed via a correlated
  subquery:
  ```sql
  COALESCE((
      SELECT SUM(dc.quantity) FROM deck_cards dc
      JOIN decks d ON d.id = dc.deck_id
      WHERE dc.card_id = c.id AND dc.is_considering = 0 AND d.built = 1
  ), 0) AS allocated_qty
  ```
  added alongside the existing `col.quantity` column in the same query.
  No changes to the `WHERE col.quantity > 0` clause or anything else in
  the function.
- `static/app.js`:
  - `makeFilterModel` (~line 188): add `hideFullyAllocated: false` to the
    default model, alongside `hideLands`/`unownedOnly`.
  - `applyFilters` (~line 240): add
    `if (model.hideFullyAllocated && (c.allocated_qty || 0) >= c.quantity) return false;`
    — note this uses `c.quantity` (the row's owned quantity, present on
    collection rows) and the new `c.allocated_qty` field, not the `qty()`
    helper (which reads the global `state.collection` map and doesn't
    carry `allocated_qty` — this filter only makes sense on collection
    rows, which already carry both fields directly from `/api/collection`).
  - `buildFilterControls` (~line 383): this toggle is COLLECTION VIEW
    ONLY. Add a new optional config flag (e.g. `showHideAllocatedToggle`,
    following the same opt-in-per-call-site pattern used for other
    view-specific toggles) and a button following the exact same
    active/inactive pattern as `landsBtn`/`unownedBtn` — label it
    something like "Hide Allocated". Wire the flag on only the
    `buildFilterControls(document.getElementById('collection-filter-controls'), ...)`
    call site (~line 1560) — do not add it to the card browser or deck
    filter bars.
  - Filter-bar reset path (~line 513-527): add `hideFullyAllocated:
    model.hideFullyAllocated` to the preserved-fields `Object.assign`,
    same as the other persistent toggles.
- `static/style.css`: reuse the existing `.action-btn` / accent-highlight
  `.active` convention (see item 018's `#deck-built-btn.active` for the
  exact color values) for the new button's active state — don't invent a
  new visual treatment.

## Acceptance criteria

- [ ] Collection view's filter bar has a new toggle that, when active,
      hides any card whose owned quantity is entirely accounted for by
      built decks' main-deck (non-Considering) cards.
- [ ] A card with more owned copies than allocated (e.g. own 3, 2
      allocated to built decks) stays visible when the toggle is active.
- [ ] A card allocated only to Considering sections of built decks (never
      the main deck) is treated as unallocated — never hidden by this
      toggle on that basis alone.
- [ ] A card allocated to a deck that is NOT built doesn't count toward
      `allocated_qty` at all.
- [ ] The toggle persists across a filter-bar "clear filters" action, same
      as `hideLands`/`unownedOnly`.
- [ ] Card browser and deck filter bars are unchanged — no new button
      there.
