---
id: 023
title: Preferred printing selectable on detail modal, persists everywhere
priority: medium
status: in-progress
branch: item/23-preferred-printing-selectable-on-detail-modal-persists-everywhere
created: 2026-08-27
---

## Problem

Each card row in `cards` stores exactly one `image_uri`, set arbitrarily to
whichever printing the Scryfall bulk-data importer happened to see first for
that `oracle_id`. Every card-art surface in the app (Cards browser grid,
collection grid, deck grid/list views) reads that same column, so users have
no way to choose which printing's art represents a card.

The detail modal already has an art-browsing strip (`loadPrintings` in
`static/app.js`, backed by `GET /api/cards/{card_id}/printings`) that lets
users preview any printing as the modal's main image, but this selection is
purely session-local — it resets the next time the modal opens and never
affects the stored `image_uri` or any other view.

## Approach

**Backend** — add `POST /api/cards/{card_id}/preferred-printing` accepting
`{"image_uri": "<url>"}`. It updates `cards.image_uri` for that row and
returns the updated card (same shape as `GET /api/cards/{card_id}`). No
server-side re-verification that the URL belongs to a real printing of this
card — consistent with this app's local, single-trusted-user posture
elsewhere (e.g. the existing printings endpoint already trusts Scryfall's
response verbatim).

**Frontend** — in the detail modal, below the existing art strip, add a "Set
as preferred printing" button:
- Disabled/hidden whenever the currently previewed printing already matches
  the card's stored image (`activePrinting.image_uri === card.image_uri`) —
  this covers the initial state, since `activePrinting` already defaults to
  the printing matching `card.image_uri`.
- Enabled once the user clicks a different thumbnail in the strip (browsing
  stays non-destructive/preview-only, per prior decision — clicking a
  thumbnail never persists by itself).
- On click, POST the active printing's front-face `image_uri` (not the back
  face, even if the flip toggle is currently showing it — grid/list views
  only ever render the front face today) to the new endpoint, then update
  `card.image_uri` in place on every cached copy of that card object
  (`state.cards`, `collectionState.cards`, `deckState.deckCards`, and
  `state.modalCard`) and re-render the currently active view. This mirrors
  the existing `syncCollectionTagsOnCard`/`syncDeckTagsOnCard` pattern used
  after tag mutations.
- After a successful save, re-run the disabled/hidden check so the button
  reflects the new persisted state (the just-saved printing is now "already
  preferred").

**Out of scope:**
- No schema change — reuses the existing `cards.image_uri` column, which is
  already the single source every art-rendering call site reads from.
- No change to `image_path` (already dead/unused) or to image disk caching
  (already keyed by URL and fetched on demand; an old printing's cached file
  just ages out via the existing 500MB LRU cap).
- No handling for a preferred *back*-face image — no current view (grid,
  list, or otherwise) ever displays a back face outside the modal's own flip
  toggle, so there's nothing for a back-face preference to affect.

## Acceptance criteria

- [ ] `POST /api/cards/{card_id}/preferred-printing` updates `cards.image_uri`
      for the given card and returns the updated card row; a nonexistent
      `card_id` returns 404.
- [ ] In the detail modal, clicking a printing thumbnail other than the
      current one reveals/enables a "Set as preferred printing" button;
      clicking the currently-preferred thumbnail again keeps it
      disabled/hidden.
- [ ] Clicking "Set as preferred printing" persists the choice (verified by
      reopening the modal for that card — the newly chosen printing is now
      the one that loads as `activePrinting` by default) and immediately
      updates the card's art in the Cards browser grid, the collection grid,
      and any deck grid/list view currently showing that card, without a
      page reload.
- [ ] Flipping to a double-faced card's back face in the modal and then
      saving persists the *front* face's `image_uri`, not the back face's.
