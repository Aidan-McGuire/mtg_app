---
id: 022
title: Bump deck text view font sizes slightly
priority: low
status: in-progress
branch: item/22-bump-deck-text-view-font-sizes-slightly
created: 2026-08-26
---

## Problem

The deck text view's row text is a little small. Bump the three main text
elements up by 1px each:

- `.deck-text-qty` (the "Nx" quantity prefix): 12px → 13px
- `.deck-text-name` (the card name): 13px → 14px
- `.deck-text-mana` (the mana cost): 11px → 12px

No other deck text view elements (tag chips, keyboard hints, the
considering-toggle button) are in scope — only these three.

## Approach

In `static/style.css`, find:

```css
.deck-text-qty  { font-size: 12px; color: var(--muted); min-width: 22px; }
.deck-text-name { font-size: 13px; font-weight: 500; flex: 1; }
.deck-text-mana { font-size: 11px; color: var(--muted); }
```

Replace with:

```css
.deck-text-qty  { font-size: 13px; color: var(--muted); min-width: 22px; }
.deck-text-name { font-size: 14px; font-weight: 500; flex: 1; }
.deck-text-mana { font-size: 12px; color: var(--muted); }
```

Only the `font-size` values change — leave `color`, `min-width`,
`font-weight`, and `flex` exactly as they are.

## Acceptance criteria

- [ ] `.deck-text-qty` renders at 13px.
- [ ] `.deck-text-name` renders at 14px.
- [ ] `.deck-text-mana` renders at 12px.
- [ ] No other properties on these three rules changed.
- [ ] No other deck text view elements (tags, kbd hints, considering
      button) changed size.
- [ ] Rows still lay out without visual overflow/clipping at the new
      sizes (check a card with a long name and a full tag list).
