---
id: 024
title: Add commander toggle to deck list (text) view
priority: medium
status: in-review
branch: item/24-add-commander-toggle-to-deck-list-text-view
created: 2026-08-27
---

## Problem

The deck grid view's card tile (`buildDeckCardTile` in `static/app.js`) has a
`.deck-cmd-btn` (♛) button that calls `toggleCommander(card.id)` to designate
a card as the deck's commander. The deck list/text view's row
(`buildDeckTextRow`) has the equivalent toggle for "Considering"
(`.deck-considering-btn`) but no way to toggle commander at all — a user in
list view has to switch to grid view to designate or un-designate a
commander.

## Approach

Add a `.deck-cmd-btn` (♛) button to `buildDeckTextRow`, mirroring
`buildDeckCardTile`'s existing markup and wiring exactly:
- Same title (`Toggle commander`) and `active` class when `card.is_commander`
  is true.
- Same click handler, wired to the existing `toggleCommander(card.id)`
  (`static/app.js:2449`) — no backend or state-model changes needed, since
  `toggleCommander` already calls `renderDeckContent()`, which re-renders
  whichever view (grid or text) is currently active.
- Placed among the row's existing action controls (alongside the
  Considering toggle and remove button), consistent with where it sits in
  the grid tile relative to the equivalent controls.

No new keyboard shortcut — the grid view's commander toggle is mouse-only
today (the existing `c` key toggles Considering, not commander), so the list
view stays at parity rather than gaining a shortcut the grid view lacks.

No CSS changes: `.deck-cmd-btn` styling in `static/style.css` is already
generic (not grid-tile-scoped), the same way `.deck-considering-btn` is
already shared between the grid tile and the text row.

**Out of scope:** the grid tile gets a gold border via
`.deck-card-tile.is-commander` (`static/style.css:813`) — the text row has no
equivalent container-level highlight for any state today (not even for
Considering), so this doesn't add one; the button's own `active` state is
sufficient, consistent with existing list-view conventions.

## Acceptance criteria

- [ ] In the deck's list (text) view, each row has a ♛ button matching the
      grid view's commander toggle.
- [ ] Clicking it on a non-commander row designates that card as the deck's
      commander (any previous commander is un-designated, matching existing
      `toggleCommander`/backend single-commander behavior) and the button
      shows the `active` state.
- [ ] Clicking it again on the current commander un-designates it.
- [ ] The change is reflected immediately in both views — toggling in list
      view and then switching to grid view (or vice versa) shows the same
      commander state without a reload.
- [ ] A row currently marked as commander does not show a Considering toggle
      (matching existing behavior already in place for both views).
