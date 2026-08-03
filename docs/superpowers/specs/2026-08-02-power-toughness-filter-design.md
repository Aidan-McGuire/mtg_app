# Power / Toughness Range Filters — Design

**Date:** 2026-08-02
**Status:** Approved (pending implementation plan)

## Goal

Add power and toughness range filters (min/max) to the existing filter system, matching the current CMC range filter in both behavior and UI, across all three pages that already support filtering: Cards, Collection, and Deck editor.

## Scope

- Two new filter groups, **Power** and **Toughness**, each with independent min/max numeric inputs — not a single combined "P/T" control.
- Enabled everywhere the `'cmc'` facet currently is: the Cards browser (server-side), the Collection view (client-side), and the Deck editor (client-side).
- Cards whose power or toughness is non-numeric (`*`, `X`, `1+*`, `∞`, etc.) are **excluded** whenever a power or toughness filter (min or max) is active — consistent with how such values are already pushed to the end of power/toughness sorts.
- Out of scope: changing sort behavior, changing how P/T is displayed, a combined query mini-language.

### Architecture decision

Mirror the existing CMC range filter exactly — it's a proven pattern already wired through the backend query builder, the shared frontend filter model, and `buildFilterControls`, and is already applied uniformly across all three pages via each page's `facets` set. No new architecture is needed; this is an additive extension of the existing one.

**Rejected alternative:** a single freeform "P/T" text filter (e.g. `pow>=3`). Rejected as inconsistent with every other filter in the app (all are structured controls, not query strings) and harder to discover than two range inputs matching the existing "Mana value" group.

## Section 1 — Backend (`app.py`)

### 1a. Numeric-safe comparison

Power/toughness are stored as free-text strings (Scryfall values like `"3"`, `"*"`, `"1+*"`, `"2.5"`, `"∞"`). The existing sort helper's numeric check (`col GLOB '[0-9]*'`) is too loose for filtering — `"1+*"` starts with a digit but isn't a real number, and `CAST("1+*" AS REAL)` in SQLite silently evaluates to `1.0`, which would wrongly let a card with variable power pass a `power_min=1` filter.

Filtering uses a stricter check: a column value counts as numeric only if it matches `GLOB '[0-9]*'` **and** does not match `GLOB '*[^0-9.]*'` (i.e. contains only digits and `.`). This correctly excludes `*`, `X`, `∞`, `1+*`, `+1`, `-1`, etc., while still matching `"3"`, `"2.5"`, `"001"`.

### 1b. `_build_card_filters`

Add four optional params: `power_min, power_max, toughness_min, toughness_max` (floats). For each bound provided, append a fragment of the form:

```sql
({col}power GLOB '[0-9]*' AND {col}power NOT GLOB '*[^0-9.]*' AND CAST({col}power AS REAL) >= ?)
```

(mirrored for `<=` on max, and for `toughness`). These combine with `AND` alongside the existing filters, so a card must satisfy every active bound to match.

### 1c. `/api/cards` endpoint

`search_cards` gains four new optional `Query` params (`power_min`, `power_max`, `toughness_min`, `toughness_max`, all `float | None`), threaded through to all three existing `_build_card_filters` call sites (FTS branch, LIKE-fallback branch, no-query branch) — same as `cmc_min`/`cmc_max` today.

## Section 2 — Frontend (`app.js`)

### 2a. Filter model

`makeFilterModel` gains four fields: `powerMin, powerMax, toughnessMin, toughnessMax` (default `null`), alongside the existing `cmcMin`/`cmcMax`.

### 2b. Client-side filtering (Collection, Deck editor)

`applyFilters` gains power/toughness range checks using a new `ptNumStrict()` helper (not the existing `ptNum()`, which is too loose for filtering — it accepts `"1+*"`-style compound values as numeric, which would violate this feature's exclusion requirement). `ptNum` itself stays unchanged since `sortComparator` still needs its existing behavior. For each of power/toughness: if a min or max bound is set and `ptNum(card.power)` is `null` (non-numeric/missing), the card is excluded; otherwise it must fall within the active bound(s).

### 2c. Server-side filtering (Cards browser)

`modelToParams` adds `power_min`/`power_max`/`toughness_min`/`toughness_max` to the query params object whenever those model fields are non-null, matching the existing `cmc_min`/`cmc_max` handling.

### 2d. Active filter count

`activeFilterCount` treats Power and Toughness as two independent counters (one increments if either `powerMin`/`powerMax` is set, the other if either `toughnessMin`/`toughnessMax` is set) — consistent with them being separate UI groups.

### 2e. UI — `buildFilterControls`

Two new facets, `'power'` and `'toughness'`. Each renders a labeled min–max input pair identical in structure/styling to the existing "Mana value" (CMC) group. Since this produces three near-identical range-input blocks, extract the shared min/max-pair construction (currently the inline `mk(key, placeholder)` closure in the CMC block) into one small helper function used by all three facets, rather than duplicating it a third time.

### 2f. Per-page wiring

Add `'power'` and `'toughness'` to the `facets` set at all three existing `buildFilterControls` call sites:
- Cards browser (`facets: new Set(['colors', 'types', 'cmc'])` → add `'power', 'toughness'`)
- Collection view (`facets: new Set(['colors', 'types', 'cmc', 'tags'])` → add `'power', 'toughness'`)
- Deck editor (`facets: new Set(['colors', 'types', 'cmc', 'tags'])` → add `'power', 'toughness'`)

The existing "Clear" button already resets via `makeFilterModel(...)` overrides, so it picks up the new fields with no extra work.

## Section 3 — Testing

### 3a. Backend tests (extend `tests/test_cards_filter_sort.py`)

- Filter by power range (min, max, both) on `/api/cards`.
- Filter by toughness range.
- A card with non-numeric power (e.g. `"*"` or `"1+*"`) is excluded when a power filter is active, even though `"1+*"` starts with a digit.
- Combining a power/toughness filter with an existing filter (e.g. `q` or `cmc_min`) still ANDs correctly.

### 3b. Frontend tests

`tests/js/` already has a convention for testing pure functions lifted out of `static/app.js` via sentinel comments (`// ── name ──` / `// ── end name ──`) and evaluated standalone with `new Function` (see `filter-decks.test.mjs`, `parse-add-query.test.mjs`). `applyFilters` fits this pattern directly — add sentinel comments around the existing `ptNum`/`sortComparator`/`applyFilters` block and a new `tests/js/apply-filters.test.mjs` covering power/toughness range filtering, including the non-numeric-exclusion case. Run via `node tests/js/apply-filters.test.mjs` (no test runner/CI wiring exists for these — same as the other `tests/js/*.test.mjs` files today).

`buildFilterControls` (DOM-building) has no test harness and stays manual: verify in the running app (`uvicorn app:app --reload`) across all three pages — filter by power/toughness alone and combined with other filters, confirm non-numeric P/T cards drop out, confirm Clear resets the new inputs, confirm the active-filter badge count.

## Notes / caveats

- The stricter numeric check introduced here (excluding `"1+*"`-style values) is intentionally *not* backported to the existing power/toughness **sort** comparator — sort already pushes non-numeric values last regardless of exact parse correctness, and changing that is out of scope for this feature.
