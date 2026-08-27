---
id: 029
title: Apply a deck tag to the keyboard-focused deck card without the mouse
priority: high
status: queued
branch:
created: 2026-08-27
---

## Problem

Deck tags can currently only be applied through the detail modal's tag
editor (`buildTagEditor`, wired up in `loadModalTags`,
`static/app.js:1030-1075` and `:1163-1225`) — there is no way to tag a card
while keyboard-navigating the deck grid/list view without opening the modal
first (which itself currently requires a mouse click, until item 027 ships
Enter-to-open). The user has flagged this as the most important gap in this
set: applying a deck tag to a card should never require touching the mouse.

## Approach

Add a small keyboard-only "quick tag" palette, following the same pattern as
the existing `deck-add-palette` / `deck-switch-palette`:

**Shortcut:** `t`/`T` (unused today), added to the deck-page keydown block
(`static/app.js:1320-1343`, alongside the existing `Backspace`/`c` cases —
and the `Enter` case from item 027): when the deck page is active, not
typing in a field, and a card is keyboard-focused
(`deckState.focusedCardId`), opens `#deck-tag-palette` and focuses its input.

**Palette markup** (new element in `static/index.html`, styled by extending
the existing shared selector `.deck-add-palette, .deck-switch-palette` in
`static/style.css` to include `.deck-tag-palette` — no new positioning CSS
needed):

```html
<div id="deck-tag-palette" class="deck-tag-palette hidden">
  <div id="deck-tag-palette-card" class="deck-tag-palette-card"></div>
  <input id="deck-tag-input" class="deck-search-input" list="deck-tag-suggestions" placeholder="Add tag…" autocomplete="off">
  <datalist id="deck-tag-suggestions"></datalist>
</div>
```

`openDeckTagPalette()`:
- Records the target card id (the currently focused card at open time —
  fixed for the palette's lifetime, since typing in an input doesn't change
  `deckState.focusedCardId`).
- Sets `#deck-tag-palette-card`'s text to that card's name, so it's clear
  which card is being tagged (the palette has no visual anchor to the tile).
- Fetches `API.listDeckTags(deckState.currentDeckId)` and populates
  `#deck-tag-suggestions` for autocomplete, mirroring what `loadModalTags`
  already does for the modal's own tag editor.
- Shows the palette and focuses `#deck-tag-input`.

`#deck-tag-input` keydown handler:
- `Enter` or `,`: normalize the value exactly like `buildTagEditor`'s input
  handler does (`trim().toLowerCase().replace(/,/g, '')`), skip if empty or
  already in the target card's `deck_tags`; otherwise call
  `API.addDeckTag(deckId, cardId, tag)`, then update via the existing
  `syncDeckTagsOnCard(cardId, updated)` (already re-renders the deck view),
  clear the input, and **keep the palette open** so multiple tags can be
  added back-to-back without reinvoking the shortcut.
- `Escape`: close the palette (blur input, clear value, hide, matching
  `closeAddPalette()`'s shape).

`closeDeckTagPalette()`: same shape as `closeAddPalette()` — blur/clear the
input, hide the palette.

**Guard existing deck-page key handling while the palette is open:** add a
`deckTagPaletteOpen()` helper (same shape as `addPaletteOpen()`) and include
it in the existing guard at `static/app.js:1321-1322`
(`!deckSwitchPaletteOpen() && !addPaletteOpen()` becomes
`&& !deckTagPaletteOpen()`), so arrow keys/Backspace/`c`/`t` don't fire while
typing in the tag input. Also close the palette on outside click, mirroring
the existing `document.addEventListener('mousedown', ...)` handlers for the
other two palettes.

**Out of scope:** removing a tag via this flow — tag chips on the deck
tile/row are already display-only everywhere outside the modal, and the raw
request was specifically about *applying* a tag, not removing one.

## Acceptance criteria

- [ ] With a card keyboard-focused in the deck grid or list view, pressing
      `t` opens the quick-tag palette showing that card's name and a focused
      text input.
- [ ] Typing a tag name and pressing `Enter` applies it as a deck tag to
      that card (visible immediately as a chip on its tile/row) and clears
      the input, leaving the palette open.
- [ ] Autocomplete suggestions in the input include this deck's existing
      tags.
- [ ] Pressing `Escape` closes the palette without adding anything if the
      input is empty, and returns to normal deck-page keyboard navigation.
- [ ] Clicking outside the palette closes it, matching the Add-cards and
      deck-switcher palettes' existing outside-click behavior.
- [ ] While the palette is open, arrow keys type/move the cursor in the
      input rather than moving the deck-grid focus.
- [ ] Applying the same tag twice is a no-op (matching the modal tag
      editor's existing dedupe behavior).
