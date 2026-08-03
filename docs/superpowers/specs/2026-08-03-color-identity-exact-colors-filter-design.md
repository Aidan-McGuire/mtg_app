# Color Identity / Exact Colors Filters — Design

**Date:** 2026-08-03
**Status:** Approved (pending implementation plan)

## Goal

Split the existing single "Colors" filter into two independent filter groups: **Color Identity** (today's behavior, unchanged — subset match against `color_identity`) and a new **Exact Colors** group (exact set-equality match against the card's actual printed color, `colors`). Both are available everywhere the color filter already is: Cards browser, Collection view, Deck editor.

## Scope

- Two separate filter groups in the filter panel, each with its own W/U/B/R/G + Colorless button row and its own selection — not a mode toggle over one shared selection. Both can be active simultaneously and AND together with every other active filter, same as the rest of the filter system.
- **Color Identity** (existing, relabeled from "Colors"): unchanged subset semantics against `color_identity` — a card matches if its color identity is a subset of the selected letters (empty identity always passes). Underlying model fields (`colors`, `colorlessOnly`) and API params (`colors`, `colorless`) are untouched.
- **Exact Colors** (new): matches the card's `colors` column with **exact set equality** — selecting U+B returns only cards whose actual color is precisely {U,B}, not mono-U, not U/B/R, not colorless. New model fields (`exactColors`, `exactColorlessOnly`) and API params (`exact_colors`, `exact_colorless`).
- Out of scope: changing `color_identity` semantics, a combined/single color-selection UI, exposing a raw query-string mini-language.

### Why this works cleanly

