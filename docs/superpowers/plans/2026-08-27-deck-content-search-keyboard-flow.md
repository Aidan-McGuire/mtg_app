# Plan: deck content-search keyboard flow (item 028)

Small, mechanical, frontend-only change to `static/app.js` and
`static/index.html`. No backend, no DB, no new pure-function extraction
needed (this touches DOM event wiring, which the existing `tests/js/`
sentinel-comment convention doesn't cover).

## Steps

1. In the global `keydown` handler's `/` branch (`static/app.js` ~1298-1309):
   change the `decksActive` case from `openAddPalette()` to focusing
   `#deck-content-search`, guarded like the Collection/Cards branches (only
   act if it isn't already the active element).
2. Add a new `a`/`A` handler alongside the `d`/`D` deck-switcher handler
   (~1311-1318): when the deck page is active and not typing in a field,
   call `openAddPalette()`.
3. Update `#deck-content-search`'s keydown listener (~1719-1721) to add an
   `ArrowDown` case mirroring the Cards page's `#search-input` pattern:
   compute `deckNavGroups` for whichever view is active (grid/text), and if
   there's a first group with a first tile, blur the search box and
   `focusDeckTile` it. No-op if there are no results.
4. Update `#deck-add-btn`'s `title` in `static/index.html` from
   `Add cards  (/)` to `Add cards  (a)`.

## Verification

- Read through each acceptance criterion against the new code by hand
  (no automated coverage exists for this DOM-event code path).
- `node --check static/app.js` for syntax validity.
- Run `tests/js/*.test.mjs` (unaffected, but confirms nothing else broke).
- `python3 -m pytest` for backend regression safety.

## Out of scope

- Add-cards palette's own internal keyboard handling (unaffected).
- Reconciling with sibling items 027 (`Enter` case added near
  Backspace/`c`) and 029 (expected to touch this same block next) — the
  human maintainer reconciles at merge time. Keep the diff minimal and
  scoped to exactly what's described above.
