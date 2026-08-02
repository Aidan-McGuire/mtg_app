# Collapsed groups sort to the bottom

## Problem

Notes.md, Deck Page item #4: "when a category is minimized the category goes
to the bottom." Today, collapsing a group (`renderGroupSection`'s header
click) only toggles a CSS class in place — the section stays wherever it
was in the grouping order, just visually shrunk to its header. A minimized
group should instead move after all still-expanded groups, so browsing the
expanded content isn't interrupted by empty collapsed headers sitting
between them.

`renderGroupSection`/`renderGroupedGrid` are shared by the Deck page (Grid
and Text view) and the Collection page's grouped grid, so this applies
everywhere groups can be collapsed.

## Behavior

- Collapsed groups sort after all expanded groups, in their own original
  relative order (the order they'd appear in if nothing were collapsed —
  alphabetical for tag groups, fixed Commander-first for type groups).
  Expanding a group returns it to that natural position among the other
  expanded groups.
- This holds continuously, not just at the instant of the click: after any
  full re-render (sort change, filter change, card add/remove/quantity
  change, deck switch, group-by change), collapsed groups are still at the
  bottom.
- The already-existing "Considering starts collapsed by default" behavior
  is unaffected — Considering is appended last in the groups array by its
  callers already, so it naturally stays last whether collapsed or
  expanded (there's nothing "before" it to sort past).

## Implementation

Two changes, both in `renderGroupSection`/`renderGroupedGrid`
(`static/app.js`) — no CSS changes, since Grid view's grouped layout and
Text view's column layout both already follow DOM order for visual order.

**1. Sort at build time**, so every full rebuild already reflects the rule:

```js
function sortGroupsByCollapsed(groups, collapsedState) {
  const expanded  = groups.filter(g => !collapsedState.has(g.label));
  const collapsed = groups.filter(g => collapsedState.has(g.label));
  return [...expanded, ...collapsed];
}
```

`renderGroupedGrid` calls this before iterating to build sections.

**2. Move only the toggled section at click time**, so collapsing/expanding
is instant without rebuilding any tiles or images. `renderGroupSection`
needs the full `groups` array (not just its own group) to compute the new
order; each section gets `dataset.label` so the toggled section can find
where to reinsert itself:

```js
header.addEventListener('click', () => {
  if (collapsedState.has(group.label)) collapsedState.delete(group.label);
  else collapsedState.add(group.label);
  header.classList.toggle('collapsed');
  body.classList.toggle('collapsed');

  const ordered = sortGroupsByCollapsed(allGroups, collapsedState);
  const idx = ordered.findIndex(g => g.label === group.label);
  const nextLabel = ordered[idx + 1]?.label;
  const nextEl = nextLabel
    ? container.querySelector(`.group-section[data-label="${CSS.escape(nextLabel)}"]`)
    : null;
  if (nextEl) container.insertBefore(section, nextEl);
  else container.appendChild(section);
});
```

`renderGroupSection(container, group, buildTileFn, collapsedState, allGroups)`
gains the `allGroups` parameter. `renderGroupedGrid` passes its own
`groups` array through unchanged. The two standalone call sites that
render a single trailing Considering section outside `renderGroupedGrid`
(the deck Grid ungrouped branch and the deck Text ungrouped branch — the
Collection page has no standalone call, only its one `renderGroupedGrid`
call) pass `[group]` — a single-element array, so the reorder computation
is a no-op there, which is correct since there's nothing else to sort
against.

## Out of Scope

- No change to default collapse state (Considering still starts collapsed;
  everything else still starts expanded).
- No animation on the move — it's an instant DOM reposition, matching the
  instant expand/collapse of the body today.
- No change to group *header* content or the count badge (notes.md item
  #5) — that's already showing today regardless of collapse state and is
  a separate, unfiled-yet request.

## Testing

No JS test runner applies (DOM-dependent, no jsdom harness in this repo,
per this project's established convention). Manual verification in a
running browser (`uvicorn app:app --reload`):

- Deck Grid view, Group-by "Card type" or a tag mode with 3+ groups:
  collapse the middle group — confirm it moves to just before the
  Considering group (or to the very end if Considering isn't present),
  without any tile flicker/reload in the other groups.
- Expand it again — confirm it returns to its original position among the
  still-expanded groups.
- Collapse two different groups — confirm both end up at the bottom, in
  their original relative order relative to each other.
- Trigger a full re-render while a group is collapsed (change the sort
  dropdown, or increment a card's quantity) — confirm the collapsed group
  is still at the bottom afterward.
- Repeat the above in Text view and on the Collection page's grouped grid.
- Confirm Considering's existing default-collapsed-and-last behavior is
  unchanged.
