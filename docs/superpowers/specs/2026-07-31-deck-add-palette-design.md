# Deck Page: add-card command palette

## Goal

Reclaim the deck editor's permanently-dedicated add-card column by moving the
add-card search into a foreground palette that appears only while in use, and
give it a way to add many copies of one card in a single action.

## Scope

- **In:** removing `.deck-search-col`; a fixed-position `#deck-add-palette`
  hosting the existing `deck-search` input and results; `/` and a `+ Add` button
  as openers; `Escape`/outside-click as closers; an `x20 Swamp` quantity prefix
  in the query; live "in deck" counts on result rows; post-add reset with a
  confirmation note; collapsing `addCardToDeck`'s two-path add into one POST.
- **Out:** backend changes (the POST endpoint already accepts `quantity` and
  upserts additively); changes to the deck content filter box
  (`deck-content-search`); changes to the deck grid tile size; the deck-list
  sidebar (stays 220px); deck composition/ratio display (deferred to a later
  spec).

## Context

The deck editor body is two columns (`static/index.html:85-99`):

- `.deck-search-col` — **260px fixed** (`static/style.css:560-567`), always
  present whether or not you are adding cards. Holds `#deck-search` and the
  scrollable `#deck-search-results`.
- `.deck-content-col` — `flex: 1`, holds the content filter input and the
  grid/text views.

With the 220px `.decks-sidebar` this puts ~480px of permanent chrome on the
page. On a 1512px window the content column gets ~1030px, which at
`grid-template-columns: repeat(auto-fill, minmax(140px, 1fr))`
(`static/style.css:671`) yields 6 tile columns.

Existing behaviour that must survive:

- `/` focuses `#deck-search` when the decks view is active (`static/app.js:1113-1115`).
- `Escape` blurs the input and clears results (`static/app.js:2012-2017`).
- `ArrowUp`/`ArrowDown` move `deckState.searchFocusIdx`; `ArrowUp` past the top
  returns focus to the input (`static/app.js:1997-2007`).
- `Enter` or `+` adds the focused result; clicking a row or its `+` button also
  adds (`static/app.js:1839-1840`, `2008-2011`).
- `closeModal()` refocuses `#deck-search` when the decks view is active
  (`static/app.js:1058-1059`).

Relevant facts that make bulk add cheap:

- `POST /api/decks/{deck_id}/cards` takes `quantity` (default 1) and upserts
  with `ON CONFLICT ... SET quantity = quantity + excluded.quantity`
  (`app.py:588-590`). Adding N copies, to a new or existing card, is one call.
- `API.addCardToDeck(deckId, cardId, quantity = 1)` already forwards the
  quantity (`static/app.js:57-62`); no wrapper change needed.
- There is **no** reusable transient-note helper. `showNote` (`static/app.js:774`)
  is a closure local to the modal's add-to-deck section and writes to
  `#modal-add-deck-note`. The palette needs its own note element and timer.
- The decklist importer parses entries with
  `^(\d+)x?\s+(.+?)(?:\s+\([A-Z0-9]{2,6}\)(?:\s+\d+.*)?)?$` (`app.py:145`) —
  i.e. a *leading* number, optional trailing `x`. The palette deliberately does
  **not** reuse this form; see §4.

## Changes

### 1. Remove the dedicated search column

- **HTML** (`static/index.html`): delete the `.deck-search-col` div. Move
  `#deck-search` and `#deck-search-results` into the new palette element
  (below). `.deck-content-col` becomes the only child of `.deck-editor-body`.
- **CSS** (`static/style.css`): delete the `.deck-search-col` rule. Keep
  `.deck-search-input`, `#deck-search-results`, `.deck-search-row`,
  `.dsearch-*` rules — the elements survive, only their container changes.
  Adjust `.deck-search-input` margin to suit the palette's padding.

The grid gains ~260px (6 → 8 tile columns at 1512px). Tile size is unchanged.

### 2. The palette element

