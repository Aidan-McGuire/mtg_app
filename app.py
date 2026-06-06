import asyncio
import re
import sqlite3
import hashlib
import httpx
from contextlib import contextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = Path("mtg.db")
IMAGE_CACHE_DIR = Path("image_cache")
IMAGE_CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500MB
SCRYFALL_IMAGE_HOSTS = ("https://cards.scryfall.io/", "https://c1.scryfall.com/")

# Shared card column list — update here if the cards table schema changes
CARD_COLS   = "id, oracle_id, name, mana_cost, cmc, type_line, oracle_text, colors, color_identity, image_uri"
CARD_COLS_C = "c.id, c.oracle_id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text, c.colors, c.color_identity, c.image_uri"

IMAGE_CACHE_DIR.mkdir(exist_ok=True)


def fetch_collection_tags(cur, card_id: int) -> list[str]:
    cur.execute(
        "SELECT tag FROM collection_tags WHERE card_id = ? ORDER BY tag",
        (card_id,)
    )
    return [r[0] for r in cur.fetchall()]


def fetch_deck_tags(cur, deck_id: int, card_id: int) -> list[str]:
    cur.execute(
        "SELECT tag FROM deck_card_tags WHERE deck_id = ? AND card_id = ? ORDER BY tag",
        (deck_id, card_id)
    )
    return [r[0] for r in cur.fetchall()]

from main import migrate_database
migrate_database()

app = FastAPI()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_ENTRY_RE = re.compile(r'^(\d+)x?\s+(.+?)(?:\s+\([A-Z0-9]{2,6}\)(?:\s+\d+.*)?)?$')
_MARKER_RE = re.compile(r'\s+\*[A-Z]+\*$')  # strip *F* foil markers etc.


def parse_decklist(text: str) -> list[tuple[int, str]]:
    """Return [(quantity, card_name), ...] from a pasted decklist."""
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('//') or line.startswith('#'):
            continue
        m = _ENTRY_RE.match(line)
        if not m:
            continue  # section header or unrecognised line
        qty  = int(m.group(1))
        name = _MARKER_RE.sub('', m.group(2)).strip()
        if qty > 0 and name:
            entries.append((qty, name))
    return entries


def lookup_card_id(cur, name: str) -> int | None:
    """Look up a card id by name, handling MDFC slash variants."""
    # 1. Exact match
    cur.execute("SELECT id FROM cards WHERE name = ? COLLATE NOCASE LIMIT 1", (name,))
    row = cur.fetchone()
    if row:
        return row["id"]

    # 2. Single slash → double slash (Moxfield/Archidekt export MDFCs as "A / B")
    normalized = name.replace(' / ', ' // ')
    if normalized != name:
        cur.execute("SELECT id FROM cards WHERE name = ? COLLATE NOCASE LIMIT 1", (normalized,))
        row = cur.fetchone()
        if row:
            return row["id"]

    # 3. Front-face-only (user wrote just "Bala Ged Recovery" without the back face)
    cur.execute(
        "SELECT id FROM cards WHERE name LIKE ? COLLATE NOCASE LIMIT 1",
        (name + ' //%',)
    )
    row = cur.fetchone()
    return row["id"] if row else None


# ---------------------------------------------------------------------------
# Image cache
# ---------------------------------------------------------------------------

