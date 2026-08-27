# Preferred Printing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user pick which printing's art represents a card everywhere in the app (not just as a session-local modal preview), by persisting the chosen printing's `image_uri` to `cards.image_uri`.

**Spec:** `docs/superpowers/backlog/023-preferred-printing.md`

**Tech Stack:** FastAPI backend (`app.py`, pytest suite in `tests/` using an in-memory scratch DB via `tests/conftest.py`), vanilla JS frontend (`static/app.js`, no build step, no JS test framework — verify by reading + `node --check`).

## Task 1: Backend endpoint

**Files:** Modify `app.py` (add near `get_card`/`get_printings`, ~line 470-480).

- Add `class PreferredPrinting(BaseModel): image_uri: str`.
- Add `POST /api/cards/{card_id}/preferred-printing`: 404 if card doesn't exist, else `UPDATE cards SET image_uri = ? WHERE id = ?`, commit, and return the updated row via the same `CARD_COLS` shape as `GET /api/cards/{card_id}`.

**Test:** New file `tests/test_preferred_printing.py` (follows `tests/test_card_decks.py` conventions):
- POST with a new `image_uri` for card 1 → 200, response has the new `image_uri` and the full `CARD_COLS` shape.
- A follow-up `GET /api/cards/1` reflects the persisted change.
- POST to a nonexistent card id → 404 `{"detail": "Card not found"}`.

Write the test first (red), then implement the endpoint (green).

## Task 2: Frontend — button + save + cross-view sync

**Files:** Modify `static/app.js`:
- `openModal` (~line 886-902): add a `<button id="modal-set-preferred-btn" class="hidden">Set as preferred printing</button>` under the art strip.
- `loadPrintings` (~line 1077): track whether `activePrinting.image_uri === card.image_uri`; show/hide the button accordingly, both on initial load and after each thumbnail click. Wire the button's click handler to POST `{ image_uri: activePrinting.image_uri }` (front face only — never `back_image_uri`) to `/api/cards/${card.id}/preferred-printing`, then:
  - Update `card.image_uri` in place (the `card` object passed into `openModal`/`loadPrintings` — same object referenced by `state.modalCard`).
  - Call a new small helper, e.g. `syncCardArtOnCard(cardId, imageUri)`, that: updates the matching entries in `state.cards` and `collectionState.cards` and `deckState.deckCards` in place, patches any currently-rendered Cards-browser tile `<img>` directly via `document.querySelectorAll('#card-grid .card-tile[data-id="ID"] img')` (that grid has no single full-rerender function — it's built incrementally via infinite scroll, unlike the collection/deck grids), and calls `renderCollectionGrid()` and `renderDeckContent()` unconditionally — mirroring the existing `syncCollectionTagsOnCard`/`syncDeckTagsOnCard` pattern at `static/app.js:1227-1235`.
  - Re-run the disabled/hidden check after save so the button reflects the new persisted state.

**Verify:** `node --check static/app.js` (use `/opt/homebrew/bin/node` if present), plus careful reading — no JS test framework exists for this repo.

## Task 3: Full suite + wrap-up

- `python3 -m pytest -q` — full suite green.
- Commit after Task 1 and after Task 2.
- `python3 scripts/backlog_cli.py finish docs/superpowers/backlog/023-preferred-printing.md`, commit, push.
