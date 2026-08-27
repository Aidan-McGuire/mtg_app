---
id: 028
title: Deck content-search box gets keyboard shortcut + arrow-down into results
priority: medium
status: in-review
branch: item/28-deck-content-search-box-gets-keyboard-shortcut-arrow-down-into-results
created: 2026-08-27
---

## Problem

On the Cards browser page, `/` focuses `#search-input`, and `ArrowDown` from
that box moves focus into the results grid (`static/app.js:1397-1404`). The
Collection page has the same `/`-focuses-search convention
(`static/app.js:1304-1305`). The deck page has an equivalent content-search
box, `#deck-content-search` (filters the cards already in the current deck —
distinct from the separate "Add cards" palette's own search), but it has
neither: `/` on the deck page instead opens the Add-cards palette
(`openAddPalette()`, `static/app.js:1299-1308`), and `#deck-content-search`'s
own keydown handler (`static/app.js:1719-1721`) only handles `Escape`. There
is no way to reach or move through this search box's results without a
mouse.

## Approach

**Rebind `/`:** on the deck page, `/` should focus `#deck-content-search`
instead of opening the Add-cards palette, matching the Cards/Collection page
convention. In the `/` handler (`static/app.js:1299-1308`), change the
`decksActive` branch from `openAddPalette()` to focusing
`document.getElementById('deck-content-search')` (guarded the same way the
Collection/Cards branches already are, by checking it isn't already the
active element).

**New shortcut `a`/`A` for Add-cards:** add a new global handler, alongside
the existing `d`/`D` (deck-switcher) handler (`static/app.js:1311-1318`):
when the deck page is active and not typing in a field, `a`/`A` calls
`openAddPalette()`. Update `#deck-add-btn`'s `title` attribute in
`static/index.html` from `Add cards  (/)` to `Add cards  (a)`.

**Arrow-down into results:** add an `ArrowDown` case to
`#deck-content-search`'s existing keydown listener
(`static/app.js:1719-1721`), mirroring the Cards page's search-input pattern
exactly:

```js
document.getElementById('deck-content-search').addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.target.blur(); deckState.query = ''; renderDeckContent(); }
  else if (e.key === 'ArrowDown') {
    e.preventDefault();
    const containerId = deckState.deckView === 'grid' ? 'deck-grid-view' : 'deck-text-view';
    const groups = deckNavGroups(document.getElementById(containerId));
    if (groups.length && groups[0].length) {
      e.target.blur();
      focusDeckTile(groups[0][0]);
    }
  }
});
```

This needs no changes to `deckNavGroups`/`focusDeckTile` — both already read
live from whatever's currently rendered, so they naturally reflect the
content-search's current filter.

**Out of scope:** no change to the Add-cards palette's own internal
keyboard handling (arrows/Enter/Escape within its results) — that's already
fully keyboard-driven and unaffected by this rebind.

## Acceptance criteria

- [ ] On the deck page, pressing `/` (while not typing in a field) focuses
      `#deck-content-search` instead of opening the Add-cards palette.
- [ ] Pressing `a` or `A` (while not typing in a field) opens the Add-cards
      palette, matching prior `/` behavior.
- [ ] The "+ Add" button's tooltip reads "Add cards  (a)".
- [ ] With `#deck-content-search` focused and at least one result visible in
      the current view (grid or list), pressing `ArrowDown` moves keyboard
      focus onto the first visible card and blurs the search box.
- [ ] Pressing `ArrowDown` in `#deck-content-search` when the filtered result
      set is empty does nothing (no error, no focus change).
- [ ] Existing `Escape`-clears-and-blurs behavior on `#deck-content-search`
      is unchanged.
