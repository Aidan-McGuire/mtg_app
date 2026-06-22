# List-View Filter, Sort & Search — Design

**Date:** 2026-06-21
**Status:** Approved (pending implementation plan)

## Goal

Add filter, sort, and search support to all three "list view" pages — **Cards**, **Collection**, and **Decks** (deck contents) — with controls tailored to each page. Sorting must respect existing category groupings (sort *within* groups when a group-by is active).

## Scope

### Filter facets
- **Color identity** — W/U/B/R/G + colorless.
- **Card type** — creature, instant, sorcery, enchantment, artifact, planeswalker, land, etc.
- **Mana value (CMC)** — numeric range (min/max).
- **Tags** — collection tags (Collection) and collection + deck tags (Decks). Not applicable to Cards.
- **Rules text** — substring match on `oracle_text`.

### Sort options
- **Name** (A–Z, current default)
- **Mana value (CMC)**
- **Card type**
- **Quantity** — Collection/Decks only
- **Power / Toughness**

All sorts support a direction toggle (asc/desc). Non-numeric or missing power/toughness values sort last.

### Per-page tailoring
| Page | Filters | Sort | Notes |
|------|---------|------|-------|
| Cards | color, type, cmc, rules text | name, cmc, type, power, toughness | server-side; no tags/quantity |
| Collection | color, type, cmc, tags, rules text | name, cmc, type, quantity, power, toughness | client-side; keeps group-by |
| Decks | color, type, cmc, collection+deck tags, rules text | name, cmc, type, quantity, power, toughness | client-side; commander pinned; grid + text views |

### Architecture decision
**Approach A**: a shared filter/sort module owns the control UI and the filter/sort model. Collection/Decks apply it to their already-loaded in-memory arrays; Cards translates the model into `/api/cards` query params and re-fetches (preserving the existing paginated FTS / infinite-scroll design). This matches the current architecture with the least disruption and keeps each page as snappy as today.

Rejected alternatives:
- **B — everything server-side**: adds a network round-trip per keystroke/toggle and re-implements tag/quantity joins for tiny, already-loaded datasets. Overkill.
- **C — everything client-side**: loading the full ~30k-row cards table into the browser is too heavy and discards the existing paginated FTS design.

## Section 1 — Data & API (backend)

### 1a. Schema migration (v3)
Add a `version < 3` block to `migrate_database()`:
```sql
ALTER TABLE cards ADD COLUMN power TEXT;
ALTER TABLE cards ADD COLUMN toughness TEXT;
```
Stored as raw Scryfall strings, nullable (only creatures/vehicles have them). Numeric coercion happens at sort time, not stored — keeps the schema minimal. Update `tests/conftest.py` `_SCHEMA` with the same two columns.

### 1b. Importer: backfill + idempotency
- Add `power`/`toughness` to the insert via an `extract_pt(card)` helper (top-level value, else front face — mirrors `extract_image_uri`).
- Make the importer **idempotent** so re-running backfills existing rows:
  - Load existing `oracle_id`s into a set once at start.
  - New cards → insert into `cards` + `cards_fts`.
  - Existing cards → `UPDATE` the `cards` row (including power/toughness); skip FTS.
  - This also fixes a latent bug where re-running currently duplicates every `cards_fts` row.
- Backfill mechanism: run `python importer.py` once (re-streams bulk data, updates P/T on existing rows).

### 1c. `/api/cards` query params
Extend `search_cards` with optional params, composed into the SQL `WHERE`/`ORDER BY` on top of the existing FTS/base branches (the `type_line NOT LIKE 'Token%'` exclusion stays):
- `colors` — e.g. `U,B`; **subset semantics** ("color identity within selected"; empty identity = colorless, always a subset). A mode toggle (subset vs. contains) can be added later.
- `types` — e.g. `Creature,Land`; `type_line LIKE` per type, OR-combined.
- `cmc_min`, `cmc_max` — numeric range.
- `text` — substring on `oracle_text` (explicit rules-text filter; the main search box already does FTS over name + text).
- `sort` — `name|cmc|type|power|toughness`; `dir` — `asc|desc`. Non-numeric/missing P/T sorts last via a `CASE … GLOB '[0-9]*'` ordering key.