The `colors` column (the card's actual printed color, as opposed to `color_identity`) is already selected and returned by every card-bearing endpoint (`CARD_COLS`/`CARD_COLS_C`, `/api/collection`'s hand-written query) but is not currently used by any filter. Both `colors` and `color_identity` are stored **pre-sorted alphabetically** by the importer (`importer.py`'s `sort_colors`: `"".join(sorted(colors))`) — confirmed against the live DB (e.g. `"BG"`, `"BRU"`, never `"GB"` or `"RUB"`). This means exact-match filtering doesn't need the `REPLACE`-chain subset trick the existing Color Identity filter uses — it's a direct string-equality comparison against a canonically-sorted selection string.

### Architecture decision

Extend the existing filter-group pattern with a second, independent group, exactly as the power/toughness feature added two new range groups alongside the existing CMC group. Extract the existing ~35-line color-button-group-building code (currently inline in `buildFilterControls`'s `'colors'` facet block) into a shared `appendColorFilterGroup` helper, used by both the existing Color Identity group and the new Exact Colors group — the same DRY move `appendRangeFilterGroup` made for CMC/Power/Toughness.

**Rejected alternative:** a single color selection with a subset-vs-exact mode toggle. Rejected because the user wants both filters simultaneously available (e.g. narrow to a color identity AND require the printed color be exact), which a single shared selection can't express.

## Section 1 — Backend (`app.py`)

### 1a. `_build_card_filters`

Add two optional params: `exact_colors` (comma-separated letters, e.g. `"U,B"`) and `exact_colorless` (bool).

```python
if exact_colorless:
    frags.append(f"{col}colors = ''")
elif exact_colors:
    wanted = sorted(set(
        c.strip() for c in exact_colors.upper().split(",") if c.strip() in COLOR_LETTERS
    ))
    if wanted:
        frags.append(f"{col}colors = ?")
        params.append("".join(wanted))
```

No `REPLACE` chain needed — `wanted` sorted the same way the importer sorts `colors` at write time, so a straight string comparison is correct.

### 1b. `/api/cards` endpoint

`search_cards` gains `exact_colors: str = Query("")` and `exact_colorless: bool = Query(False)`, threaded through to all three existing `_build_card_filters` call sites (FTS branch, LIKE-fallback branch, no-query branch) — same pattern as every prior filter addition.

## Section 2 — Frontend (`static/app.js`)

### 2a. Filter model

`makeFilterModel` gains `exactColors: new Set(), exactColorlessOnly: false`, alongside the existing `colors`/`colorlessOnly`.

### 2b. Client-side filtering (Collection, Deck editor)

`applyFilters` gains an exact-color check. Since `c.colors` is already a canonically-sorted string from the backend, build the same canonical string from the selected `Set` and compare directly:

```js
if (model.exactColorlessOnly) {
  if ((c.colors || '') !== '') return false;
} else if (model.exactColors.size) {
  const wanted = [...model.exactColors].sort().join('');
  if ((c.colors || '') !== wanted) return false;
}
```

This mirrors the existing Color Identity block's placement and style but is simpler (no subset loop needed).

### 2c. Server-side filtering (Cards browser)

`modelToParams` adds `exact_colors`/`exact_colorless` to the query params object, following the same `colorlessOnly ? ... : colors.size ? ...` pattern already used for `colors`/`colorless`.

### 2d. Active filter count

`activeFilterCount` treats Exact Colors as an independent counter from Color Identity: `if (model.exactColorlessOnly || model.exactColors.size) n++;`.

### 2e. UI — `buildFilterControls`

Extract the existing inline `'colors'` facet block into a shared helper:

```js
function appendColorFilterGroup(panel, label, model, colorsKey, colorlessKey, refreshBadge, onChange) {
  const grp = document.createElement('div');
  grp.className = 'filter-group';
  grp.innerHTML = `<span class="filter-group-label">${label}</span>`;
  const clBtn = document.createElement('button');
  clBtn.className = 'color-btn color-C' + (model[colorlessKey] ? ' active' : '');
  clBtn.textContent = 'C';
  clBtn.title = 'Colorless only';
  for (const letter of COLOR_LETTERS) {
    const b = document.createElement('button');
    b.className = 'color-btn color-' + letter +
      (model[colorsKey].has(letter) ? ' active' : '');
    b.textContent = letter;
    b.dataset.color = letter;
    b.addEventListener('click', () => {
      if (model[colorsKey].has(letter)) model[colorsKey].delete(letter);
      else { model[colorsKey].add(letter); model[colorlessKey] = false; }
      b.classList.toggle('active');
      clBtn.classList.toggle('active', model[colorlessKey]);
      refreshBadge(); onChange();
    });
    grp.appendChild(b);
  }
  clBtn.addEventListener('click', () => {
    model[colorlessKey] = !model[colorlessKey];
    if (model[colorlessKey]) model[colorsKey].clear();
    grp.querySelectorAll('.color-btn').forEach(x =>
      x.classList.toggle('active',
        x === clBtn ? model[colorlessKey] : model[colorsKey].has(x.dataset.color)));
    refreshBadge(); onChange();
  });
  grp.appendChild(clBtn);
  panel.appendChild(grp);
}
```

The `'colors'` facet block becomes `appendColorFilterGroup(panel, 'Color Identity', model, 'colors', 'colorlessOnly', refreshBadge, onChange)`. A new `'exactColors'` facet block calls `appendColorFilterGroup(panel, 'Exact Colors', model, 'exactColors', 'exactColorlessOnly', refreshBadge, onChange)`. Both reuse the existing `.color-btn`/`.color-W` etc. CSS classes — no new styles needed.

### 2f. Per-page wiring

Add `'exactColors'` to the `facets` set at all three existing `buildFilterControls` call sites, alongside the existing `'colors'`:
- Cards browser: `facets: new Set(['colors', 'types', 'cmc', 'power', 'toughness'])` → add `'exactColors'`
- Collection view: `facets: new Set(['colors', 'types', 'cmc', 'power', 'toughness', 'tags'])` → add `'exactColors'`
- Deck editor: `facets: new Set(['colors', 'types', 'cmc', 'power', 'toughness', 'tags'])` → add `'exactColors'`

The existing "Clear" button already resets via `makeFilterModel(...)` overrides, so it picks up the new fields with no extra work.

## Section 3 — Testing

### 3a. Backend tests (extend `tests/test_cards_filter_sort.py`)

`seed_cards` already sets `colors` equal to `color_identity` on every row (`bears`/`ele`/`hydra` → `'G'`, `isle` → `'U'`, `wall` → `''`), but none are multicolor, so exact-set matching against a 2+ color card is untestable without one. Add a multicolor row the same way the power/toughness tests added `Battlefield Construct` — a direct `sqlite3` insert against `db_path` inside the test that needs it (not into `seed_cards` itself, to avoid perturbing the many existing tests that assert exact name lists against the current 5-card set):

```python
conn.execute(
    "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, colors, color_identity) "
    "VALUES ('deathrite', 'Deathrite Shaman', '{B/G}', 1, 'Creature — Elf Shaman', 'BG', 'BG')"
)
```

- Exact-color match on a single letter (`exact_colors=G`) returns only the mono-green seeded cards (`bears`, `ele`, `hydra`), excluding `Deathrite Shaman` despite it containing green.
- Exact-color match on multiple letters (`exact_colors=B,G`) returns only `Deathrite Shaman`.
- Exact colorless (`exact_colorless=1`) matches only `Steel Wall` (`colors=''`).
- Color Identity and Exact Colors combined (both params set) AND correctly: `colors=G&exact_colors=B,G` returns an empty list. `Deathrite Shaman` satisfies `exact_colors=B,G` (its `colors` is exactly `BG`) but fails `colors=G` (its identity `BG` is not a subset of `{G}`); `bears`/`ele`/`hydra` satisfy `colors=G` but fail `exact_colors=B,G` (their `colors` is `G`, not `BG`). No card satisfies both, so asserting an empty result proves the two filters are ANDed rather than ORed (under OR, `Deathrite Shaman` and the mono-green cards would all appear).

### 3b. Frontend tests (extend `tests/js/apply-filters.test.mjs`)

The existing `cards` fixture array sets `color_identity` on every card but no `colors` field (it predates any color filtering). Add a `colors` field to each existing card (equal to its `color_identity`, since none of the current fixture cards are multicolor: `'G'` for Grizzly Bears/Wise Elephant/Mystery Hydra/Compound Beast, `''` for Steel Wall, `'U'` for Ancestral Vision), plus one new multicolor card to exercise exact-set matching against a card that isn't mono-color or colorless:

```js
{ name: 'Deathrite Shaman', power: '1', toughness: '2', cmc: 1, type_line: 'Creature — Elf Shaman', color_identity: 'BG', colors: 'BG' },
```

`baseModel` gains `exactColors: new Set(), exactColorlessOnly: false`. New cases: exact match on `G` returns only mono-green cards (excludes `Deathrite Shaman` despite it containing green); exact match on `B,G` returns only `Deathrite Shaman`; exact colorless returns only `Steel Wall`.

## Notes / caveats

- `colors` can differ from `color_identity` for cards with colored abilities/text but colorless mana cost, and for cards whose identity includes colors from companion/partner rules — Exact Colors intentionally filters on the printed-cost color only; that's the point of having both groups available together.
