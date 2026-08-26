import asyncio
import re
import sqlite3
import hashlib
import httpx
import threading
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from main import migrate_database
from importer import import_cards

DB_PATH = Path("mtg.db")
IMAGE_CACHE_DIR = Path("image_cache")
IMAGE_CACHE_MAX_BYTES = 500 * 1024 * 1024  # 500MB
SCRYFALL_IMAGE_HOSTS = ("https://cards.scryfall.io/", "https://c1.scryfall.com/")

# Shared card column list — update here if the cards table schema changes
CARD_COLS   = "id, oracle_id, name, mana_cost, cmc, type_line, oracle_text, colors, color_identity, image_uri, power, toughness"
CARD_COLS_C = "c.id, c.oracle_id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text, c.colors, c.color_identity, c.image_uri, c.power, c.toughness"

COLOR_LETTERS = ("W", "U", "B", "R", "G")


def _numeric_pt_frags(col_expr, min_v, max_v):
    """Return SQL fragments constraining a power/toughness column to a numeric range.

    Power/toughness are stored as free text (e.g. "3", "*", "1+*", "2.5"). A
    value only counts as numeric if it consists solely of digits and ".",
    which excludes "1+*"-style variable values that a bare GLOB '[0-9]*'
    check would wrongly accept (SQLite's CAST stops at the first non-numeric
    character, so CAST('1+*' AS REAL) == 1.0).
    """
    is_numeric = f"({col_expr} GLOB '[0-9]*' AND {col_expr} NOT GLOB '*[^0-9.]*')"
    frags = []
    if min_v is not None:
        frags.append(f"({is_numeric} AND CAST({col_expr} AS REAL) >= ?)")
    if max_v is not None:
        frags.append(f"({is_numeric} AND CAST({col_expr} AS REAL) <= ?)")
    return frags


def _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="",
                         power_min=None, power_max=None, toughness_min=None, toughness_max=None,
                         exact_colors="", exact_colorless=False):
    """Return (sql_fragments, params) for the optional card filters.

    `col` is an optional column prefix (e.g. "c.") for aliased queries.
    """
    frags, params = [], []

    if colorless:
        frags.append(f"{col}color_identity = ''")
    elif colors:
        wanted = list(dict.fromkeys(
                c.strip() for c in colors.upper().split(",") if c.strip() in COLOR_LETTERS
            ))
        if wanted:
            # subset: stripping every selected letter leaves nothing (colorless '' passes)
            expr = f"{col}color_identity"
            for letter in wanted:
                expr = f"REPLACE({expr}, '{letter}', '')"
            frags.append(f"{expr} = ''")

    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else []
    if type_list:
        ors = " OR ".join([f"{col}type_line LIKE ?"] * len(type_list))
        frags.append(f"({ors})")
        params.extend(f"%{t}%" for t in type_list)

    if cmc_min is not None:
        frags.append(f"{col}cmc >= ?")
        params.append(cmc_min)
    if cmc_max is not None:
        frags.append(f"{col}cmc <= ?")
        params.append(cmc_max)

    if text and text.strip():
        frags.append(f"{col}oracle_text LIKE ?")
        params.append(f"%{text.strip()}%")

    for frag in _numeric_pt_frags(f"{col}power", power_min, power_max):
        frags.append(frag)
    if power_min is not None:
        params.append(power_min)
    if power_max is not None:
        params.append(power_max)

    for frag in _numeric_pt_frags(f"{col}toughness", toughness_min, toughness_max):
        frags.append(frag)
    if toughness_min is not None:
        params.append(toughness_min)
    if toughness_max is not None:
        params.append(toughness_max)

    if exact_colorless:
        frags.append(f"{col}colors = ''")
    elif exact_colors:
        wanted_exact = sorted(set(
            c.strip() for c in exact_colors.upper().split(",") if c.strip() in COLOR_LETTERS
        ))
        if wanted_exact:
            frags.append(f"{col}colors = ?")
            params.append("".join(wanted_exact))

    return frags, params

_TYPE_RANK_SQL = """CASE
    WHEN {col} LIKE '%Creature%'     THEN 0
    WHEN {col} LIKE '%Instant%'      THEN 1
    WHEN {col} LIKE '%Sorcery%'      THEN 2
    WHEN {col} LIKE '%Enchantment%'  THEN 3
    WHEN {col} LIKE '%Artifact%'     THEN 4
    WHEN {col} LIKE '%Planeswalker%' THEN 5
    WHEN {col} LIKE '%Land%'         THEN 6
    WHEN {col} LIKE '%Battle%'       THEN 7
    ELSE 8 END"""


