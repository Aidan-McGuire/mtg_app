---
id: 002
title: Widen deck-page hover/focus preview panel
priority: medium
status: in-review
branch: item/2-widen-deck-page-hover-focus-preview-panel
created: 2026-08-21
---

## Problem

The deck page's preview panel (`#deck-preview-panel`, populated by
`renderDeckPreviewPanel` in `static/app.js`) shows the card image, name,
mana cost, type line, and oracle text for whichever card is currently
hovered or keyboard-focused. It's rendered at a fixed width via
`.deck-preview-panel { flex: 0 0 260px; ... }` in `static/style.css`
(currently around line 549), which is too small to comfortably read card
art and full oracle text at a glance.

## Approach

In `static/style.css`, change the `.deck-preview-panel` rule's `flex-basis`
from `260px` to `360px`:

```css
.deck-preview-panel {
  flex: 0 0 360px;
  overflow-y: auto;
  padding: 12px;
  border-right: 1px solid var(--border);
}
```

No other changes needed — `.deck-preview-img img` is already `width: 100%`
inside the panel, so the card image scales up automatically with the wider
container. Text elements (`.deck-preview-name`, `.deck-preview-mana`,
`.deck-preview-type`, `.deck-preview-oracle`) keep their existing font
sizes; only the available width increases, giving oracle text more room to
wrap.

## Acceptance criteria

- [ ] `.deck-preview-panel` renders at 360px wide instead of 260px on the
      deck page.
- [ ] The card image inside the panel scales up proportionally to fill the
      new width (no distortion, no fixed max-width capping it below the
      panel's width).
- [ ] The rest of the deck page layout (grid/text view area) still fits
      without horizontal overflow at typical desktop window widths.
