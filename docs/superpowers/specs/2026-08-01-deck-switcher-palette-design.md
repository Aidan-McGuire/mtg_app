# Decks page: replace sidebar with a deck-switcher palette

## Goal

The persistent 220px-wide deck-list sidebar on the Decks page takes up
space (width, always-visible height) that isn't needed — with dozens of
decks, the list doesn't need to stay pinned on screen. Replace it with an
on-demand searchable palette, mirroring the existing add-card palette
pattern, so the deck editor gets the full width and the list only appears
when invoked.

## Scope

- **In:** removing the sidebar, a new deck-switcher palette (search +
  results + New/Import actions), a compact header control and keyboard
  shortcut to open it, auto-open behavior when no deck is selected.
- **Out:** any backend/API changes, changes to deck editor internals
  (grid/text view, filters, add-card palette), deck reordering/pinning,
  fuzzy/ranked search (plain substring match is enough at "dozens" scale).

## Layout changes (`static/index.html`, `static/style.css`)

- Remove `<aside class="decks-sidebar">` and its contents (`#deck-list`,
  the `+ New` / `↑ Import` buttons) entirely.
- `.deck-main` becomes the sole child of `.decks-layout` and takes full
  width (drop the sidebar's width from the flex layout).
- In `.deck-editor-hdr`, next to `#deck-editor-name`, add a
  `#deck-switch-btn` control showing a switch affordance (e.g. "▾") with
  a `d` hint, mirroring the look of the existing `deck-add-btn`.
- New overlay markup, structurally a twin of `#deck-add-palette`:
  ```html
  <div id="deck-switch-palette" class="deck-switch-palette hidden">
    <div class="deck-switch-actions">
      <button id="deck-switch-new-btn" class="action-btn">+ New</button>
      <button id="deck-switch-import-btn" class="action-btn">↑ Import</button>
    </div>
    <input id="deck-switch-search" class="deck-search-input"
      placeholder="Switch deck…" autocomplete="off" spellcheck="false">
    <div id="deck-switch-results"></div>
  </div>
  ```
- CSS: reuse `.deck-add-palette`'s fixed/centered floating panel rules
  (same position, `max-height`, `box-shadow`, z-index tier) under a new
  `.deck-switch-palette` class. Results rows reuse `.deck-list-item`,
  `.deck-list-name`, `.deck-list-count` styles from the old sidebar
  (kept, just re-targeted at the new container).

## Behavior (`static/app.js`)

- `openDeckSwitchPalette()` / `closeDeckSwitchPalette()`, modeled on
  `openAddPalette()` / `closeAddPalette()`:
  - Open: unhide the panel, focus+select `#deck-switch-search`, render
    all decks (empty query = full list, current deck marked `.active`).
  - Close: hide the panel, clear the input, clear filtered state.
- `renderDeckSwitchResults(query)` replaces `renderDeckList()`'s DOM
  target: filters `deckState.decks` by case-insensitive substring match
  on `name`, renders `.deck-list-item` rows (name + `card_count`),
  clicking a row calls `selectDeck(id)` then closes the palette.
- Input wiring on `#deck-switch-search`: `input` → re-filter/re-render;
  `ArrowDown`/`ArrowUp` move a focus index through the results; `Enter`
  selects the focused (or first) result, same pattern as
  `#deck-search`'s existing keydown handler.
- `#deck-switch-new-btn` / `#deck-switch-import-btn` reuse the existing
  `new-deck-btn` / `import-deck-btn` click handlers (IDs change, logic
  doesn't).
- Global keydown handler: add `d` → `openDeckSwitchPalette()` when the
  Decks view is active and focus isn't in a text field (parallel to the
  existing `/` → `openAddPalette()` branch). Add the palette to the
  existing `Escape` chain (checked before falling through, same tier as
  `addPaletteOpen()`).
- Nav click handler for `data-view="decks"`: after `loadDeckList()`, if
  `deckState.currentDeckId` is null, call `openDeckSwitchPalette()`
  instead of leaving the static empty state showing. Same check after a
  deck delete that clears `currentDeckId`.
- `#deck-empty` fallback text (shown only if the user opens Decks, the
  palette auto-opens, then they Escape without picking) changes from
  "Select a deck or create a new one" to "No deck selected — press `d`".

## Removed

- `.decks-sidebar`, `.decks-sidebar-hdr`, `.decks-sidebar-btns`,
  `#deck-list` and their CSS rules.
- `renderDeckList()` (replaced by `renderDeckSwitchResults`).

## Testing

- Decks page with 0 decks: palette auto-opens, results empty, "+ New"
  reachable.
- Decks page with an existing selection (e.g. returning from another
  view): sidebar/palette does not auto-open; header shows the current
  deck name.
- `d` opens the palette only when Decks is active and no input/textarea
  is focused; typing "d" in the deck-content-search or add-card search
  does not trigger it.
- Typing in the switch search filters by substring, case-insensitive;
  arrow keys + Enter select; clicking a row selects; Escape closes
  without changing the current deck.
- Deleting the current deck returns to the auto-open/empty-state
  behavior above.