def _order_by(sort, direction, col_prefix=""):
    """Return an ORDER BY clause body. Unknown sort -> name."""
    d = "DESC" if direction == "desc" else "ASC"
    name = f"{col_prefix}name COLLATE NOCASE"
    if sort == "cmc":
        return f"{col_prefix}cmc {d}, {name} ASC"
    if sort == "type":
        rank = _TYPE_RANK_SQL.format(col=f"{col_prefix}type_line")
        return f"{rank} {d}, {name} ASC"
    if sort in ("power", "toughness"):
        c = f"{col_prefix}{sort}"
        # numeric rows first; non-numeric/NULL last (regardless of direction)
        return (
            f"CASE WHEN {c} GLOB '[0-9]*' THEN 0 ELSE 1 END ASC, "
            f"CASE WHEN {c} GLOB '[0-9]*' THEN CAST({c} AS REAL) ELSE NULL END {d}, "
            f"{name} ASC"
        )
    return f"{name} {d}"


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

migrate_database()

REFRESH_INTERVAL = timedelta(days=7)
REFRESH_LOG_PATH = Path("card_refresh.log")


def _should_refresh_cards():
    with get_db() as conn:
        row = conn.execute("SELECT cards_last_refreshed FROM schema_version LIMIT 1").fetchone()
    last = row[0] if row else None
    if not last:
        return True
    return datetime.now(timezone.utc) - datetime.fromisoformat(last) > REFRESH_INTERVAL


def _run_card_refresh():
    started = datetime.now(timezone.utc)
    try:
        result = import_cards()
        with get_db() as conn:
            conn.execute(
                "UPDATE schema_version SET cards_last_refreshed = ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()
        line = (f"{started.isoformat()} refreshed cards: "
                f"{result['inserted']} new, {result['updated']} updated, "
                f"{result['processed']} processed\n")
    except Exception as e:
        line = f"{started.isoformat()} card refresh FAILED: {e}\n"
    with open(REFRESH_LOG_PATH, "a") as f:
        f.write(line)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _should_refresh_cards():
        threading.Thread(target=_run_card_refresh, daemon=True).start()
    yield


app = FastAPI(lifespan=lifespan)


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

_ENTRY_RE = re.compile(r'^(\d+)x?\s+(.+?)(?:\s+\([A-Z0-9]{2,6}\)(?:\s+\d+.*)?)?(?:\s+\{[0-9]+\})?$')
_MARKER_RE = re.compile(r'\s+\*[A-Z]+\*$')  # strip *F* foil markers etc.

_SMART_QUOTE_TRANSLATION = str.maketrans({
    '‘': "'", '’': "'",  # curly single quotes → straight
    '“': '"', '”': '"',  # curly double quotes → straight
})


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
    """Look up a card id by name, handling MDFC slash variants and smart quotes.

    Returns None both when no card matches and when a tier's query matches
    more than one card — an ambiguous match is never silently resolved to
    one of several candidates.
    """
    name = name.translate(_SMART_QUOTE_TRANSLATION)

    # 1. Exact match
    cur.execute("SELECT id FROM cards WHERE name = ? COLLATE NOCASE LIMIT 2", (name,))
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]["id"]
    if len(rows) > 1:
        return None

    # 2. Single slash → double slash (Moxfield/Archidekt export MDFCs as "A / B")
    normalized = name.replace(' / ', ' // ')
    if normalized != name:
        cur.execute("SELECT id FROM cards WHERE name = ? COLLATE NOCASE LIMIT 2", (normalized,))
        rows = cur.fetchall()
        if len(rows) == 1:
            return rows[0]["id"]
        if len(rows) > 1:
            return None

    # 3. Front-face-only (user wrote just "Bala Ged Recovery" without the back face)
    cur.execute(
        "SELECT id FROM cards WHERE name LIKE ? COLLATE NOCASE LIMIT 2",
        (name + ' //%',)
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]["id"]
    return None


