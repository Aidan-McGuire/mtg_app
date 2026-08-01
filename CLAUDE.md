# MTG App

A local Magic: The Gathering deckbuilding and collection management app. Runs as a localhost web app (FastAPI backend, vanilla JS frontend). Keyboard-first navigation, mouse supported.

## Project Structure

- `main.py` — initializes the SQLite database schema
- `importer.py` — downloads and streams Scryfall bulk data, inserts cards into the DB
- `app.py` — FastAPI server (to be created)
- `static/` — frontend HTML/CSS/JS (to be created)
- `mtg.db` — local SQLite database (WAL mode, foreign keys enabled)
- `image_cache/` — on-demand disk cache for card images (500MB cap, LRU eviction)

## Database Schema

### Existing
- `cards` — deduplicated by `oracle_id`; stores name, mana_cost, cmc, type_line, oracle_text, colors, color_identity, image_uri, image_path
- `cards_fts` — FTS5 virtual table over name and oracle_text
- `schema_version` — single-row version tracking

### Planned
- `collection` — card_id → cards, quantity (owned card counts)
- `decks` — id, name, created_at
- `deck_cards` — deck_id → decks, card_id → cards, quantity, is_commander (bool)

## Key Design Decisions

- Cards are deduplicated by `oracle_id` (one row per unique card, not per printing)
- Tokens and digital-only cards are skipped during import
- Colors are stored as sorted strings (e.g. "BGU") for consistent querying
- Bulk data is streamed and gzip-decoded in memory using ijson to avoid loading the full JSON file
- Inserts are batched in groups of 1000 for performance
- Images are fetched on demand from Scryfall CDN (image_uri stored in DB), cached to disk at image_cache/ with a 500MB LRU cap — no bulk image storage
- Decks are free-form (no format legality checks); Commander decks support designating a commander card via is_commander flag on deck_cards

## UI Features (Planned)

### Card Browser
- Search bar with FTS (name + oracle text)
- Results grid with card images
- Keyboard navigation: arrow keys to move, Enter to select
- Increment/decrement owned collection count per card

### Deck Builder
- Create/rename/delete decks
- Search and add cards to a deck
- Designate a commander card
- Visual grid view + text list view (e.g. `4x Lightning Bolt`)
- Keyboard-first, mouse supported

## Setup

```bash
python main.py       # initialize the database
python importer.py   # download and import cards from Scryfall
uvicorn app:app --reload # start the dev server (once app.py exists)
```
