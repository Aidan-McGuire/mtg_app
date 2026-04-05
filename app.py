import sqlite3
import hashlib
import httpx
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = Path("mtg.db")
IMAGE_CACHE_DIR = Path("image_cache")
IMAGE_CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500MB

IMAGE_CACHE_DIR.mkdir(exist_ok=True)

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
    dest = cache_path_for(url)
    if not dest.exists():
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=10)
            if r.status_code != 200:
                raise HTTPException(502, "Failed to fetch image from Scryfall")
            dest.write_bytes(r.content)
        evict_cache_if_needed()
    return FileResponse(dest, media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

@app.get("/api/cards")
def search_cards(q: str = Query(""), limit: int = Query(40, le=200), offset: int = Query(0)):
    conn = get_connection()
    cur = conn.cursor()
    if q.strip():
        cur.execute("""
            SELECT c.id, c.oracle_id, c.name, c.mana_cost, c.cmc, c.type_line,
                   c.oracle_text, c.colors, c.color_identity, c.image_uri
            FROM cards_fts f
            JOIN cards c ON c.rowid = f.rowid
            WHERE cards_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        """, (q.strip() + "*", limit, offset))
    else:
        cur.execute("""
            SELECT id, oracle_id, name, mana_cost, cmc, type_line,
                   oracle_text, colors, color_identity, image_uri
            FROM cards
            ORDER BY RANDOM()
            LIMIT ? OFFSET ?
        """, (limit, offset))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/api/cards/{card_id}/printings")
async def get_printings(card_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT oracle_id FROM cards WHERE id = ?", (card_id,))
    row = cur.fetchone()
    conn.close()
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
        image_uri = None
        if "image_uris" in card:
            image_uri = card["image_uris"].get("normal")
        elif "card_faces" in card:
            for face in card["card_faces"]:
                if "image_uris" in face:
                    image_uri = face["image_uris"].get("normal")
                    break
        if image_uri:
            printings.append({
                "set_name": card.get("set_name"),
                "artist":   card.get("artist"),
                "image_uri": image_uri,
            })

    return printings


@app.get("/api/cards/{card_id}")
def get_card(card_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, oracle_id, name, mana_cost, cmc, type_line,
               oracle_text, colors, color_identity, image_uri
        FROM cards WHERE id = ?
    """, (card_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Card not found")
    return dict(row)


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

@app.get("/api/collection")
def get_collection():
    conn = get_connection()
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
    conn.close()
    return rows


@app.post("/api/collection/{card_id}/increment")
def increment_collection(card_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Card not found")
    cur.execute("""
        INSERT INTO collection (card_id, quantity) VALUES (?, 1)
        ON CONFLICT(card_id) DO UPDATE SET quantity = quantity + 1
    """, (card_id,))
    conn.commit()
    cur.execute("SELECT quantity FROM collection WHERE card_id = ?", (card_id,))
    qty = cur.fetchone()["quantity"]
    conn.close()
    return {"card_id": card_id, "quantity": qty}


@app.post("/api/collection/{card_id}/decrement")
def decrement_collection(card_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT quantity FROM collection WHERE card_id = ?", (card_id,))
    row = cur.fetchone()
    if not row or row["quantity"] == 0:
        conn.close()
        return {"card_id": card_id, "quantity": 0}
    new_qty = max(0, row["quantity"] - 1)
    cur.execute("UPDATE collection SET quantity = ? WHERE card_id = ?", (new_qty, card_id))
    conn.commit()
    conn.close()
    return {"card_id": card_id, "quantity": new_qty}


# ---------------------------------------------------------------------------
# Decks
# ---------------------------------------------------------------------------

class DeckCreate(BaseModel):
    name: str


class DeckRename(BaseModel):
    name: str


@app.get("/api/decks")
def list_decks():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.name, d.created_at,
               COALESCE(SUM(dc.quantity), 0) AS card_count
        FROM decks d
        LEFT JOIN deck_cards dc ON dc.deck_id = d.id
        GROUP BY d.id
        ORDER BY d.name
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.post("/api/decks", status_code=201)
def create_deck(body: DeckCreate):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO decks (name) VALUES (?)", (body.name.strip(),))
    conn.commit()
    deck_id = cur.lastrowid
    conn.close()
    return {"id": deck_id, "name": body.name.strip()}


@app.patch("/api/decks/{deck_id}")
def rename_deck(deck_id: int, body: DeckRename):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE decks SET name = ? WHERE id = ?", (body.name.strip(), deck_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Deck not found")
    conn.commit()
    conn.close()
    return {"id": deck_id, "name": body.name.strip()}


@app.delete("/api/decks/{deck_id}", status_code=204)
def delete_deck(deck_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Deck not found")
    conn.commit()
    conn.close()


@app.get("/api/decks/{deck_id}/cards")
def get_deck_cards(deck_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Deck not found")
    cur.execute("""
        SELECT c.id, c.name, c.mana_cost, c.cmc, c.type_line,
               c.oracle_text, c.colors, c.color_identity, c.image_uri,
               dc.quantity, dc.is_commander
        FROM deck_cards dc
        JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ?
        ORDER BY dc.is_commander DESC, c.name
    """, (deck_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM decks WHERE id = ?", (deck_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Deck not found")
    cur.execute("SELECT id FROM cards WHERE id = ?", (body.card_id,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(404, "Card not found")
    cur.execute("""
        INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)
        ON CONFLICT(deck_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity
    """, (deck_id, body.card_id, body.quantity))
    conn.commit()
    cur.execute("SELECT quantity, is_commander FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                (deck_id, body.card_id))
    row = dict(cur.fetchone())
    conn.close()
    return {"deck_id": deck_id, "card_id": body.card_id, **row}


@app.patch("/api/decks/{deck_id}/cards/{card_id}")
def update_deck_card(deck_id: int, card_id: int, body: DeckCardUpdate):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT quantity, is_commander FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                (deck_id, card_id))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Card not in deck")
    new_qty = body.quantity if body.quantity is not None else row["quantity"]
    new_cmd = int(body.is_commander) if body.is_commander is not None else row["is_commander"]
    cur.execute("""
        UPDATE deck_cards SET quantity = ?, is_commander = ?
        WHERE deck_id = ? AND card_id = ?
    """, (new_qty, new_cmd, deck_id, card_id))
    conn.commit()
    conn.close()
    return {"deck_id": deck_id, "card_id": card_id, "quantity": new_qty, "is_commander": bool(new_cmd)}


@app.delete("/api/decks/{deck_id}/cards/{card_id}", status_code=204)
def remove_card_from_deck(deck_id: int, card_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM deck_cards WHERE deck_id = ? AND card_id = ?", (deck_id, card_id))
    if cur.rowcount == 0:
        conn.close()
        raise HTTPException(404, "Card not in deck")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Static files (frontend) — must be last
# ---------------------------------------------------------------------------

app.mount("/", StaticFiles(directory="static", html=True), name="static")
