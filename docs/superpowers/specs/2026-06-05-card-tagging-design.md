# Card Tagging — Design Spec
**Date:** 2026-06-05

## Overview

Add free-form text tag support to cards at two scopes:
- **Collection tags** — applied to a card in the user's collection; persist across all decks
- **Deck tags** — applied to a card within a specific deck; each card-in-deck can have different tags in different decks

Tags are user-defined lowercase strings. Both tag types are visible simultaneously on a card when viewing a deck. Cards can be grouped by either tag type in collection and deck views.

---

## Schema

Two new tables. Migration bumps `schema_version` to 2.

```sql
CREATE TABLE collection_tags (
    id      INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    tag     TEXT    NOT NULL,
    UNIQUE(card_id, tag)
);

CREATE TABLE deck_card_tags (
    id      INTEGER PRIMARY KEY,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    tag     TEXT    NOT NULL,
    UNIQUE(deck_id, card_id, tag)
);
```

- `UNIQUE` constraints prevent duplicate tags per card/deck.
- `collection_tags` cascades off `cards(id)` (if a card is ever deleted from the DB). Removing a card from the `collection` table does not cascade automatically — the `decrement_collection` endpoint must explicitly delete collection tags when quantity reaches 0.
- `deck_card_tags` cascades off `decks(id)` — deleting a deck removes all its tags. Removing a card from a deck (`DELETE FROM deck_cards`) does not cascade — the `remove_card_from_deck` endpoint must also delete that card's deck tags.
- Tags are normalized to lowercase + trimmed at insert time.

---

## API

### Tags included in existing list responses

`GET /api/collection` — each card object gains a `collection_tags: string[]` field.

`GET /api/decks/{deck_id}/cards` — each card object gains both `collection_tags: string[]` and `deck_tags: string[]`.

### Tag mutation endpoints

**Collection tags:**
```
POST   /api/collection/{card_id}/tags          body: { "tag": "foil" }
DELETE /api/collection/{card_id}/tags/{tag}
```

**Deck card tags:**
```
POST   /api/decks/{deck_id}/cards/{card_id}/tags     body: { "tag": "ramp" }
DELETE /api/decks/{deck_id}/cards/{card_id}/tags/{tag}
```

- `POST` returns the full updated tag list for that card/scope.
- `DELETE` returns 204.
- Adding a tag that already exists is a no-op (200, not an error).

### Tag autocomplete endpoints

```
GET /api/collection/tags              — sorted list of all collection tags in use
GET /api/decks/{deck_id}/tags         — sorted list of all deck tags in use for that deck
```

Used to populate autocomplete suggestions in the tag input.

---

## UI

### Tag display on card tiles

- Tags render as small pill/chip elements on card tiles in grid views.
- Collection tags: muted gold color.
- Deck tags: muted blue/teal color.
- Both show simultaneously on deck card tiles.
- In deck text list view, tags appear inline after the card name.

### Tag editing (in card detail modal only)

Tag editing is not inline on tiles — tiles are too dense. Editing lives in the card detail modal.

- **Collection tags section:** shown whenever the card is in the user's collection.
- **Deck tags section:** shown only when the modal is opened from within a deck view.
- Each section renders existing tags as chips with an `×` remove button.
- A small text input at the end of the chip row allows adding new tags: press `Enter` or `,` to confirm.
- The input fetches autocomplete suggestions from the tag list endpoints so previously used tags are easy to reuse.
- Removing a tag fires the DELETE endpoint immediately (no save button needed).

### Grouping

A "Group by" control in the collection view toolbar and deck editor header.

Options:
- **None** — flat grid (default)
- **Collection tag**
- **Deck tag** (deck view only)

Grouping behavior:
- Cards are organized into labeled sections, one per tag value.
- A card with multiple tags appears in each of its tag sections.
- Cards with no tags appear in an **"Untagged"** section at the bottom.
- Each section header shows the tag name and card count, and can be collapsed (JS state only, not persisted).
- Within each section, cards are sorted by name.
- Group-by selection is transient UI state — not persisted to the DB or URL.

---

## Out of scope

- Grouping by type, subtype, CMC, or color identity (noted in project notes for later)
- Global tag rename/delete management UI
- Tag-based search/filter (separate from grouping)
- Persisting group-by or collapse state across sessions
