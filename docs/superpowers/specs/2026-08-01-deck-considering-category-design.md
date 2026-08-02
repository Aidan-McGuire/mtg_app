# Deck "Considering" category

## Problem

Notes.md, Deck Page item #2: deckbuilders want a way to keep cards attached
to a deck that they're still deciding on, without those cards counting
toward the deck's committed card total, and without those cards muddying
up tag-based grouping. Sub-requirements:

1. A way to move a card out of the "real" deck and into this category
   (and back), rather than only a hard delete.
2. Cards in this category are excluded from tag-based grouping/sorting —
   they get their own bucket instead of being scattered across tag groups.

## Naming

The category is called **Considering** in the UI (group headers, button
titles), matching the notes.md wording.

## Data Model

Add `is_considering INTEGER NOT NULL DEFAULT 0` to `deck_cards`, as a
migration `main.py` schema v3 → v4, directly parallel to the existing
`is_commander` column:

```python
if version < 4:
    cur.execute("ALTER TABLE deck_cards ADD COLUMN is_considering INTEGER NOT NULL DEFAULT 0;")
    cur.execute("UPDATE schema_version SET version = 4;")
```

A card in Considering remains a normal `deck_cards` row: same `quantity`,
same `collection_tags`/`deck_tags`. Only `is_considering` changes. Nothing
is deleted or moved to a different table.

**Mutual exclusion with Commander:** a card cannot be both. Enforced at
the data layer in `update_deck_card`, not just the UI, so the invariant
holds even for direct API calls:
- Setting `is_commander = true` always forces `is_considering = false`.
- Setting `is_considering = true` always forces `is_commander = false`.

This is a deterministic auto-clear, not a validation error — whichever
flag was just set to true wins, the other is silently cleared. In the
degenerate case where a single request sets both `is_commander: true` and
`is_considering: true` simultaneously (not reachable through the UI, which
never sends both in one call), `is_commander` wins.

## Backend Changes (`app.py`)

- `DeckCardUpdate` gains `is_considering: bool | None = None`, alongside
  the existing `quantity`/`is_commander` fields.
- `update_deck_card`: apply the mutual-exclusion rule above when computing
  the new `is_commander`/`is_considering` pair, then persist both.
- `get_deck_cards` and `add_card_to_deck`: include `dc.is_considering` in
  their `SELECT`s and responses, so the frontend always has current state
  for both flags.
- `list_decks` (`GET /api/decks`, backs the deck-switcher palette's
  card-count display): the `card_count` aggregate excludes Considering
  cards —
  ```sql
  COALESCE(SUM(CASE WHEN dc.is_considering THEN 0 ELSE dc.quantity END), 0) AS card_count
  ```

## Frontend Changes (`static/app.js`)

### Toggling Considering

- `buildDeckCardTile`: add a `?`-glyph button (`.deck-considering-btn`,
  mirroring the existing `.deck-cmd-btn` commander button) that calls a
  new `toggleConsidering(cardId)`, structured exactly like the existing
  `toggleCommander(cardId)` — optimistic local update, then
  `PATCH /api/decks/{deckId}/cards/{cardId}` with
  `{ is_considering: !card.is_considering }`, then sync `card.is_commander`
  and `card.is_considering` from the response (the response reflects
  whichever the backend actually persisted, honoring the mutual-exclusion
  rule above).
- The button is **omitted** on the current commander's tile — a commander
  can't be Considering, so there's no useful toggle to show there.
- Tiles with `is_considering` get a distinct-but-subtle style (dashed
  border, reduced opacity) so they read as "not committed" at a glance,
  independent of which section they're grouped into.

### Rendering: extracting a reusable group-section helper

`renderGroupedGrid` currently clears its container and loops over groups,
building a header+body pair for each. Extract that per-group work into:

```js
function renderGroupSection(container, group, buildTileFn, collapsedState) {
  // builds one .group-section (header + body) and appends it to container
}

function renderGroupedGrid(container, groups, buildTileFn, collapsedState) {
  container.innerHTML = '';
  for (const group of groups) renderGroupSection(container, group, buildTileFn, collapsedState);
}
```

`renderGroupedGrid`'s external behavior/signature is unchanged — this is
an internal refactor that lets the ungrouped deck-grid path (below) append
one more section without going through the full grouped-rendering path.

### Grid view — grouped by tag (`deckState.groupBy !== 'none'`)

In `renderDeckGrid`, before calling `groupCards()`: split `filtered` into
`mainCards` (`!is_considering`) and `consideringCards` (`is_considering`).
Run the existing `groupCards(mainCards, tagField)` + per-group `.sort(cmp)`
exactly as today, then, if `consideringCards.length`, append
`{ label: 'Considering', cards: consideringCards.sort(cmp) }` to the
groups array — always after "Untagged", so Considering is always the
last group. Pass the combined array to `renderGroupedGrid` unchanged.

### Grid view — ungrouped (`deckState.groupBy === 'none'`)

Same `mainCards`/`consideringCards` split. `mainCards` render exactly as
today (commander-pinned-first, then `cmp`) into the flat grid. If
`consideringCards.length`, call
`renderGroupSection(el, { label: 'Considering', cards: consideringCards.sort(cmp) }, buildDeckCardTile, deckGroupCollapsed)`
afterward to append one collapsible section below the flat grid, without
clearing what was just rendered.

### Text view (`renderDeckText`)

Add a `Considering` bucket to the existing fixed-order groups object,
after `Other`. Cards with `is_considering` go there instead of their
type-based bucket (checked before the type-line branches, same way
`is_commander` is checked first today). Rendered exactly like the other
buckets — a heading, no collapse control — since the text view has no
collapse mechanic for any section today and this doesn't introduce one.

### Minimized by default

`deckGroupCollapsed` (the existing `Set` of collapsed group labels, shared
by both grid-view rendering paths) starts pre-seeded:
`new Set(['Considering'])`. A small `resetDeckGroupCollapsed()` helper
(`clear()` then re-add `'Considering'`) replaces the current bare
`deckGroupCollapsed.clear()` call on group-by-mode change, and is also
called when switching decks — so Considering always starts collapsed for
a freshly loaded or freshly re-grouped deck, while the existing
click-to-expand/collapse interaction works on it exactly like any other
group thereafter.

### Total count exclusion (frontend)

- `renderDeckContent`'s header total: `deckState.deckCards` is filtered to
  `!is_considering` before summing quantities.
- `syncDeckCount()` (keeps the in-memory deck-switcher list's `card_count`
  in sync after local quantity edits): same filter applied, to match the
  backend's `list_decks` definition.

## Out of Scope

- No changes to the add-card palette — cards are always added to the main
  deck first; Considering is reached via the toggle afterward.
- No drag-and-drop.
- No collapse mechanic added to the text view.
- No changes to Cards/Collection pages or the card detail modal.

## Testing

Backend: extend `tests/test_card_decks.py` with cases for
`update_deck_card`'s mutual-exclusion behavior (setting `is_considering`
clears `is_commander` and vice versa) and for `list_decks`' `card_count`
excluding Considering cards.

Frontend: no JS test runner exists in this repo (consistent with prior
frontend-only work in this project) — verification is manual in the
browser:
- Toggle a card into Considering: it disappears from its tag group /
  ungrouped position and appears in a new, collapsed "Considering"
  section at the bottom; the deck's header total count decreases by its
  quantity.
- Toggle it back: reverses cleanly.
- Set a card as commander while it's in Considering: Considering clears
  automatically; the reverse also holds.
- Text view shows a "Considering" heading last, always expanded.
- Deck-switcher palette's card count matches the deck editor's header
  total (both exclude Considering).
