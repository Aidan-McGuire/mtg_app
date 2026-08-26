---
id: 021
title: Deck text view owned indicator becomes a 3-state status color
priority: medium
status: queued
branch:
created: 2026-08-26
---

## Problem

The deck text view currently shows two visually unrelated marks on a row:
a subtle gold left-edge highlight (`.deck-text-row.owned`, from item 013)
when the card is owned at all, and a separate red `⚠` inline glyph
(`.deck-text-locked`, from item 020) when every owned copy is allocated to
other built decks. These two signals don't read as part of the same
system, and a viewer has to notice both independently.

Replace them with a single left-edge highlight whose color communicates
one of three mutually exclusive, exhaustive states for every row:

- **Green** — owned (`quantity > 0`) and at least one copy is free (not
  locked elsewhere).
- **Yellow** — owned but every copy is locked elsewhere
  (`isLockedElsewhere(cardId)` is true — this already implies `quantity >
  0`, per its own guard clause).
- **Red** — not owned at all (`quantity` is 0).

This item is scoped to the **deck text view only** (`buildDeckTextRow` /
`.deck-text-row`). It does not touch the deck grid view's owned badge
(`buildDeckCardTile`, `OWNED_BADGE_HTML`) or the "Add cards" search
results' locked-elsewhere indicator (`renderDeckSearchResults`,
`.dsearch-locked`) — both stay exactly as they are today.

## Approach

- `static/app.js`, `buildDeckTextRow(card)`: replace the current
  ```js
  row.className = 'deck-text-row'
    + (card.id === deckState.focusedCardId ? ' focused' : '')
    + (qty(card.id) > 0 ? ' owned' : '');
  ```
  with logic that computes one of three status classes and drops the old
  `owned` class entirely:
  ```js
  const owned = qty(card.id) > 0;
  const locked = owned && isLockedElsewhere(card.id);
  const statusClass = !owned ? 'unowned' : (locked ? 'owned-locked' : 'owned-free');
  row.className = 'deck-text-row'
    + (card.id === deckState.focusedCardId ? ' focused' : '')
    + ' ' + statusClass;
  ```
  Also set a `title` on the row itself so the removed glyph's tooltip
  isn't lost: `row.title = locked ? 'All owned copies are in other built
  decks' : (!owned ? 'Not owned' : '');` (empty string clears any
  previous title when re-rendered).
  Remove the existing `lockedHtml` variable and the
  `<span class="deck-text-locked">...</span>` it produced from the row's
  `innerHTML` template entirely — the edge color now carries that
  meaning, so the inline glyph is redundant on this view.
- `static/style.css`: replace
  ```css
  .deck-text-row.owned { box-shadow: inset 2px 0 0 var(--accent); }
  .deck-text-row.owned.focused { background: var(--surface2); box-shadow: inset 2px 0 0 var(--accent); }
  ```
  with three state rules (reusing the existing danger red `#e74c3c`
  already defined elsewhere in the file for consistency; introduce a new
  green `#2ecc71` and yellow `#f1c40f` — both from the same flat, muted
  color family the existing `#e74c3c`/`#c0392b` danger colors already come
  from, so the new colors read as part of the same palette):
  ```css
  .deck-text-row.owned-free { box-shadow: inset 2px 0 0 #2ecc71; }
  .deck-text-row.owned-free.focused { background: var(--surface2); box-shadow: inset 2px 0 0 #2ecc71; }
  .deck-text-row.owned-locked { box-shadow: inset 2px 0 0 #f1c40f; }
  .deck-text-row.owned-locked.focused { background: var(--surface2); box-shadow: inset 2px 0 0 #f1c40f; }
  .deck-text-row.unowned { box-shadow: inset 2px 0 0 #e74c3c; }
  .deck-text-row.unowned.focused { background: var(--surface2); box-shadow: inset 2px 0 0 #e74c3c; }
  ```
  Split the existing combined rule
  ```css
  .deck-text-locked, .dsearch-locked {
    color: #e74c3c;
    font-size: 12px;
  }
  ```
  into just
  ```css
  .dsearch-locked {
    color: #e74c3c;
    font-size: 12px;
  }
  ```
  (`.deck-text-locked` no longer exists in the DOM after the JS change
  above, so its half of the selector is dead — remove it; `.dsearch-locked`
  is unrelated to this item and must keep its styling unchanged).

## Acceptance criteria

- [ ] A card owned with at least one free copy shows a green left-edge
      highlight on its text-view row.
- [ ] A card owned but fully allocated to other built decks shows a
      yellow left-edge highlight — no separate warning glyph appears.
- [ ] A card not owned at all shows a red left-edge highlight.
- [ ] Every text-view row has exactly one of these three states — never
      zero, never more than one.
- [ ] The `.focused` row style (background tint) still applies correctly
      layered under any of the three edge colors.
- [ ] The deck grid view's owned badge and the "Add cards" search
      results' locked-elsewhere `⚠` indicator are visually unchanged.
- [ ] No remaining references to `.deck-text-locked` or the old
      `.deck-text-row.owned` class in `static/app.js` or `static/style.css`.
