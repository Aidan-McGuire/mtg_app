# Plan: deck list view scroll buffer (item 032)

CSS-only change. No JS changes needed since `focusDeckTile`'s
`el.scrollIntoView({ block: 'nearest' })` already respects
`scroll-margin-top`/`scroll-margin-bottom`.

## Step 1

Add to the `.deck-text-row` rule in `static/style.css` (currently around
line 924):

```css
scroll-margin-top: 48px;     /* clears the sticky #deck-content-search box (~44px incl. its margin) */
scroll-margin-bottom: 40px;  /* buffer so the row isn't pinned flush to the bottom edge */
```

## Verification

- Read the edited CSS block to confirm syntax is valid (property names,
  semicolons, closing brace).
- Run `python3 -m pytest` — should be unaffected (no Python touched) but
  confirms nothing else is broken.
- Confirm `.deck-card-tile` (grid view) and Cards browser grid rules are
  untouched (out of scope).
