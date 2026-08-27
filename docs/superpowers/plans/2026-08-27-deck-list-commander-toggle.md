# Plan: Add commander toggle to deck list (text) view

Backlog item: `docs/superpowers/backlog/024-deck-list-commander-toggle.md`

## Summary

`buildDeckTextRow` in `static/app.js` is missing a `.deck-cmd-btn` (♛) button
that `buildDeckCardTile` already has. Add it, mirroring the grid tile's
markup and wiring exactly (same title, same `active` class condition, same
click handler calling `toggleCommander(card.id)`). No backend or CSS changes
needed.

## Steps

1. In `buildDeckTextRow` (static/app.js, ~line 2241-2272), add the
   `.deck-cmd-btn` button to `row.innerHTML`, placed among the row's action
   controls in the same relative position as in `buildDeckCardTile`
   (immediately after `consideringBtnHtml`, before the remove-button's kbd
   hint).
2. Wire its click handler right after the existing `consideringBtn` wiring,
   calling `toggleCommander(card.id)` with `e.stopPropagation()`, matching
   `buildDeckCardTile`'s wiring.
3. Manually verify against acceptance criteria by reading the code:
   - Button present in every row, `active` class when `card.is_commander`.
   - Click toggles commander via existing `toggleCommander`, which already
     re-renders whichever view is active — so grid/text views stay in sync.
   - Commander rows already suppress `consideringBtnHtml`, so a commander
     row shows no Considering toggle (unchanged, already-existing behavior).
4. Check JS syntax with node (`/opt/homebrew/bin/node --check static/app.js`
   or similar).
5. Run `python3 -m pytest` (initialize `mtg.db` via `python3 main.py` first
   if needed).
6. Commit.

## Out of scope

- No CSS changes (`.deck-cmd-btn` styling is already shared/generic).
- No new keyboard shortcut.
- No gold-border-style container highlight for commander rows in text view.
- Do not touch the `?`/`×`/`<kbd>` markup that item 025 changed elsewhere —
  this worktree predates that merge and should not "fix" it.