Add `#deck-add-palette` as a sibling of the deck editor (so it is not clipped
by `overflow: hidden` on `.deck-editor-body`), hidden by default via the
project's existing `.hidden` class.

```
#deck-add-palette {
  position: fixed;
  top: 110px;
  left: 50%;
  transform: translateX(-50%);
  width: 560px;
  max-width: calc(100vw - 40px);
  max-height: 60vh;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0,0,0,0.5);
  z-index: 50;   /* above .filter-panel (20), below .modal-overlay (100) */
}
```

`#deck-search-results` inside it keeps `flex: 1; overflow-y: auto;` so the
result list scrolls within the 60vh cap.

**No dim backdrop.** The deck stays fully visible and readable behind the
palette so added cards can be seen appearing in the grid.

Open/close helpers `openAddPalette()` / `closeAddPalette()`:

- `openAddPalette()` — no-op unless `deckState.currentDeckId` is set. Removes
  `.hidden`, focuses `#deck-search`, selects any existing input text.
- `closeAddPalette()` — adds `.hidden`, blurs the input, clears the input value,
  sets `deckState.searchResults = []`, re-renders results, resets
  `deckState.searchFocusIdx = -1`.

### 3. Openers and closers

- **`+ Add` button** in `.deck-editor-acts` (`static/index.html:70-83`), before
  the group-by select. `title="Add cards  (/)"`. Click → `openAddPalette()`.
- **`/`** — the existing handler (`static/app.js:1113-1115`) changes from
  "focus the input" to `openAddPalette()`. Because the palette is hidden by
  default, `/` is now the only keyboard way in, matching the app's keyboard-first
  goal.
- **`Escape`** — the global handler's decks branch (`static/app.js:1098-1110`)
  and the input's own Escape branch (`static/app.js:2012-2017`) both call
  `closeAddPalette()`. Keep the existing precedence: an open filter panel or
  import modal still absorbs Escape first.
- **Outside click** — a `mousedown` listener on `document` closes the palette
  when the target is outside `#deck-add-palette` and outside the `+ Add` button
  (excluding the button prevents the click that opens it from immediately
  closing it).

`closeModal()`'s decks-view refocus of `#deck-search` (`static/app.js:1058-1059`)
must become conditional: refocus only if the palette is open, otherwise focusing
a hidden input steals focus with no visible target.

### 4. Quantity prefix

Add a pure helper, kept free of DOM access so it is testable:

```js
/**
 * Splits a leading xN quantity off an add-card query.
 * "x20 swamp" -> { quantity: 20, name: "swamp" }
 * "swamp"     -> { quantity: 1,  name: "swamp" }
 * "20 swamp"  -> { quantity: 1,  name: "20 swamp" }   // bare number is not a quantity
 */
function parseAddQuery(raw) { ... }
```

Rules:

- Match `^x(\d+)\s+(.+)$` on the trimmed query, case-insensitive on the `x`
  (`X20 Swamp` works too).
- The `x` **must** lead the string and **must** precede the digits. A bare
  leading number is never a quantity.
- No match → `{ quantity: 1, name: trimmed }`. **Singleton is the default**; a
  normal add never requires typing a prefix.
- A parsed quantity of `0` is treated as `1` (nothing else is meaningful).
- Clamp the parsed quantity to a sane ceiling (999) so a typo cannot add
  thousands of copies.

This diverges from the importer's `20x Swamp` form (`app.py:145`) by design.
Requiring the leading `x` removes the ambiguity a bare leading number creates:
card names that begin with digits (`1996 World Champion`, `60 Feet Tall`) are
searched literally instead of being silently read as a count. The importer is
parsing whole pasted decklists where a leading count is the established
convention; the palette is parsing a free-text search box where it is not.

Wiring:

- `onDeckSearchInput` runs the search against `parseAddQuery(q).name`, so
  `x20 swamp` shows Swamp results live while typing.
- An empty `name` (query is only a prefix, e.g. `x20 `) clears results rather
  than searching.
