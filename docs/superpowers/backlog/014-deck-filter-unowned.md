---
id: 014
title: Deck filter for cards not owned
priority: medium
status: in-progress
branch: item/14-deck-filter-for-cards-not-owned
created: 2026-08-26
---

## Problem

A deck can contain cards the player doesn't own any copies of (collection
quantity 0). There's currently no way to filter a deck view down to just
those cards — useful as a shopping-list view. The existing filter model
(`makeFilterModel` in `static/app.js`) already has a directly analogous
boolean toggle, `hideLands`, rendered as a button in `buildFilterControls`
(`static/app.js`) and applied in `applyFilters`.

## Approach

Add a new boolean filter, `unownedOnly`, following the exact same pattern
as `hideLands`:

- `makeFilterModel` (`static/app.js`): add `unownedOnly: false` to the
  default model (alongside the existing `hideLands: false`).
- `applyFilters` (`static/app.js`): add a check —
  `if (model.unownedOnly && qty(c.id) > 0) return false;` — using the
  existing `qty(cardId)` helper (reads `state.collection`, the same source
  the grid/text owned indicators use). Not owned = collection quantity is
  exactly 0 (not "fewer than deck needs").
- `buildFilterControls` (`static/app.js`): add a toggle button next to the
  existing "Hide lands" button (`landsBtn`), same active/inactive class
  toggling (`.active`), same reset behavior in the filter-clear path (the
  function that currently preserves `hideLands` across a filter-bar reset,
  around the `Object.assign(model, makeFilterModel({ sort: model.sort, dir:
  model.dir, text: keepText, hideLands: model.hideLands }))` call — decide
  whether `unownedOnly` should also survive a filter-bar reset the same way
  `hideLands` does; since they're the same kind of persistent toggle,
  `unownedOnly` should be preserved identically).
- This is deck-view only (matches the "not owned in deck" framing and the
  fact that `hideLands` itself is only wired into the **deck** filter bar
  today, per `buildFilterControls(document.getElementById('deck-filter-controls'), ...)`
  — do not add it to the card browser or collection browser filter bars).
- Button label/icon: reuse the existing action-btn visual style
  (`hide-lands-btn action-btn` classes) with a label like "Unowned only" —
  match whatever short label convention the existing lands button uses.

## Acceptance criteria

- [ ] Deck view's filter bar has a new toggle button that, when active,
      shows only deck cards with collection quantity 0.
- [ ] Toggling it off restores the full (other-filters-permitting) list.
- [ ] It combines correctly with other active filters (e.g. `hideLands` +
      `unownedOnly` together — AND semantics, matching how every other
      filter in `applyFilters` composes).
- [ ] It persists across a filter-bar "clear filters" action the same way
      `hideLands` does (survives; not reset to false).
- [ ] Card browser and collection browser filter bars are unchanged — no
      new button there.
