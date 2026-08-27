---
id: 030
title: Group headers (collapse/expand) are keyboard-operable
priority: low
status: in-progress
branch: item/30-group-headers-collapse-expand-are-keyboard-operable
created: 2026-08-27
---

## Problem

`renderGroupSection` (`static/app.js:1557-1601`) — shared by the Collection
page's grouped grid, the deck grid view, and the deck list (text) view —
renders each group header as a plain `<div class="group-header">` with only
a `click` listener toggling `collapsedState`. It has no `tabindex` and no
keydown handling, so it cannot be reached or activated by keyboard at all;
collapsing/expanding a group requires a mouse click.

## Approach

Make `.group-header` keyboard-operable wherever it's collapsible
(`collapsedState` present — some callers render groups without collapse
support and should stay non-interactive, unchanged):

- Add `tabindex="0"`, `role="button"`, and `aria-expanded="${!isCollapsed}"`
  to the header's markup when `collapsedState` is passed.
- Extract the existing click handler's body (the collapse/expand +
  DOM-reorder logic at `static/app.js:1571-1590`) into a named local
  function, e.g. `toggleGroup()`, and call it from both the existing `click`
  listener and a new `keydown` listener on `header` for `Enter` and `Space`
  (`e.preventDefault()` on `Space` to stop the page from scrolling).
- Keep `aria-expanded` in sync inside `toggleGroup()` alongside the existing
  `header.classList.toggle('collapsed')`.
- Add a focus-visible style in `static/style.css`:
  `.group-header:focus-visible { outline: 2px solid var(--accent);
  outline-offset: 2px; }`, matching the focus-ring convention already used
  elsewhere (e.g. `.deck-card-tile.focused`).

**Out of scope:** no change to the arrow-key grid/list navigation system
(`handleDeckColumnNavKey`/`deckNavGroups`) — headers become reachable via
standard browser Tab order, not the custom card-to-card arrow navigation.
Extending arrow-nav to also stop on headers would be a larger redesign of
that system and isn't needed to make headers keyboard-operable.

## Acceptance criteria

- [ ] In the deck grid view, deck list view, and Collection page's grouped
      grid, each collapsible group header can be reached via Tab and
      toggled with `Enter` or `Space`.
- [ ] Toggling via keyboard produces the same visual result (chevron
      rotation, body collapse, group reordering to the end) as toggling via
      mouse click today.
- [ ] `aria-expanded` reflects the header's current collapsed/expanded
      state.
- [ ] A focused header shows a visible focus ring.
- [ ] Groups rendered without `collapsedState` (non-collapsible callers, if
      any) are unaffected — no `tabindex`/keydown added to those.
