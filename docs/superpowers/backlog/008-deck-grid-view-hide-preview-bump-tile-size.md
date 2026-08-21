---
id: 008
title: Hide deck preview panel in grid view and enlarge grid tiles
priority: medium
status: queued
branch:
created: 2026-08-21
---

## Problem

The deck page's hover/focus preview panel (`#deck-preview-panel`,
`static/index.html` ~line 81, `flex: 0 0 360px` per item 002,
`static/style.css` line 550-551) is always visible, in both grid and text
view. In grid view it's redundant — each `.deck-card-tile` already shows
the card's art directly (`.deck-card-img-wrap`, `static/style.css` line
788-801) — while in text view (`.deck-text-view`, compact rows with no
card art) it's the only way to see what a card looks like.

## Approach

Hide the preview panel only while `deckState.deckView === 'grid'`, and
enlarge the grid's tile minimum width to take advantage of the freed space.
Text view is untouched.

### 1. Hide the panel in grid view

`.deck-editor-body` (`static/style.css` line 543-548) is a flex row with
`.deck-preview-panel` (`flex: 0 0 360px`) and `.deck-content-col`
(`flex: 1`, line 736) as its two children. Toggling the generic `.hidden`
utility class (`static/style.css` line 410, `display: none !important`) on
`#deck-preview-panel` is enough — `.deck-content-col`'s `flex: 1` already
makes it expand to fill whatever width `.deck-editor-body` has, so hiding
its sibling frees that ~360px + gap automatically, no extra layout CSS
needed.

In `renderDeckContent` (`static/app.js` line 1948-1967), alongside the
existing grid/text-view toggling (line 1957-1965):

```js
const previewPanel = document.getElementById('deck-preview-panel');
if (deckState.deckView === 'grid') {
  renderDeckGrid();
  document.getElementById('deck-grid-view').classList.remove('hidden');
  document.getElementById('deck-text-view').classList.add('hidden');
  previewPanel.classList.add('hidden');
} else {
  renderDeckText();
  document.getElementById('deck-text-view').classList.remove('hidden');
  document.getElementById('deck-grid-view').classList.add('hidden');
  previewPanel.classList.remove('hidden');
}
renderDeckPreviewPanel();
```

Leave `renderDeckPreviewPanel()` itself, and all focus-tracking logic that
feeds it (`setDeckFocus`, hover handlers, `deckState.focusedCardId`),
completely unchanged — it keeps running and updating its content even while
hidden in grid view, so switching to text view immediately shows the
correct (already up to date) preview for whatever card was last
focused/hovered, with no extra state-sync work needed.

### 2. Enlarge grid tiles

Two separate CSS rules currently set the deck grid's tile minimum width to
240px (from item 003):

- `.deck-grid-view` (`static/style.css` line 768-771, ungrouped deck grid).
- `.group-body` (`static/style.css` line ~1196-1201) — **shared** with the
  Collection page's grouped views (tag mode today; also type mode if item
  007 has landed), so it cannot be changed globally without also enlarging
  Collection's grouped tiles, which this item doesn't intend to touch.

Change `.deck-grid-view`'s own rule directly to `minmax(280px, 1fr)`. For
the grouped case, add a more specific override scoped to the deck page only
(`#deck-grid-view` is the container `renderGroupedGrid` renders `.group-section`/
`.group-body` elements into when `deckState.groupBy !== 'none'`):

```css
.deck-grid-view {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  grid-auto-rows: max-content;
  gap: 10px;
  align-items: start;
}

#deck-grid-view .group-body {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
```

(The second rule's higher specificity — an ID selector — overrides the
generic `.group-body` rule just for sections rendered inside
`#deck-grid-view`, leaving `#collection-grid .group-body` at 240px
untouched.)

### Out of scope

- Text view (`.deck-text-view`) and its preview-panel behavior are
  completely unchanged.
- Collection page's tile sizing (ungrouped and grouped) is unchanged.
- No change to the preview panel's own width/content/focus-tracking logic
  — only its visibility in grid view.

## Acceptance criteria

- [ ] With a deck open in grid view, the preview panel is not visible and
      the card grid occupies the full width of the deck editor body.
- [ ] Switching to text view immediately shows the preview panel again,
      reflecting whatever card is currently focused/hovered.
- [ ] Switching back to grid view hides it again.
- [ ] In grid view, card tiles are noticeably larger than before (minimum
      ~280px instead of ~240px), in both the ungrouped grid and every
      grouped-by-type/tag/deck-tag section.
- [ ] In text view, hovering/clicking a row still updates the preview panel
      exactly as today.
- [ ] The Collection page's own tile sizes (ungrouped and grouped) are
      visually unchanged.
- [ ] Full test suite (pytest + JS) still passes.
