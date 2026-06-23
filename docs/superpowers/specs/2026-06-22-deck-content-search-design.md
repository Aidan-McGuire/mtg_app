# Deck Page: content search box

## Goal

Add a search box scoped to the deck editor that filters the deck's current
cards by name, rules text, or card type.

## Scope

- **In:** a text input over the deck's contents bound to `deckState.filter.text`; a one-line extension of the shared text matcher to also match `type_line`; state reset on deck switch.
- **Out:** backend changes (all filtering is client-side over already-loaded deck cards), separate per-field inputs (one combined box), a new keyboard shortcut (`/` stays mapped to the add-cards box), changes to the add-cards search (`deck-search`).

## Context

The codebase already has a shared filter pipeline:

- `makeFilterModel()` returns a model with a `text` field (among `colors`, `types`, `cmc`, `tags`, `sort`, `dir`).
- `applyFilters(cards, model)` filters by `model.text` against **`name` + `oracle_text`** only (not `type_line`), plus the faceted filters.
- The deck editor already renders its contents via `renderDeckContent()`, which calls `applyFilters(deckState.deckCards, deckState.filter)`.
- `buildFilterControls` deliberately does NOT render a text input — text is "owned by the page's search box." The **collection** page has such a box (`collection-search` → `collectionState.query` → `collectionState.filter.text` in `renderCollectionGrid`). The **deck** page has no equivalent; its `deck-search` box is for *adding* cards (separate column/results), not filtering contents.

## Changes

### 1. Extend the shared text matcher (applies everywhere)

In `applyFilters` (`static/app.js`), the `model.text` branch currently is:

```js
if (model.text) {
  const t = model.text.toLowerCase();
  if (!c.name.toLowerCase().includes(t) &&
      !(c.oracle_text || '').toLowerCase().includes(t)) return false;
}
```

Add a `type_line` clause so a card matches if the text appears in name, rules
text, OR type:

```js
if (model.text) {
  const t = model.text.toLowerCase();
  if (!c.name.toLowerCase().includes(t) &&
      !(c.oracle_text || '').toLowerCase().includes(t) &&
      !(c.type_line || '').toLowerCase().includes(t)) return false;
}
```

This is shared, so the collection search also gains type matching (intended,
per design decision "apply everywhere"). Case-insensitive substring match.

### 2. Deck content search box (new)

- **HTML** (`static/index.html`): add a text input at the top of the deck
  content column (`deck-content-col`), above `#deck-grid-view`/`#deck-text-view`:
  `id="deck-content-search"`, a class consistent with existing inputs,
  placeholder `Filter cards… (name, text, type)`, `autocomplete="off"`.
- **State** (`static/app.js`): add `query: ''` to the `deckState` object
  (alongside `filter`).
- **Render**: in `renderDeckContent()`, set
  `deckState.filter.text = deckState.query;` before the existing
  `applyFilters(deckState.deckCards, deckState.filter)` call (mirrors the
  collection's `renderCollectionGrid` line `collectionState.filter.text = collectionState.query`).
- **Events**:
  - `input` on `#deck-content-search` → `deckState.query = e.target.value; renderDeckContent();`
  - `keydown` Escape → `e.target.blur(); deckState.query = ''; renderDeckContent();`

### 3. Reset on deck switch

`selectDeck(id)` already resets `deckState.filter = makeFilterModel()`. Also:

- set `deckState.query = ''`, and
- clear the input element's value (`document.getElementById('deck-content-search').value = ''`)

so a search term does not carry between decks.

## Empty state

The deck content views already render an empty message when the filtered list
is empty (the existing filter-panel empty path). Because the search box feeds
the same `applyFilters` result, a no-match search reuses that message with no
new code. Confirm during implementation that the wording reads sensibly for a
search miss (e.g. not implying the deck itself is empty); adjust only if it
reads wrong.

## Error handling

- No network or async work — purely synchronous filtering of in-memory cards.
- Guard the deck-switch input clear with a null check (the element exists in the
  deck editor, which is present whenever a deck is selected).

## Testing

- `applyFilters` is a pure function; the `type_line` extension is the only logic
  change. There is no JavaScript test harness in this project (tests are pytest
  over the Python backend), so verification is `node --check static/app.js` for
  syntax plus manual click-through:
  - typing a type word (e.g. `instant`) filters the deck to matching cards;
  - typing part of a card name filters by name;
  - typing rules-text words filters by oracle text;
  - clearing the box (or Escape) restores the full deck;
  - switching decks clears the search.
- Confirm the collection search still works and now also matches type.