def cache_path_for(url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()
    return IMAGE_CACHE_DIR / f"{digest}.jpg"


def evict_cache_if_needed():
    files = sorted(IMAGE_CACHE_DIR.glob("*.jpg"), key=lambda p: p.stat().st_atime)
    total = sum(p.stat().st_size for p in files)
    while total > IMAGE_CACHE_MAX_BYTES and files:
        oldest = files.pop(0)
        total -= oldest.stat().st_size
        oldest.unlink()


@app.get("/api/image")
async def proxy_image(url: str = Query(...)):
    if not any(url.startswith(host) for host in SCRYFALL_IMAGE_HOSTS):
        raise HTTPException(400, "Invalid image URL")
    dest = cache_path_for(url)
    if not dest.exists():
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            if r.status_code != 200:
                raise HTTPException(502, "Failed to fetch image from Scryfall")
            dest.write_bytes(r.content)
        await asyncio.to_thread(evict_cache_if_needed)
    return FileResponse(dest, media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

@app.get("/api/cards")
def search_cards(q: str = Query(""), limit: int = Query(40, le=200), offset: int = Query(0)):
    with get_db() as conn:
        cur = conn.cursor()
        if q.strip():
            try:
                cur.execute(f"""
                    SELECT {CARD_COLS_C}
                    FROM cards_fts f
                    JOIN cards c ON c.rowid = f.rowid
                    WHERE cards_fts MATCH ?
                      AND c.type_line NOT LIKE 'Token%'
                    ORDER BY rank
                    LIMIT ? OFFSET ?
                """, (q.strip() + "*", limit, offset))
            except sqlite3.OperationalError:
                cur.execute(f"""
                    SELECT {CARD_COLS}
                    FROM cards
                    WHERE name LIKE ?
                      AND type_line NOT LIKE 'Token%'
                    ORDER BY name
                    LIMIT ? OFFSET ?
                """, (f"%{q.strip()}%", limit, offset))
        else:
            cur.execute(f"""
                SELECT {CARD_COLS}
                FROM cards
                WHERE type_line NOT LIKE 'Token%'
                ORDER BY name
                LIMIT ? OFFSET ?
            """, (limit, offset))
        return [dict(r) for r in cur.fetchall()]


@app.get("/api/cards/{card_id}/printings")
async def get_printings(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT oracle_id FROM cards WHERE id = ?", (card_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Card not found")

    oracle_id = row["oracle_id"]
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.scryfall.com/cards/search",
            params={"q": f"oracleid:{oracle_id}", "unique": "art", "order": "released"},
            headers={"User-Agent": "MTGApp/1.0"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json()

    printings = []
    for card in data.get("data", []):
        if "image_uris" in card:
            printings.append({
                "set_name": card.get("set_name"),
                "artist":   card.get("artist"),
                "image_uri": card["image_uris"].get("normal"),
            })
        elif "card_faces" in card:
            faces = [f for f in card["card_faces"] if "image_uris" in f]
            if faces:
                entry = {
                    "set_name": card.get("set_name"),
                    "artist":   card.get("artist"),
                    "image_uri": faces[0]["image_uris"].get("normal"),
                }
                if len(faces) > 1:
                    entry["back_image_uri"] = faces[1]["image_uris"].get("normal")
                printings.append(entry)

    return printings


@app.get("/api/cards/{card_id}")
def get_card(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT {CARD_COLS} FROM cards WHERE id = ?", (card_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Card not found")
    return dict(row)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

@app.get("/api/collection")
def get_collection():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id, c.name, c.mana_cost, c.cmc, c.type_line,
                   c.colors, c.color_identity, c.image_uri,
                   col.quantity
            FROM collection col
            JOIN cards c ON c.id = col.card_id
            WHERE col.quantity > 0
            ORDER BY c.name
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            row["collection_tags"] = fetch_collection_tags(cur, row["id"])
        return rows


@app.post("/api/collection/{card_id}/increment")
def increment_collection(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Card not found")
        cur.execute("""
            INSERT INTO collection (card_id, quantity) VALUES (?, 1)
            ON CONFLICT(card_id) DO UPDATE SET quantity = quantity + 1
        """, (card_id,))
        conn.commit()
        cur.execute("SELECT quantity FROM collection WHERE card_id = ?", (card_id,))
        qty = cur.fetchone()["quantity"]
    return {"card_id": card_id, "quantity": qty}


@app.post("/api/collection/{card_id}/decrement")
def decrement_collection(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT quantity FROM collection WHERE card_id = ?", (card_id,))
        row = cur.fetchone()
        if not row or row["quantity"] == 0:
            return {"card_id": card_id, "quantity": 0}
        new_qty = max(0, row["quantity"] - 1)
        cur.execute("UPDATE collection SET quantity = ? WHERE card_id = ?", (new_qty, card_id))
        conn.commit()
    return {"card_id": card_id, "quantity": new_qty}


class CollectionImport(BaseModel):
    list: str


@app.post("/api/collection/import")
def import_collection(body: CollectionImport):
    entries = parse_decklist(body.list)
    if not entries:
        raise HTTPException(400, "No valid card entries found")

    with get_db() as conn:
        cur = conn.cursor()
        not_found = []
        imported = 0
        for qty, name in entries:
            card_id = lookup_card_id(cur, name)
            if card_id:
                cur.execute("""
                    INSERT INTO collection (card_id, quantity) VALUES (?, ?)
                    ON CONFLICT(card_id) DO UPDATE SET quantity = quantity + excluded.quantity
                """, (card_id, qty))
                imported += qty
            else:
                not_found.append(name)
        conn.commit()

    return {"imported": imported, "not_found": not_found}


# ---------------------------------------------------------------------------
# Decks
# ---------------------------------------------------------------------------

class DeckCreate(BaseModel):
    name: str


class DeckRename(BaseModel):
    name: str


class DeckImport(BaseModel):
    name: str
    list: str


@app.get("/api/decks")
def list_decks():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT d.id, d.name, d.created_at,
                   COALESCE(SUM(dc.quantity), 0) AS card_count
            FROM decks d
            LEFT JOIN deck_cards dc ON dc.deck_id = d.id
            GROUP BY d.id
            ORDER BY d.name
        """)
        return [dict(r) for r in cur.fetchall()]


@app.post("/api/decks", status_code=201)
def create_deck(body: DeckCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO decks (name) VALUES (?)", (body.name.strip(),))
        conn.commit()
        deck_id = cur.lastrowid
    return {"id": deck_id, "name": body.name.strip()}


@app.patch("/api/decks/{deck_id}")
def rename_deck(deck_id: int, body: DeckRename):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE decks SET name = ? WHERE id = ?", (body.name.strip(), deck_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Deck not found")
        conn.commit()
    return {"id": deck_id, "name": body.name.strip()}


@app.delete("/api/decks/{deck_id}", status_code=204)
def delete_deck(deck_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Deck not found")
        conn.commit()


@app.get("/api/decks/{deck_id}/cards")
def get_deck_cards(deck_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Deck not found")
        cur.execute(f"""
            SELECT {CARD_COLS_C}, dc.quantity, dc.is_commander
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            WHERE dc.deck_id = ?
            ORDER BY dc.is_commander DESC, c.name
        """, (deck_id,))
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            row["collection_tags"] = fetch_collection_tags(cur, row["id"])
            row["deck_tags"] = fetch_deck_tags(cur, deck_id, row["id"])
        return rows


@app.post("/api/decks/import", status_code=201)
def import_deck(body: DeckImport):
    entries = parse_decklist(body.list)
    if not entries:
        raise HTTPException(400, "No valid card entries found in decklist")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO decks (name) VALUES (?)", (body.name.strip(),))
        deck_id = cur.lastrowid

        not_found = []
        imported  = 0
        for qty, name in entries:
            card_id = lookup_card_id(cur, name)
            if card_id:
                cur.execute("""
                    INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)
                    ON CONFLICT(deck_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity
                """, (deck_id, card_id, qty))
                imported += qty
            else:
                not_found.append(name)

        conn.commit()

    return {
        "deck":      {"id": deck_id, "name": body.name.strip()},
        "imported":  imported,
        "not_found": not_found,
    }


# ---------------------------------------------------------------------------
# Deck cards
# ---------------------------------------------------------------------------

class DeckCardAdd(BaseModel):
    card_id: int
    quantity: int = 1


class DeckCardUpdate(BaseModel):
    quantity: int | None = None
    is_commander: bool | None = None


@app.post("/api/decks/{deck_id}/cards", status_code=201)
def add_card_to_deck(deck_id: int, body: DeckCardAdd):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Deck not found")
        cur.execute("SELECT id FROM cards WHERE id = ?", (body.card_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Card not found")
        cur.execute("""
            INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)
            ON CONFLICT(deck_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity
        """, (deck_id, body.card_id, body.quantity))
        conn.commit()
        cur.execute("SELECT quantity, is_commander FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, body.card_id))
        row = dict(cur.fetchone())
    return {"deck_id": deck_id, "card_id": body.card_id, **row}


@app.patch("/api/decks/{deck_id}/cards/{card_id}")
def update_deck_card(deck_id: int, card_id: int, body: DeckCardUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT quantity, is_commander FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, card_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Card not in deck")
        new_qty = body.quantity if body.quantity is not None else row["quantity"]
        new_cmd = int(body.is_commander) if body.is_commander is not None else row["is_commander"]
        cur.execute("""
            UPDATE deck_cards SET quantity = ?, is_commander = ?
            WHERE deck_id = ? AND card_id = ?
        """, (new_qty, new_cmd, deck_id, card_id))
        conn.commit()
    return {"deck_id": deck_id, "card_id": card_id, "quantity": new_qty, "is_commander": bool(new_cmd)}


@app.delete("/api/decks/{deck_id}/cards/{card_id}", status_code=204)
def remove_card_from_deck(deck_id: int, card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM deck_cards WHERE deck_id = ? AND card_id = ?", (deck_id, card_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Card not in deck")
        conn.commit()


# ---------------------------------------------------------------------------
# Tag read / autocomplete endpoints
# ---------------------------------------------------------------------------

@app.get("/api/collection/tags")
def list_collection_tags():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT tag FROM collection_tags ORDER BY tag")
        return [r[0] for r in cur.fetchall()]


@app.get("/api/collection/{card_id}/tags")
def get_collection_card_tags(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        return fetch_collection_tags(cur, card_id)


@app.get("/api/decks/{deck_id}/tags")
def list_deck_tags(deck_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT tag FROM deck_card_tags WHERE deck_id = ? ORDER BY tag",
            (deck_id,)
        )
        return [r[0] for r in cur.fetchall()]


@app.get("/api/decks/{deck_id}/cards/{card_id}/tags")
def get_deck_card_tags(deck_id: int, card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        return fetch_deck_tags(cur, deck_id, card_id)


# ---------------------------------------------------------------------------
# Static files (frontend) — must be last
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="static", html=True), name="static")
