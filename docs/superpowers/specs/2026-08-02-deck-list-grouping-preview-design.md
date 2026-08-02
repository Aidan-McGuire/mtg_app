# Deck list grouping + focused-card preview panel

## Problem

Notes.md, Deck Page item #3: "add group by tag when viewing by list," with
nested sub-items about showing the focused card (arrow keys or hover) in a
dedicated preview panel, defaulting to the commander. Two gaps this closes:

1. Text/list view ignores `deckState.groupBy` entirely — it always groups
   by a hardcoded card-type bucket list, so Collection tag / Deck tag
   grouping (already available in Grid view) has no effect there.
2. Text view shows no card images at all, and neither view has any
   keyboard navigation — browsing a deck without a mouse currently means
   opening the click-only modal over and over.

This feature unifies grouping across both views and adds a persistent
left-side preview panel driven by keyboard focus or mouse hover, in both
Grid and Text view.

## Grouping

`groupCardsByType(cards)` is extracted from the current hardcoded logic in
`renderDeckText` into a standalone, reusable function:

- The deck's commander (`is_commander`) gets its own leading `Commander`
  group.
- Remaining cards bucket by `type_line` into the existing fixed order:
  Creature, Instant, Sorcery, Enchantment, Artifact, Planeswalker, Land,
  Other.
- `is_considering` cards are excluded here — Considering is always handled
  as its own separate trailing group by the caller, exactly as it is today
  for tag-based grouping.

`#deck-group-by` gains a new option, ordered:

```html
<option value="none">Group: None</option>
<option value="type">Card type</option>
<option value="collection-tag">Collection tag</option>
<option value="deck-tag">Deck tag</option>
```

`deckState.groupBy` type becomes `'none' | 'type' | 'collection-tag' | 'deck-tag'`.

Both `renderDeckGrid` and `renderDeckText` branch on `deckState.groupBy`
the same way:

- `'none'` → flat, ungrouped (commander pinned first, existing behavior).
- `'type'` → `groupCardsByType(mainCards)`.
- `'collection-tag'` / `'deck-tag'` → existing `groupCards(mainCards, tagField)`.

In every branch, `consideringCards` (already split out today) are appended
as a trailing `Considering` group exactly as the current grid-view code
does — `renderDeckText` gains this same split/append instead of its
current inline `Considering` bucket built into the fixed groups object.

`renderDeckText` is rewritten to share `renderGroupSection` /
`renderGroupedGrid` (the same group-header/collapse UI Grid view already
uses) rather than hand-rolling its own section markup, so collapse state
(`deckGroupCollapsed`) and header styling are identical across both views.
Text view previously had no collapse mechanic for any section — after
this change it gains the same one Grid view already has, uniformly.

## Preview panel

A new persistent panel, fixed-width, in a left column next to the
existing content column — present in both Grid and Text view, driven by
one shared `deckState.focusedCardId`.

Markup mirrors the modal's left/details split, minus tags/qty/actions:

```html
<div id="deck-preview-panel" class="deck-preview-panel">
  <div class="deck-preview-img">…image or placeholder…</div>
  <div class="deck-preview-name">…</div>
  <div class="deck-preview-mana">…</div>
  <div class="deck-preview-type">…</div>
  <div class="deck-preview-oracle">…</div>
</div>
```

`renderDeckPreviewPanel()` resolves which card to show, in priority order,
each time it's called:

1. `deckState.focusedCardId`, if that card is still present in the
   current filtered card set.
2. The deck's commander, if present.
3. The first card in the current sort order (post-filter, post-group
   flattening), or nothing if the deck view is empty.

It's called after every render of Grid or Text view, and on every focus
change described below.

## Focus & hover model

New `deckState` field: `focusedCardId` (the live keyboard/hover focus).
There is no `mouseleave` handler that clears it, so it stays set to the
last-interacted card until the next focus change — a separate sticky
field to track "last focused" would be redundant, since `focusedCardId`
itself already never gets cleared by hovering away. It resets to `null`
in `selectDeck` when switching decks.

**Mouse:** `mouseenter` on a `.deck-card-tile` (Grid) or `.deck-text-row`
(Text) sets `focusedCardId` to that card and re-renders the preview
panel. There is no `mouseleave` handler that clears focus — moving the
mouse off a card leaves the panel showing what it was showing, per the
priority order above (`focusedCardId` still points at the last-hovered
card).

**Keyboard**, active only while a deck is open, the deck editor has
implicit focus (mirrors the Cards-page guard already in place — no active
text input/modal), Grid or Text view is showing:

- *List view:* `ArrowUp`/`ArrowDown` move to the previous/next row within
  the current group only, clamped at the group's own top/bottom (no
  wrap). `ArrowLeft`/`ArrowRight` jump to the first row of the
  previous/next group, skipping collapsed groups. With nothing focused,
  any arrow key focuses the first visible row of the first group.
- *Grid view* (new — no keyboard nav exists here today): within a group,
  spatial movement identical to the Cards-page model — column count is
  measured from that group's own rendered `.group-body` via
  `getBoundingClientRect` (same technique as the existing `columnCount()`
  helper), `ArrowRight`/`ArrowLeft` move ±1, `ArrowUp`/`ArrowDown` move
  ± that column count. Moving `ArrowDown` past a group's last row, or
  `ArrowUp` past its first row, crosses into the adjacent group
  (skipping collapsed groups), landing on the closest matching column
  (clamped to that group's row length). When ungrouped, this is one
  continuous grid, matching the Cards-page model exactly.
- Every focus change: add `.focused` to the newly focused tile/row
  (removing it from the previous one), `scrollIntoView({block:'nearest'})`,
  update `focusedCardId`, re-render the preview panel.

**Click is unchanged** — clicking a tile or row still calls
`openModal(card, ...)` directly, independent of focus/hover state.

## Layout

`.deck-editor-body` becomes a flex row:

```css
.deck-editor-body { display: flex; gap: 16px; align-items: flex-start; }
.deck-preview-panel { flex: 0 0 260px; position: sticky; top: 0; }
.deck-content-col { flex: 1; min-width: 0; }
```

`.deck-card-tile.focused` / `.deck-text-row.focused` get a visible outline
(same accent color already used for `is-commander`, distinguished by
being an outline rather than a border-color change, so commander +
focused is visually distinguishable from either alone).

## Out of scope

- No changes to the card detail modal, add-card palette, or deck-switcher
  palette.
- No changes to Cards/Collection page keyboard nav.
- Collapsed-group "moves to bottom" and "show count while collapsed"
  (notes.md Deck Page items #4/#5) are separate, not addressed here.
- No drag-and-drop, no reordering.

## Testing

No JS test runner exists in this repo (consistent with prior
frontend-only work) — verification is manual in the browser:

- Switch `#deck-group-by` through all four options in both Grid and Text
  view; confirm groupings match (type buckets incl. leading Commander
  group, collection tags, deck tags), with Considering always last and
  collapsed by default in both views.
- Hover over tiles/rows in both views: preview panel updates live.
- Move the mouse off the deck area entirely: preview panel keeps showing
  the last-hovered card.
- With nothing ever focused/hovered and a commander set: panel shows the
  commander on deck load.
- Remove/toggle-away the commander so none is set, with a
  previously-focused card still visible: panel falls back to that last
  focused card.
- Keyboard nav in List view: Up/Down stay inside a group; Left/Right jump
  groups and skip collapsed ones.
- Keyboard nav in Grid view: spatial movement within a group; Up/Down at
  a group's edge crosses into the adjacent group.
- Click still opens the modal regardless of current focus/hover state.
- Switch Grid ↔ Text view: focused card and panel contents persist.
