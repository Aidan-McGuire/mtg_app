---
id: 018
title: Built flag on decks
priority: medium
status: in-review
branch: item/18-built-flag-on-decks
created: 2026-08-26
---

## Problem

There's no way to mark a deck as physically "built" (assembled with real
cards) versus a theoretical list. This is a prerequisite for items 019
(collection filter hiding fully-allocated cards) and 020 (deck-page
indicator for cards locked up in other built decks) — both need a `built`
flag on decks to know which decks' cards count as "spoken for." This item
ships the flag and its toggle UI standalone; 019/020 build on top of it.

## Approach

- `main.py`: bump `migrate_database()` — add a `version < 7` block:
  `ALTER TABLE decks ADD COLUMN built INTEGER NOT NULL DEFAULT 0;` then
  `UPDATE schema_version SET version = 7;`, following the exact pattern of
  the existing `version < 4` (`is_considering`) migration block.
- `app.py`:
  - `list_decks()` (`GET /api/decks`): add `d.built` to the `SELECT`
    alongside `d.id, d.name, d.created_at`.
  - Rename the `DeckRename` Pydantic model to `DeckUpdate` with both fields
    optional: `name: str | None = None`, `built: bool | None = None`.
    Update `rename_deck` (`PATCH /api/decks/{deck_id}`) to match the exact
    pattern `update_deck_card` already uses for `DeckCardUpdate`: fetch the
    current `name, built` row first, fall back to the current value for
    whichever field is omitted from the request body, then `UPDATE decks
    SET name = ?, built = ? WHERE id = ?`. This keeps the existing
    rename-only call site (which sends only `{name}`) working unchanged,
    since `built` simply falls back to its current value when omitted.
- `static/app.js`:
  - `API`: no new call needed — reuse the existing rename call
    (`fetch(`/api/decks/${id}`, {method:'PATCH', body: JSON.stringify(...)})`)
    with a `{ built: !currentValue }` body instead of `{ name }`. Add a
    `toggleDeckBuilt()` function mirroring `toggleConsidering()`/the
    existing rename-button handler's fetch-and-refresh pattern.
  - `renderDeckSwitchResults()` (~line 1913): add a small badge span to the
    `.deck-list-item` template when `deck.built` is true, e.g.
    `${deck.built ? '<span class="deck-list-built-badge" title="Built">✓</span>' : ''}`,
    placed next to `.deck-list-count`.
  - Wherever the deck editor header's action buttons are wired up (near the
    existing `deck-rename-btn`/`deck-delete-btn` click handlers, ~line
    2639), add a new `deck-built-btn` click handler calling
    `toggleDeckBuilt()`. After toggling, update the button's own `.active`
    class from the response so it reflects the new state immediately
    (mirroring `deck-cmd-btn`'s `.active` toggling pattern).
- `static/index.html`: add `<button id="deck-built-btn" class="action-btn">Built</button>` next to the existing `#deck-rename-btn`/`#deck-delete-btn` buttons in the deck editor header (~line 67-68).
- `static/style.css`: add `.action-btn.active` — no, be specific: add
  `#deck-built-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }`
  reusing the exact same highlight already defined for `.hide-lands-btn.active`
  and `.unowned-only-btn.active` (don't invent a new color). Also add
  `.deck-list-built-badge { color: var(--accent); margin-left: 4px; }` (or
  similar, consistent with other small badge/label styling already in the
  file) for the switcher-list badge.
- The button's label text stays constant ("Built"); only its `.active`
  class (and thus its highlight) changes — same convention as Hide Lands
  and Unowned Only, which don't change their label text on toggle either.
- No default-value complications: `built` defaults to `0` (not built) for
  every existing and newly-created deck.

## Acceptance criteria

- [x] A deck can be toggled between built and not-built via a button in the
      deck editor header, and the toggle persists (reload the page, still
      set).
- [x] The button visually reflects the current state via the same
      accent-color highlight convention already used by Hide Lands/Unowned
      Only, not a new visual language.
- [x] The deck-switcher list shows a small badge on decks that are built,
      and no badge on decks that aren't.
- [x] Renaming a deck (existing functionality) still works unchanged and
      does not reset its `built` flag.
- [x] All existing decks default to `built = 0` after the migration runs.
