---
id: 036
title: Export decklist to clipboard
priority: medium
status: in-review
branch: item/36-export-decklist-to-clipboard
created: 2026-10-19
---

## Problem

There is no way to get a deck's card list out of the app. The user wants to
copy a decklist to the clipboard in one click, formatted as `1x Card Name`
(one line per card, the number being that card's quantity in the deck).

## Approach

Frontend-only; no backend or schema change. `deckState.deckCards` (from
`GET /api/decks/{id}/cards`) already carries `name`, `quantity`,
`is_commander`, and `is_considering` for every card in the deck.

Add two buttons to the deck page's action-button row in `static/index.html`
(next to `#deck-add-btn` / `#deck-built-btn`, class `action-btn`):

- **Copy deck** — copies the main list only (cards where `!is_considering`).
- **Copy deck + considering** — copies the main list, then a blank line, then
  the Considering cards (no header line). If there are no Considering cards,
  output is identical to "Copy deck" (no trailing blank line).

Behavior:

- Line format: `${quantity}x ${name}`, joined with `\n`, no trailing newline.
- Main list order: commander first (if any), then the rest alphabetically by
  name (case-insensitive). Considering block: alphabetical by name. The
  commander is an ordinary `1x` line — no marker.
- Names are the full card name as stored (double-faced cards stay
  `Front // Back`).
- Ignores the page's current search/filter/grouping/view state; always
  exports the entire deck, from `deckState.deckCards` (not the filtered view).
- Copy via `navigator.clipboard.writeText`. On success, show a brief inline
  confirmation by swapping the button's label to "Copied ✓" for ~1.5s, then
  restoring it (keep the button width stable so it doesn't reflow). On
  failure (clipboard API rejected/unavailable), show "Copy failed" the same
  way. If the deck has no cards for the chosen export, do nothing but flash
  "Nothing to copy".
- Keyboard-first: bake the shortcut hint into each button's own label/icon
  (per the existing convention, e.g. `<u>C</u>onsidering`; not a separate
  hover-toggled element). Suggested keys: `e` for Copy deck and `Shift+E`
  for Copy deck + considering — verify `e` is unused in the deck-page keydown
  handler (`static/app.js` ~line 1377-1425; currently d, a, c, t, Backspace,
  Enter are taken) and that the handler ignores the key while typing in an
  input/textarea, like its neighbours. If `e` turns out to conflict, pick
  another free letter and note it in the commit message.
- Buttons only show/work on the deck page when a deck is loaded, like the
  other deck action buttons.

## Acceptance criteria

- [ ] Deck page has "Copy deck" and "Copy deck + considering" buttons in the
      action row, each with its shortcut hint baked into the label.
- [ ] Clicking "Copy deck" puts `Nx Name` lines for all non-considering cards
      on the clipboard: commander first, rest alphabetical, `\n`-separated.
- [ ] Clicking "Copy deck + considering" yields the same main list, a blank
      line, then the Considering cards alphabetically; with no Considering
      cards it equals "Copy deck".
- [ ] Quantities are the card's deck quantity (e.g. `4x Lightning Bolt`);
      DFCs use the full `Front // Back` name.
- [ ] Export is unaffected by active search/filters or grid/list view.
- [ ] Button shows "Copied ✓" ~1.5s then restores, with no layout shift;
      shows "Copy failed" if the clipboard write fails.
- [ ] Keyboard shortcuts trigger the two actions and are ignored while typing
      in a field.
- [ ] Verified in the browser against a real deck containing a commander,
      multi-copy cards, and Considering cards (paste result into a text field
      or scratch file to confirm exact output).