def _record_import_failure(cur, source: str, deck_id: int | None, card_name: str, requested_qty: int) -> None:
    cur.execute("""
        INSERT INTO import_failures (source, deck_id, card_name, requested_qty)
        VALUES (?, ?, ?, ?)
    """, (source, deck_id, card_name, requested_qty))


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
            r = await client.get(url, timeout=10, headers={"User-Agent": "MTGApp/1.0"})
            if r.status_code != 200:
                raise HTTPException(502, "Failed to fetch image from Scryfall")
            dest.write_bytes(r.content)
        await asyncio.to_thread(evict_cache_if_needed)
    return FileResponse(dest, media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

@app.get("/api/cards")
def search_cards(
    q: str = Query(""),
    limit: int = Query(40, le=200),
    offset: int = Query(0),
    colors: str = Query(""),
    colorless: bool = Query(False),
    types: str = Query(""),
    cmc_min: float | None = Query(None),
    cmc_max: float | None = Query(None),
    power_min: float | None = Query(None),
    power_max: float | None = Query(None),
    toughness_min: float | None = Query(None),
    toughness_max: float | None = Query(None),
    exact_colors: str = Query(""),
    exact_colorless: bool = Query(False),
    text: str = Query(""),
    sort: str = Query("name"),
    direction: str = Query("asc", alias="dir"),
):
    with get_db() as conn:
        cur = conn.cursor()
        if q.strip():
            cfrags, cparams = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text, col="c.",
                                                    power_min=power_min, power_max=power_max,
                                                    toughness_min=toughness_min, toughness_max=toughness_max,
                                                    exact_colors=exact_colors, exact_colorless=exact_colorless)
            where_c = "".join(f" AND {f}" for f in cfrags)
            try:
                fts_order = "rank" if sort == "name" else _order_by(sort, direction, "c.")
                cur.execute(f"""
                    SELECT {CARD_COLS_C}
                    FROM cards_fts f
                    JOIN cards c ON c.rowid = f.rowid
                    WHERE cards_fts MATCH ?
                      AND c.type_line NOT LIKE 'Token%'
                      {where_c}
                    ORDER BY {fts_order}
                    LIMIT ? OFFSET ?
                """, (q.strip() + "*", *cparams, limit, offset))
            except sqlite3.OperationalError:
                bfrags, bparams = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text,
                                                       power_min=power_min, power_max=power_max,
                                                       toughness_min=toughness_min, toughness_max=toughness_max,
                                                       exact_colors=exact_colors, exact_colorless=exact_colorless)
                where_b = "".join(f" AND {f}" for f in bfrags)
                cur.execute(f"""
                    SELECT {CARD_COLS}
                    FROM cards
                    WHERE name LIKE ?
                      AND type_line NOT LIKE 'Token%'
                      {where_b}
                    ORDER BY {_order_by(sort, direction)}
                    LIMIT ? OFFSET ?
                """, (f"%{q.strip()}%", *bparams, limit, offset))
        else:
            frags, params = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text,
                                                 power_min=power_min, power_max=power_max,
                                                 toughness_min=toughness_min, toughness_max=toughness_max,
                                                 exact_colors=exact_colors, exact_colorless=exact_colorless)
            where_extra = "".join(f" AND {f}" for f in frags)
            cur.execute(f"""
                SELECT {CARD_COLS}
                FROM cards
                WHERE type_line NOT LIKE 'Token%'
                  {where_extra}
                ORDER BY {_order_by(sort, direction)}
                LIMIT ? OFFSET ?
            """, (*params, limit, offset))
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


@app.get("/api/cards/{card_id}/decks")
def get_card_decks(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM cards WHERE id = ?", (card_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Card not found")
        cur.execute("""
            SELECT DISTINCT d.id, d.name
            FROM deck_cards dc
            JOIN decks d ON d.id = dc.deck_id
            WHERE dc.card_id = ?
            ORDER BY d.name
        """, (card_id,))
        return [dict(r) for r in cur.fetchall()]


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
            SELECT c.id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text,
                   c.colors, c.color_identity, c.image_uri, c.power, c.toughness,
                   col.quantity,
                   COALESCE((
                       SELECT SUM(dc.quantity) FROM deck_cards dc
                       JOIN decks d ON d.id = dc.deck_id
                       WHERE dc.card_id = c.id AND dc.is_considering = 0 AND d.built = 1
                   ), 0) AS allocated_qty
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
        if new_qty == 0:
            cur.execute("DELETE FROM collection_tags WHERE card_id = ?", (card_id,))
        conn.commit()
    return {"card_id": card_id, "quantity": new_qty}


class CollectionImport(BaseModel):
    list: str