### 1d. Fields for client-side views
- Add `power, toughness` to `CARD_COLS` / `CARD_COLS_C` (deck cards pick them up automatically).
- Add `oracle_text, power, toughness` to the hand-written `/api/collection` query.

## Section 2 — Frontend

### 2a. Shared filter/sort module
A module (in `app.js` or a new `static/filtersort.js`) owning:
- **Model** (per view): `{ text, colors:Set, types:Set, cmcMin, cmcMax, tags:Set, sort, dir }`. `groupBy` remains the separate, existing state field.
- `buildControls(config)` — renders the control bar into a container. `config` declares which facets are enabled for the page + dynamic options (available tags) + an `onChange` callback. This keeps per-page tailoring DRY.
- `sortComparator(model)` — single source of truth for ordering (name/cmc/type/quantity/power/toughness, asc/desc; non-numeric P/T and missing values last).
- `applyFilters(cards, model)` — returns the filtered array (client-side).

### 2b. Grouping interaction
Filter first, then group, then sort **within** each group using `sortComparator`:
- Grouped: `groupCards(applyFilters(cards), field)` → sort each group's `cards` with the comparator. Group order unchanged (alpha labels / by-type, "Untagged" last).
- Flat: sort the filtered array directly.
- Commander: in flat deck view sorts first regardless; in grouped view appears within its group (as today).

### 2c. Per-page wiring
- **Cards:** model → `/api/cards` query string; on any change, reset `offset` and re-fetch (reuses `loadCards` + infinite scroll). Facets: text (existing search box feeds `model.text`), color, type, cmc; sort by name/cmc/type/power/toughness. No tags/quantity.
- **Collection:** existing name filter folds into the model; add color/type/cmc/tags filters + sort (incl. quantity). Keeps group-by. Applied in-memory over `collectionState.cards`.
- **Decks:** new content filter bar: color/type/cmc + tags (collection and deck) + sort (incl. quantity). Applied in-memory over `deckState.deckCards`. Works in grid view; text view keeps its type-section layout but honors the active filter.

### 2d. UI & keyboard
- A compact **filter bar** beside/below each page's existing search row: a **Sort** `<select>` + a direction toggle button, and a **Filters** disclosure opening a panel with color buttons (W U B R G + C), type checkboxes, CMC min/max inputs, and a tag multi-select (where applicable).
- An **active-filter count badge** + a **Clear** affordance.
- Native focusable controls (selects/buttons/inputs); `/` still focuses search; `Esc` clears/closes. Consistent layout across all three pages.
- Out of scope: the broader keyboard-navigation refinement noted in `notes.md` (separate item).

## Section 3 — Testing & rollout

### 3a. Backend tests (pytest, extends `tests/`)
- `/api/cards` filters: `colors` subset semantics (incl. colorless), `types` OR-combining, `cmc_min/max` range, `text` rules-text match, and each `sort`/`dir` — with explicit coverage that non-numeric/missing power/toughness sorts last.
- Collection/deck endpoints return `power`/`toughness` (and collection returns `oracle_text`).
- Importer idempotency: re-running over a small fixture updates power/toughness on existing rows and does not duplicate `cards_fts` rows.
- `conftest.py` `_SCHEMA` updated with the two new columns.

### 3b. Frontend verification
No JS test harness exists, so the module's pure functions (`sortComparator`, `applyFilters`) are written as standalone/testable units; behavior verified manually in the running app (`uvicorn app:app --reload`) across all three pages — filter, sort, sort-within-groups, clear.

### 3c. Rollout order
1. Schema migration + `conftest` schema.
2. Importer P/T + idempotency; run backfill (`python importer.py`).
3. `/api/cards` params + `CARD_COLS` / collection fields + backend tests.
4. Shared frontend module (model, `buildControls`, `sortComparator`, `applyFilters`).
5. Per-page wiring: Cards → Collection → Decks.
6. UI polish (filter bar, badge, clear) + manual verification.

## Notes / caveats
- Power/toughness sort shows empty values until the backfill re-import (`python importer.py`) is run.
- Color filter ships with subset semantics; a subset-vs-contains mode toggle is a possible later refinement.