- The add path uses `parseAddQuery(...).quantity` as the POST quantity.
- A `×N` badge renders next to the input whenever the parsed quantity is > 1, so
  the prefix is visibly registered before committing.

### 5. Result rows and the add path

Result rows (`renderDeckSearchResults`, `static/app.js:1827-1843`) gain a
current-deck-quantity span, read from in-memory state — no API call:

```
Lightning Bolt      Instant      in deck: 2      [+]
```

Cards not in the deck show no count (not `in deck: 0`).

`addCardToDeck(cardId, cardData, quantity = 1)` (`static/app.js:1845-1861`)
collapses its two branches into one POST, since the backend upserts additively:

- Always `POST` with the quantity. Drop the `incDeckCard` branch.
- On success, if the card is already in `deckState.deckCards`, set its
  `quantity` to the returned value; otherwise push a new entry as today.
- Keep the `deckState.addingCards` in-flight guard so a double Enter cannot fire
  two overlapping POSTs for the same card.
- Then `syncDeckCount()` and `renderDeckContent()` as today.

`incDeckCard` stays — the grid tile `+` button still uses it.

### 6. Post-add behaviour

After a successful add, the palette **stays open** and resets for the next card:

- clear the input value and `deckState.searchResults`, re-render results,
- reset `deckState.searchFocusIdx = -1`,
- refocus the input,
- `showAddNote('Added 20× Swamp')` — a palette-local note helper writing to a
  `#deck-add-note` element; without this, a cleared palette looks like nothing
  happened.

Use the singular form (`Added Lightning Bolt`) when quantity is 1.

## Keyboard contract

| Key | Behaviour |
| --- | --- |
| `/` | Open the palette (decks view, a deck selected) |
| `↑` `↓` | Move through results; `↑` past the top returns to the input |
| `Enter` / `+` | Add the focused result at the parsed quantity |
| `Escape` | Close the palette |

Only `/` (focus → open) and `Escape` (blur → close) change meaning. Arrow, Enter
and `+` handling is untouched.

## Error handling

- `openAddPalette()` no-ops without `deckState.currentDeckId`, so the palette
  can never open with nowhere to add to. `addCardToDeck` retains its own
  `if (!deckState.currentDeckId) return` guard.
- A failed POST is caught as today; add a `showNote(..., true)` error note so a
  failure is not silent now that the palette self-clears on success.
- The in-flight guard (`deckState.addingCards`) prevents duplicate POSTs from
  repeated Enter presses.
- Guard element lookups in `closeAddPalette()` — it can be called from the
  global Escape handler while the deck editor is hidden.

## Testing

Backend is unchanged, so no pytest additions.

- `parseAddQuery` is pure and DOM-free: test it with node (native ARM node at
  `/opt/homebrew`) over the cases `swamp` → 1, `x20 swamp` → 20, `X4 Bolt` → 4,
  `20 swamp` → 1 (name kept whole), `20x swamp` → 1 (name kept whole),
  `x20` → 1 with name `x20` (no name to split; trailing space trims to the
  same case), `x0 swamp` → 1, 
  `x9999 swamp` → 999, and `1996 World Champion` → 1 with the full name intact.
- `node --check static/app.js` for syntax.
- Manual click-through in the running app:
  - `/` opens the palette; `+ Add` opens the same palette; the deck is visible
    behind it.
  - Type a name, `↑↓`, `Enter` → card added, palette clears and stays open,
    note appears.
  - `x20 swamp` → `×20` badge shows, Swamp results appear while typing, Enter
    adds 20 in one call.
  - `20 swamp` shows no badge and searches the literal string — a bare number
    is not a quantity.
  - Adding a card already in the deck increases its quantity by the parsed
    amount rather than resetting it.
  - Result rows show `in deck: N` for cards already present.
  - `Escape` and an outside click both close it; the grid is full width and
    shows more columns than before.
  - Opening and closing a card modal from the decks view does not strand focus.