class TagAdd(BaseModel):
    tag: str


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
                _record_import_failure(cur, "collection", None, name, qty)
        conn.commit()

    return {"imported": imported, "not_found": not_found}


# ---------------------------------------------------------------------------
# Decks
# ---------------------------------------------------------------------------

class DeckCreate(BaseModel):
    name: str


class DeckUpdate(BaseModel):
    name: str | None = None
    built: bool | None = None


class DeckImport(BaseModel):
    name: str
    list: str


@app.get("/api/decks")
def list_decks():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT d.id, d.name, d.created_at, d.built,
                   COALESCE(SUM(CASE WHEN dc.is_considering THEN 0 ELSE dc.quantity END), 0) AS card_count
            FROM decks d
            LEFT JOIN deck_cards dc ON dc.deck_id = d.id
            GROUP BY d.id
            ORDER BY d.name
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            row["built"] = bool(row["built"])
        return rows


@app.post("/api/decks", status_code=201)
def create_deck(body: DeckCreate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO decks (name) VALUES (?)", (body.name.strip(),))
        conn.commit()
        deck_id = cur.lastrowid
    return {"id": deck_id, "name": body.name.strip()}


@app.patch("/api/decks/{deck_id}")
def update_deck(deck_id: int, body: DeckUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, built FROM decks WHERE id = ?", (deck_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Deck not found")
        new_name = body.name.strip() if body.name is not None else row["name"]
        new_built = int(body.built) if body.built is not None else row["built"]
        cur.execute("UPDATE decks SET name = ?, built = ? WHERE id = ?", (new_name, new_built, deck_id))
        conn.commit()
    return {"id": deck_id, "name": new_name, "built": bool(new_built)}


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
            SELECT {CARD_COLS_C}, dc.quantity, dc.is_commander, dc.is_considering
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            WHERE dc.deck_id = ?
            ORDER BY dc.is_commander DESC, c.name
        """, (deck_id,))
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            row["is_commander"] = bool(row["is_commander"])
            row["is_considering"] = bool(row["is_considering"])
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
                _record_import_failure(cur, "deck", deck_id, name, qty)

        conn.commit()

    return {
        "deck":      {"id": deck_id, "name": body.name.strip()},
        "imported":  imported,
        "not_found": not_found,
    }


# ---------------------------------------------------------------------------
# Import failures
# ---------------------------------------------------------------------------

@app.get("/api/import-failures")
def list_import_failures(resolved: str = Query("false")):
    with get_db() as conn:
        cur = conn.cursor()
        where = ""
        if resolved == "false":
            where = "WHERE f.resolved_at IS NULL"
        elif resolved == "true":
            where = "WHERE f.resolved_at IS NOT NULL"
        elif resolved != "all":
            raise HTTPException(400, "resolved must be 'false', 'true', or 'all'")

        cur.execute(f"""
            SELECT f.id, f.source, f.deck_id, d.name AS deck_name,
                   f.card_name, f.requested_qty, f.created_at, f.resolved_at
            FROM import_failures f
            LEFT JOIN decks d ON d.id = f.deck_id
            {where}
            ORDER BY f.created_at DESC, f.id DESC
        """)
        return [dict(r) for r in cur.fetchall()]


@app.post("/api/import-failures/{failure_id}/resolve")
def resolve_import_failure(failure_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM import_failures WHERE id = ?", (failure_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Import failure not found")
        cur.execute(
            "UPDATE import_failures SET resolved_at = datetime('now') WHERE id = ?",
            (failure_id,)
        )
        conn.commit()
        cur.execute("""
            SELECT f.id, f.source, f.deck_id, d.name AS deck_name,
                   f.card_name, f.requested_qty, f.created_at, f.resolved_at
            FROM import_failures f
            LEFT JOIN decks d ON d.id = f.deck_id
            WHERE f.id = ?
        """, (failure_id,))
        return dict(cur.fetchone())


# ---------------------------------------------------------------------------
# Deck cards
# ---------------------------------------------------------------------------

class DeckCardAdd(BaseModel):
    card_id: int
    quantity: int = 1


class DeckCardUpdate(BaseModel):
    quantity: int | None = None
    is_commander: bool | None = None
    is_considering: bool | None = None


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
        cur.execute("SELECT quantity, is_commander, is_considering FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, body.card_id))
        row = dict(cur.fetchone())
        row["is_commander"] = bool(row["is_commander"])
        row["is_considering"] = bool(row["is_considering"])
    return {"deck_id": deck_id, "card_id": body.card_id, **row}


@app.patch("/api/decks/{deck_id}/cards/{card_id}")
def update_deck_card(deck_id: int, card_id: int, body: DeckCardUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT quantity, is_commander, is_considering FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, card_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Card not in deck")
        new_qty = body.quantity if body.quantity is not None else row["quantity"]
        new_cmd = int(body.is_commander) if body.is_commander is not None else row["is_commander"]
        new_considering = int(body.is_considering) if body.is_considering is not None else row["is_considering"]
        # Commander and Considering are mutually exclusive. Whichever flag was
        # just explicitly set true wins over the other; is_commander wins if
        # a single request sets both true.
        if body.is_commander:
            new_considering = 0
        elif body.is_considering:
            new_cmd = 0
        cur.execute("""
            UPDATE deck_cards SET quantity = ?, is_commander = ?, is_considering = ?
            WHERE deck_id = ? AND card_id = ?
        """, (new_qty, new_cmd, new_considering, deck_id, card_id))
        conn.commit()
    return {
        "deck_id": deck_id, "card_id": card_id, "quantity": new_qty,
        "is_commander": bool(new_cmd), "is_considering": bool(new_considering),
    }


@app.delete("/api/decks/{deck_id}/cards/{card_id}", status_code=204)
def remove_card_from_deck(deck_id: int, card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM deck_cards WHERE deck_id = ? AND card_id = ?",
            (deck_id, card_id)
        )
        if not cur.fetchone():
            raise HTTPException(404, "Card not in deck")
        cur.execute(
            "DELETE FROM deck_card_tags WHERE deck_id = ? AND card_id = ?",
            (deck_id, card_id)
        )
        cur.execute(
            "DELETE FROM deck_cards WHERE deck_id = ? AND card_id = ?",
            (deck_id, card_id)
        )
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


@app.post("/api/collection/{card_id}/tags")
def add_collection_tag(card_id: int, body: TagAdd):
    tag = body.tag.strip().lower()
    if not tag:
        raise HTTPException(400, "Tag cannot be empty")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT quantity FROM collection WHERE card_id = ?", (card_id,))
        row = cur.fetchone()
        if not row or row["quantity"] == 0:
            raise HTTPException(404, "Card not in collection")
        cur.execute(
            "INSERT OR IGNORE INTO collection_tags (card_id, tag) VALUES (?, ?)",
            (card_id, tag)
        )
        conn.commit()
        return fetch_collection_tags(cur, card_id)


@app.delete("/api/collection/{card_id}/tags/{tag}", status_code=204)
def remove_collection_tag(card_id: int, tag: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM collection_tags WHERE card_id = ? AND tag = ?",
            (card_id, tag.strip().lower())
        )
        conn.commit()


@app.post("/api/decks/{deck_id}/cards/{card_id}/tags")
def add_deck_card_tag(deck_id: int, card_id: int, body: TagAdd):
    tag = body.tag.strip().lower()
    if not tag:
        raise HTTPException(400, "Tag cannot be empty")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM deck_cards WHERE deck_id = ? AND card_id = ?",
            (deck_id, card_id)
        )
        if not cur.fetchone():
            raise HTTPException(404, "Card not in deck")
        cur.execute(
            "INSERT OR IGNORE INTO deck_card_tags (deck_id, card_id, tag) VALUES (?, ?, ?)",
            (deck_id, card_id, tag)
        )
        conn.commit()
        return fetch_deck_tags(cur, deck_id, card_id)


@app.delete("/api/decks/{deck_id}/cards/{card_id}/tags/{tag}", status_code=204)
def remove_deck_card_tag(deck_id: int, card_id: int, tag: str):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM deck_card_tags WHERE deck_id = ? AND card_id = ? AND tag = ?",
            (deck_id, card_id, tag.strip().lower())
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Static files (frontend) — must be last
# ---------------------------------------------------------------------------

class RevalidatingStaticFiles(StaticFiles):
    """StaticFiles that forces the browser to revalidate on every request.

    Without this the frontend has no cache headers at all, so a browser may
    reuse a stale app.js alongside a freshly-fetched index.html: the new markup
    renders but its handlers were never registered, and controls silently do
    nothing. "no-cache" means revalidate, not re-download — the ETag still
    yields a 304 when the file is unchanged.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", RevalidatingStaticFiles(directory="static", html=True), name="static")
