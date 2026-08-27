---
id: 025
title: Deck action buttons bake in their keyboard shortcut hints instead of a hover-toggled hint
priority: low
status: in-progress
branch: item/25-deck-action-buttons-bake-in-their-keyboard-shortcut-hints-instead-of-a-hover-toggled-hint
created: 2026-08-27
---

## Problem

In both the deck grid tile (`buildDeckCardTile`) and deck list row
(`buildDeckTextRow`) in `static/app.js`, the Considering toggle and Remove
buttons each sit next to a `<kbd class="deck-kbd-hint">` element showing
their keyboard shortcut (`c` / `⌫`). That hint is `display: none` normally
and `display: inline-block` only when the tile/row is `.focused`
(`static/style.css:958-960`), which happens on hover (`setDeckFocus`).
Toggling an element's `display` adds/removes it from the flex layout flow,
so the buttons after it visibly shift position whenever a card is
hovered/unhovered.

## Approach

Bake each shortcut's hint into the button's own permanent content instead of
a separate conditionally-visible element, so nothing is ever added to or
removed from the layout on focus/hover:

- **Considering button** (`.deck-considering-btn`): change its content from
  the bare `?` glyph to the label "Considering" with the leading **C**
  visually set apart (e.g. `<u>C</u>onsidering`). Drop the adjacent
  `<kbd class="deck-kbd-hint">c</kbd>` entirely. CSS: switch this button from
  a fixed 18×18 icon box to an auto-width pill with small horizontal padding
  (keep font-size around 10-11px so it stays compact); keep its existing
  `:hover`/`.active` color treatment.
- **Remove button** (`.deck-remove-btn`): change its glyph from `×` to `⌫`.
  Drop the adjacent `<kbd class="deck-kbd-hint">⌫</kbd>` entirely. No size
  change needed — it stays the existing fixed 18×18 icon box, since swapping
  one single-character glyph for another doesn't change its width.
- Delete the now-unused `.deck-kbd-hint` CSS rules
  (`static/style.css:958-960`) and remove both `<kbd class="deck-kbd-hint">`
  usages from `static/app.js` (one Considering + one Remove hint per
  function, in both `buildDeckCardTile` and `buildDeckTextRow` — four
  removals total).
- No new focus-state styling on these buttons themselves: the tile/row
  already gets a focus highlight (`.deck-card-tile.focused` outline;
  `.deck-text-row.focused` background + inset box-shadow), which already
  signals which card the keyboard shortcuts currently act on.
- Commander button (♛) is untouched — it has no keyboard shortcut/hint
  today, so it isn't part of this bug.

**Convention going forward:** prefer baking a shortcut hint into a button's
own always-rendered label/icon rather than a separate hover/focus-toggled
hint element, since toggling a separate element's visibility is what causes
sibling reflow.

## Acceptance criteria

- [ ] Hovering over (or keyboard-focusing) any deck grid tile or list row no
      longer shifts the position of its qty/considering/commander/remove
      buttons.
- [ ] The Considering button reads "Considering" with the C visually
      emphasized, in both grid and list views, and still toggles considering
      state on click exactly as before.
- [ ] The Remove button shows a ⌫ glyph, in both grid and list views, and
      still removes the card on click exactly as before.
- [ ] No `<kbd class="deck-kbd-hint">` elements or `.deck-kbd-hint` CSS rules
      remain in the codebase.
- [ ] Pressing `c` and `Backspace` on a focused card still work exactly as
      before (this is a presentation-only change, not a behavior change).
