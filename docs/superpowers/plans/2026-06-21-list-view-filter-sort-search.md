# List-View Filter, Sort & Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add filter, sort, and search controls (tailored per page) to the Cards, Collection, and Decks list views, with sorting that respects category groupings.

**Architecture:** A shared frontend filter/sort module owns a per-view model and the control UI. Collection and Decks apply the model to their already-loaded in-memory arrays; the Cards page translates the model into `/api/cards` query params and re-fetches (preserving the existing paginated FTS design). New `power`/`toughness` columns are added to the schema and backfilled by re-running the importer.

**Tech Stack:** FastAPI + SQLite (backend), vanilla JS (frontend), pytest + FastAPI TestClient (tests).

**Spec:** `docs/superpowers/specs/2026-06-21-list-view-filter-sort-search-design.md`

---

## File Structure

- `main.py` — add schema migration v3 (power/toughness columns).
- `importer.py` — extract power/toughness; make import idempotent so re-running backfills.
- `app.py` — add `power`/`toughness` to `CARD_COLS`/`CARD_COLS_C`; add `oracle_text`/`power`/`toughness` to the `/api/collection` query; add filter/sort params to `/api/cards`.
- `tests/conftest.py` — add `power`/`toughness` columns to `_SCHEMA` and seed sortable test data.
- `tests/test_cards_filter_sort.py` — **new** — backend filter/sort tests.
- `tests/test_importer_idempotent.py` — **new** — importer backfill/idempotency test.
- `static/app.js` — shared filter/sort module (model, `sortComparator`, `applyFilters`, `buildFilterControls`), and per-page wiring for Cards, Collection, Decks.
- `static/index.html` — control-bar containers for each page.
- `static/style.css` — styles for the filter bar, filter panel, and badges.

---

## Task 1: Schema migration v3 — power/toughness columns

**Files:**
- Modify: `main.py` (the `migrate_database` function, after the `version < 2` block ~line 111)
- Modify: `tests/conftest.py:7-19` (`_SCHEMA` cards table)

- [ ] **Step 1: Add the migration block**

In `main.py`, inside `migrate_database()`, after the existing `if version < 2:` block and before `conn.commit()`, add:

```python
    if version < 3:
        cur.execute("ALTER TABLE cards ADD COLUMN power TEXT;")
        cur.execute("ALTER TABLE cards ADD COLUMN toughness TEXT;")
        cur.execute("UPDATE schema_version SET version = 3;")
```

- [ ] **Step 2: Update the test schema to match**

In `tests/conftest.py`, change the `cards` table in `_SCHEMA` to include the two new columns (add them after `image_path TEXT`):

```sql
CREATE TABLE cards (
    id INTEGER PRIMARY KEY,
    oracle_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    mana_cost TEXT,
    cmc REAL,
    type_line TEXT NOT NULL,
    oracle_text TEXT,
    colors TEXT,
    color_identity TEXT,
    image_uri TEXT,
    image_path TEXT,
    power TEXT,
    toughness TEXT
);
```

Also bump the seed version row to 3: change `INSERT INTO schema_version VALUES (2);` to `INSERT INTO schema_version VALUES (3);`.

- [ ] **Step 3: Run the existing suite to verify nothing broke**

Run: `python -m pytest -q`
Expected: PASS (existing `tests/test_tags.py` still green; the schema change is additive).

- [ ] **Step 4: Commit**

```bash
git add main.py tests/conftest.py
git commit -m "feat: add power/toughness columns via schema migration v3"
```

---

## Task 2: Importer — extract power/toughness + idempotent re-runs

**Files:**
- Modify: `importer.py` (add `extract_pt` helper; update `import_cards`)
- Create: `tests/test_importer_idempotent.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_importer_idempotent.py`:

```python
import sqlite3
import importer


def _make_db(tmp_path):
    p = tmp_path / "imp.db"
    conn = sqlite3.connect(str(p))
    conn.executescript("""
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY,
            oracle_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            mana_cost TEXT,
            cmc REAL,
            type_line TEXT NOT NULL,
            oracle_text TEXT,
            colors TEXT,
            color_identity TEXT,
            image_uri TEXT,
            image_path TEXT,
            power TEXT,
            toughness TEXT
        );
        CREATE VIRTUAL TABLE cards_fts USING fts5(name, oracle_text);
    """)
    conn.commit()
    conn.close()
    return p


def _card(oracle_id, name, **extra):
    base = {
        "oracle_id": oracle_id, "name": name, "type_line": "Creature — Elf",
        "cmc": 1.0, "mana_cost": "{G}", "oracle_text": "Tap for mana.",
        "colors": ["G"], "color_identity": ["G"],
        "power": "1", "toughness": "1",
    }
    base.update(extra)
    return base


def test_extract_pt_top_level():
    assert importer.extract_pt({"power": "2", "toughness": "3"}) == ("2", "3")


def test_extract_pt_from_front_face():
    card = {"card_faces": [
        {"power": "4", "toughness": "5"},
        {"power": "0", "toughness": "0"},
    ]}
    assert importer.extract_pt(card) == ("4", "5")


def test_extract_pt_missing():
    assert importer.extract_pt({"type_line": "Instant"}) == (None, None)


def test_reimport_is_idempotent_and_backfills(tmp_path, monkeypatch):
    db = _make_db(tmp_path)
    monkeypatch.setattr(importer, "DB_PATH", db)

    # First import: a creature with no P/T recorded yet
    monkeypatch.setattr(importer, "get_bulk_download_url", lambda: "x")
    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([_card("elf-uuid", "Llanowar Elves", power=None, toughness=None)]),
    )
    importer.import_cards()

    # Second import: same card, now with P/T present
    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([_card("elf-uuid", "Llanowar Elves", power="1", toughness="1")]),
    )
    importer.import_cards()

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT power, toughness FROM cards WHERE oracle_id = 'elf-uuid'").fetchall()
    fts_count = conn.execute("SELECT COUNT(*) FROM cards_fts").fetchone()[0]
    conn.close()

    assert len(rows) == 1                      # no duplicate card row
    assert rows[0] == ("1", "1")               # power/toughness backfilled
    assert fts_count == 1                      # no duplicate FTS row on re-run
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `python -m pytest tests/test_importer_idempotent.py -q`
Expected: FAIL — `AttributeError: module 'importer' has no attribute 'extract_pt'` (and `_stream_cards`).

- [ ] **Step 3: Add the `extract_pt` helper**

In `importer.py`, after `extract_image_uri` (~line 47), add:

```python
def extract_pt(card):
    """Return (power, toughness) from the card or its front face, else (None, None)."""
    if card.get("power") is not None or card.get("toughness") is not None:
        return card.get("power"), card.get("toughness")
    for face in card.get("card_faces", []):
        if face.get("power") is not None or face.get("toughness") is not None:
            return face.get("power"), face.get("toughness")
    return None, None
```

- [ ] **Step 4: Extract the bulk stream into a helper**

In `importer.py`, replace the inline download/parse in `import_cards` with a reusable generator. Add this function above `import_cards`:

```python
def _stream_cards(download_url):
    """Yield card dicts from the streamed, gzip-decoded Scryfall bulk data."""
    response = requests.get(download_url, stream=True)
    response.raise_for_status()
    gzip_file = gzip.GzipFile(fileobj=response.raw)
    return ijson.items(gzip_file, "item")
```

- [ ] **Step 5: Rewrite `import_cards` to be idempotent and store P/T**

Replace the body of `import_cards` with:

```python
def import_cards():
    download_url = get_bulk_download_url()
    print("Downloading and streaming bulk data...")

    conn = get_connection()
    cur = conn.cursor()

    existing = {row[0] for row in cur.execute("SELECT oracle_id FROM cards")}
    seen_oracle_ids = set()
    batch = 0
    inserted = 0

    for card in _stream_cards(download_url):
        try:
            if card.get("layout") == "token":
                continue
            if card.get("digital"):
                continue

            oracle_id = card.get("oracle_id")
            if not oracle_id or oracle_id in seen_oracle_ids:
                continue
            seen_oracle_ids.add(oracle_id)

            power, toughness = extract_pt(card)
            values = (
                card.get("name"),
                card.get("mana_cost"),
                normalize_number(card.get("cmc")),
                card.get("type_line"),
                card.get("oracle_text"),
                sort_colors(card.get("colors")),
                sort_colors(card.get("color_identity")),
                extract_image_uri(card),
                power,
                toughness,
            )

            if oracle_id in existing:
                cur.execute("""
                    UPDATE cards SET
                        name = ?, mana_cost = ?, cmc = ?, type_line = ?,
                        oracle_text = ?, colors = ?, color_identity = ?,
                        image_uri = ?, power = ?, toughness = ?
                    WHERE oracle_id = ?
                """, (*values, oracle_id))
            else:
                cur.execute("""
                    INSERT INTO cards (
                        name, mana_cost, cmc, type_line, oracle_text,
                        colors, color_identity, image_uri, power, toughness, oracle_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (*values, oracle_id))
                cur.execute(
                    "INSERT INTO cards_fts (name, oracle_text) VALUES (?, ?)",
                    (card.get("name"), card.get("oracle_text")),
                )

            batch += 1
            inserted += 1
            if batch >= BATCH_SIZE:
                conn.commit()
                print(f"Processed {inserted} cards...")
                batch = 0
        except Exception as e:
            print("Skipping card, error:", e)
            continue

    conn.commit()
    print("Finished importing cards.")
    conn.close()
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/test_importer_idempotent.py -q`
Expected: PASS (all four tests).

- [ ] **Step 7: Commit**

```bash
git add importer.py tests/test_importer_idempotent.py
git commit -m "feat: import power/toughness; make importer idempotent for backfill"
```

> **Backfill note (manual, after merge):** run `python importer.py` once to re-stream bulk data and populate `power`/`toughness` on existing rows. P/T sort shows empty values until this is done.

---

## Task 3: API — expose power/toughness (and oracle_text on collection)

**Files:**
- Modify: `app.py:20-21` (`CARD_COLS`, `CARD_COLS_C`)
- Modify: `app.py:252-260` (`/api/collection` query)
- Create: `tests/test_cards_filter_sort.py` (first tests here; extended in Tasks 4–5)

- [ ] **Step 1: Write the failing test**

Create `tests/test_cards_filter_sort.py`:

```python
def test_collection_includes_oracle_text_and_pt(client, seed_cards):
    r = client.get("/api/collection")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["name"] == "Grizzly Bears")
    assert card["power"] == "2"
    assert card["toughness"] == "2"
    assert "oracle_text" in card


def test_deck_cards_include_pt(client, seed_cards):
    r = client.get("/api/decks/1/cards")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["name"] == "Grizzly Bears")
    assert card["power"] == "2"
    assert card["toughness"] == "2"
```

- [ ] **Step 2: Add the shared `seed_cards` fixture**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def seed_cards(db_path):
    conn = sqlite3.connect(str(db_path))
    rows = [
        # oracle_id, name, mana_cost, cmc, type_line, oracle_text, colors, ci, power, toughness
        ("bears", "Grizzly Bears", "{1}{G}", 2, "Creature — Bear", "", "G", "G", "2", "2"),
        ("ele", "Wise Elephant", "{4}{G}", 5, "Creature — Elephant", "Draw a card.", "G", "G", "3", "5"),
        ("isle", "Ancestral Vision", "{U}", 1, "Sorcery", "Draw three cards.", "U", "U", None, None),
        ("wall", "Steel Wall", "{1}", 1, "Artifact Creature — Wall", "Defender", "", "", "0", "4"),
        ("hydra", "Mystery Hydra", "{X}{G}", 1, "Creature — Hydra", "", "G", "G", "*", "*"),
    ]
    for oid, name, mc, cmc, tl, ot, col, ci, p, t in rows:
        conn.execute(
            "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, oracle_text, colors, color_identity, power, toughness) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (oid, name, mc, cmc, tl, ot, col, ci, p, t),
        )
    # add Grizzly Bears to collection + the existing test deck
    bears_id = conn.execute("SELECT id FROM cards WHERE oracle_id='bears'").fetchone()[0]
    conn.execute("INSERT INTO collection (card_id, quantity) VALUES (?, 2)", (bears_id,))
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (1, ?, 1)", (bears_id,))
    conn.commit()
    conn.close()
```

- [ ] **Step 3: Run to confirm failure**

Run: `python -m pytest tests/test_cards_filter_sort.py -q`
Expected: FAIL — `KeyError: 'power'` (collection/deck rows don't include the columns yet).

- [ ] **Step 4: Add columns to the shared column lists**

In `app.py`, change lines 20–21:

```python
CARD_COLS   = "id, oracle_id, name, mana_cost, cmc, type_line, oracle_text, colors, color_identity, image_uri, power, toughness"
CARD_COLS_C = "c.id, c.oracle_id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text, c.colors, c.color_identity, c.image_uri, c.power, c.toughness"
```

- [ ] **Step 5: Add oracle_text + P/T to the collection query**

In `app.py`, replace the `SELECT` in `get_collection` (lines ~252-260) with:

```python
        cur.execute("""
            SELECT c.id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text,
                   c.colors, c.color_identity, c.image_uri, c.power, c.toughness,
                   col.quantity
            FROM collection col
            JOIN cards c ON c.id = col.card_id
            WHERE col.quantity > 0
            ORDER BY c.name
        """)
```

- [ ] **Step 6: Run to verify pass**

Run: `python -m pytest tests/test_cards_filter_sort.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app.py tests/conftest.py tests/test_cards_filter_sort.py
git commit -m "feat: expose power/toughness on card/collection/deck payloads"
```

---

## Task 4: API — `/api/cards` filter params

**Files:**
- Modify: `app.py` (`search_cards`, lines ~154-186)
- Modify: `tests/test_cards_filter_sort.py` (add filter tests)

> **Note on the test DB:** `conftest._SCHEMA` does not create a `cards_fts` table, so when `q` is set the FTS branch raises `OperationalError` and the endpoint already falls back to the `LIKE` branch. Filter tests below pass `q=""` so they exercise the base (no-FTS) branch directly.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cards_filter_sort.py`:

```python
def _names(resp):
    return sorted(c["name"] for c in resp.json())


def test_filter_by_type(client, seed_cards):
    r = client.get("/api/cards", params={"types": "Sorcery"})
    assert _names(r) == ["Ancestral Vision"]


def test_filter_by_multiple_types_is_or(client, seed_cards):
    r = client.get("/api/cards", params={"types": "Sorcery,Artifact"})
    assert _names(r) == ["Ancestral Vision", "Steel Wall"]


def test_filter_by_cmc_range(client, seed_cards):
    r = client.get("/api/cards", params={"cmc_min": 2, "cmc_max": 5})
    assert _names(r) == ["Grizzly Bears", "Wise Elephant"]


def test_filter_by_text(client, seed_cards):
    r = client.get("/api/cards", params={"text": "draw"})
    assert _names(r) == ["Ancestral Vision", "Wise Elephant"]


def test_filter_by_colors_subset_includes_colorless(client, seed_cards):
    # Selecting G returns green cards AND colorless cards (subset semantics).
    r = client.get("/api/cards", params={"colors": "G"})
    assert _names(r) == ["Grizzly Bears", "Mystery Hydra", "Steel Wall", "Wise Elephant"]


def test_filter_colorless_only(client, seed_cards):
    r = client.get("/api/cards", params={"colorless": "1"})
    assert _names(r) == ["Steel Wall"]
```

- [ ] **Step 2: Run to confirm failure**

Run: `python -m pytest tests/test_cards_filter_sort.py -k filter -q`
Expected: FAIL — params are ignored, so result sets are wrong.

- [ ] **Step 3: Implement the filter params**

Replace the entire `search_cards` function in `app.py` with the version below. It builds shared WHERE clauses and applies them to both the FTS branch and the base branch:

```python
COLOR_LETTERS = ("W", "U", "B", "R", "G")


def _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text):
    """Return (sql_fragments, params) for the optional card filters."""
    frags, params = [], []

    if colorless:
        frags.append("color_identity = ''")
    elif colors:
        wanted = [c for c in colors.upper().split(",") if c in COLOR_LETTERS]
        if wanted:
            # subset: stripping every selected letter leaves nothing (colorless '' passes)
            expr = "color_identity"
            for letter in wanted:
                expr = f"REPLACE({expr}, '{letter}', '')"
            frags.append(f"{expr} = ''")

    type_list = [t.strip() for t in types.split(",") if t.strip()] if types else []
    if type_list:
        ors = " OR ".join(["type_line LIKE ?"] * len(type_list))
        frags.append(f"({ors})")
        params.extend(f"%{t}%" for t in type_list)

    if cmc_min is not None:
        frags.append("cmc >= ?")
        params.append(cmc_min)
    if cmc_max is not None:
        frags.append("cmc <= ?")
        params.append(cmc_max)

    if text and text.strip():
        frags.append("oracle_text LIKE ?")
        params.append(f"%{text.strip()}%")

    return frags, params


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
    text: str = Query(""),
):
    frags, fparams = _build_card_filters(colors, colorless, types, cmc_min, cmc_max, text)
    where_extra = ("".join(f" AND {f}" for f in frags))

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
                      {where_extra.replace("color_identity", "c.color_identity").replace("type_line", "c.type_line").replace("cmc", "c.cmc").replace("oracle_text", "c.oracle_text")}
                    ORDER BY rank
                    LIMIT ? OFFSET ?
                """, (q.strip() + "*", *fparams, limit, offset))
            except sqlite3.OperationalError:
                cur.execute(f"""
                    SELECT {CARD_COLS}
                    FROM cards
                    WHERE name LIKE ?
                      AND type_line NOT LIKE 'Token%'
                      {where_extra}
                    ORDER BY name
                    LIMIT ? OFFSET ?
                """, (f"%{q.strip()}%", *fparams, limit, offset))
        else:
            cur.execute(f"""
                SELECT {CARD_COLS}
                FROM cards
                WHERE type_line NOT LIKE 'Token%'
                  {where_extra}
                ORDER BY name
                LIMIT ? OFFSET ?
            """, (*fparams, limit, offset))
        return [dict(r) for r in cur.fetchall()]
```

> The `.replace(...)` chain on the FTS branch qualifies the bare column names with the `c.` alias used in that join. Keeps `_build_card_filters` alias-free and reusable.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_cards_filter_sort.py -k filter -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (existing tests unaffected).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_cards_filter_sort.py
git commit -m "feat: add color/type/cmc/text filters to /api/cards"
```

---

## Task 5: API — `/api/cards` sort params

**Files:**
- Modify: `app.py` (`search_cards` — add `sort`/`dir`, replace the `ORDER BY` clauses)
- Modify: `tests/test_cards_filter_sort.py` (add sort tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cards_filter_sort.py`:

```python
def _ordered(resp):
    return [c["name"] for c in resp.json()]


def test_sort_by_cmc_asc(client, seed_cards):
    r = client.get("/api/cards", params={"sort": "cmc", "dir": "asc"})
    cmcs = [c["cmc"] for c in r.json()]
    assert cmcs == sorted(cmcs)


def test_sort_by_cmc_desc(client, seed_cards):
    r = client.get("/api/cards", params={"sort": "cmc", "dir": "desc"})
    cmcs = [c["cmc"] for c in r.json()]
    assert cmcs == sorted(cmcs, reverse=True)


def test_sort_by_power_puts_nonnumeric_and_missing_last(client, seed_cards):
    # power values: Steel Wall 0, Grizzly Bears 2, Wise Elephant 3,
    # Mystery Hydra '*' (non-numeric -> last), Ancestral Vision NULL (-> last)
    r = client.get("/api/cards", params={"sort": "power", "dir": "asc"})
    names = _ordered(r)
    assert names[:3] == ["Steel Wall", "Grizzly Bears", "Wise Elephant"]
    assert set(names[3:]) == {"Mystery Hydra", "Ancestral Vision"}
```

- [ ] **Step 2: Run to confirm failure**

Run: `python -m pytest tests/test_cards_filter_sort.py -k sort -q`
Expected: FAIL — results are still name-ordered.

- [ ] **Step 3: Implement the sort helper**

In `app.py`, add above `search_cards`:

```python
_TYPE_RANK_SQL = """CASE
    WHEN {col} LIKE '%Creature%'     THEN 0
    WHEN {col} LIKE '%Instant%'      THEN 1
    WHEN {col} LIKE '%Sorcery%'      THEN 2
    WHEN {col} LIKE '%Enchantment%'  THEN 3
    WHEN {col} LIKE '%Artifact%'     THEN 4
    WHEN {col} LIKE '%Planeswalker%' THEN 5
    WHEN {col} LIKE '%Land%'         THEN 6
    ELSE 7 END"""


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
```

- [ ] **Step 4: Wire `sort`/`dir` into `search_cards`**

Add the two params to the signature:

```python
    sort: str = Query("name"),
    dir: str = Query("asc"),
```

Then replace the three `ORDER BY` clauses:
- FTS branch: change `ORDER BY rank` to `ORDER BY {_order_by(sort, dir, "c.")}` **only when `sort != "name"`**; keep `ORDER BY rank` when `sort == "name"` (preserve relevance ranking for text search). Implement as:

```python
                fts_order = "rank" if sort == "name" else _order_by(sort, dir, "c.")
```
and use `ORDER BY {fts_order}` in that query.

- Base `LIKE` branch and the `else` branch: change `ORDER BY name` to `ORDER BY {_order_by(sort, dir)}`.

- [ ] **Step 5: Run to verify pass**

Run: `python -m pytest tests/test_cards_filter_sort.py -k sort -q`
Expected: PASS.

- [ ] **Step 6: Run full suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_cards_filter_sort.py
git commit -m "feat: add sort/dir (incl. power/toughness) to /api/cards"
```

---

## Task 6: Frontend — shared filter/sort module (model, comparator, filters, controls)

**Files:**
- Modify: `static/app.js` (add a new "Filter/Sort module" section near the top, after the `state` block ~line 160)
- Modify: `static/style.css` (filter bar + panel styles)

> No JS test harness exists. `makeFilterModel`, `sortComparator`, and `applyFilters` are written as pure functions and verified with a browser-console snippet in Step 4. UI behavior is verified in later tasks.

- [ ] **Step 1: Add the pure model/comparator/filter functions**

In `static/app.js`, add this section after the global `state` / `LIMIT` block:

```javascript
// ── Filter / Sort module ───────────────────────────────────────────────────────

const COLOR_LETTERS = ['W', 'U', 'B', 'R', 'G'];
const TYPE_OPTIONS = ['Creature', 'Instant', 'Sorcery', 'Enchantment',
                      'Artifact', 'Planeswalker', 'Land', 'Battle'];
const SORT_OPTIONS_BASE = [
  { value: 'name', label: 'Name' },
  { value: 'cmc',  label: 'Mana value' },
  { value: 'type', label: 'Type' },
  { value: 'power', label: 'Power' },
  { value: 'toughness', label: 'Toughness' },
];
const SORT_OPTION_QUANTITY = { value: 'quantity', label: 'Quantity' };

function makeFilterModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false,
    types: new Set(), cmcMin: null, cmcMax: null, tags: new Set(),
    sort: 'name', dir: 'asc', ...overrides,
  };
}

function typeRank(typeLine) {
  const tl = typeLine || '';
  const i = TYPE_OPTIONS.findIndex(t => tl.includes(t));
  return i === -1 ? TYPE_OPTIONS.length : i;
}

function ptNum(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) && /^[0-9]/.test(String(v)) ? n : null;
}

function sortComparator(model) {
  const dir = model.dir === 'desc' ? -1 : 1;
  const byName = (a, b) => a.name.localeCompare(b.name);
  return (a, b) => {
    let r;
    switch (model.sort) {
      case 'cmc':      r = (a.cmc ?? 0) - (b.cmc ?? 0); break;
      case 'quantity': r = (a.quantity ?? 0) - (b.quantity ?? 0); break;
      case 'type':     r = typeRank(a.type_line) - typeRank(b.type_line); break;
      case 'power':
      case 'toughness': {
        const av = ptNum(a[model.sort]), bv = ptNum(b[model.sort]);
        if (av === null && bv === null) return byName(a, b);
        if (av === null) return 1;    // missing/non-numeric always last
        if (bv === null) return -1;
        r = av - bv;
        break;
      }
      default: return byName(a, b) * dir;   // name
    }
    return r !== 0 ? r * dir : byName(a, b);
  };
}

function applyFilters(cards, model) {
  return cards.filter(c => {
    if (model.text) {
      const t = model.text.toLowerCase();
      if (!c.name.toLowerCase().includes(t) &&
          !(c.oracle_text || '').toLowerCase().includes(t)) return false;
    }
    if (model.colorlessOnly) {
      if ((c.color_identity || '') !== '') return false;
    } else if (model.colors.size) {
      for (const ch of (c.color_identity || '')) {
        if (!model.colors.has(ch)) return false;   // subset; '' passes
      }
    }
    if (model.types.size) {
      const tl = c.type_line || '';
      if (![...model.types].some(ty => tl.includes(ty))) return false;
    }
    if (model.cmcMin != null && (c.cmc ?? 0) < model.cmcMin) return false;
    if (model.cmcMax != null && (c.cmc ?? 0) > model.cmcMax) return false;
    if (model.tags.size) {
      const tags = [...(c.collection_tags || []), ...(c.deck_tags || [])];
      if (![...model.tags].some(tg => tags.includes(tg))) return false;
    }
    return true;
  });
}

function activeFilterCount(model) {
  let n = 0;
  if (model.text) n++;
  if (model.colorlessOnly || model.colors.size) n++;
  if (model.types.size) n++;
  if (model.cmcMin != null || model.cmcMax != null) n++;
  if (model.tags.size) n++;
  return n;
}

function modelToParams(model) {
  const p = {};
  if (model.text) p.text = model.text;
  if (model.colorlessOnly) p.colorless = '1';
  else if (model.colors.size) p.colors = [...model.colors].join(',');
  if (model.types.size) p.types = [...model.types].join(',');
  if (model.cmcMin != null) p.cmc_min = model.cmcMin;
  if (model.cmcMax != null) p.cmc_max = model.cmcMax;
  if (model.sort) p.sort = model.sort;
  if (model.dir) p.dir = model.dir;
  return p;
}
```

- [ ] **Step 2: Add the control-bar builder**

Append to the same section:

```javascript
/**
 * Render a filter/sort control bar into `container`.
 * config: { model, facets:Set<'colors'|'types'|'cmc'|'tags'|'text'>,
 *           sortOptions:[{value,label}], tagOptions:[], onChange:fn }
 */
function buildFilterControls(container, config) {
  const { model, facets, sortOptions, tagOptions = [], onChange } = config;
  container.innerHTML = '';
  container.className = 'filter-bar';

  // Sort select + direction toggle
  const sortSel = document.createElement('select');
  sortSel.className = 'sort-select';
  for (const opt of sortOptions) {
    const o = document.createElement('option');
    o.value = opt.value; o.textContent = `Sort: ${opt.label}`;
    if (opt.value === model.sort) o.selected = true;
    sortSel.appendChild(o);
  }
  sortSel.addEventListener('change', () => { model.sort = sortSel.value; onChange(); });

  const dirBtn = document.createElement('button');
  dirBtn.className = 'dir-btn action-btn';
  dirBtn.textContent = model.dir === 'desc' ? '↓' : '↑';
  dirBtn.title = 'Toggle sort direction';
  dirBtn.addEventListener('click', () => {
    model.dir = model.dir === 'desc' ? 'asc' : 'desc';
    dirBtn.textContent = model.dir === 'desc' ? '↓' : '↑';
    onChange();
  });

  // Filters disclosure
  const filterBtn = document.createElement('button');
  filterBtn.className = 'filters-btn action-btn';
  const badge = document.createElement('span');
  badge.className = 'filter-badge';
  const refreshBadge = () => {
    const n = activeFilterCount(model);
    badge.textContent = n ? String(n) : '';
    badge.classList.toggle('hidden', n === 0);
  };
  filterBtn.textContent = 'Filters ';
  filterBtn.appendChild(badge);

  const panel = document.createElement('div');
  panel.className = 'filter-panel hidden';
  filterBtn.addEventListener('click', () => panel.classList.toggle('hidden'));

  // Colors
  if (facets.has('colors')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Colors</span>';
    for (const letter of COLOR_LETTERS) {
      const b = document.createElement('button');
      b.className = 'color-btn color-' + letter +
        (model.colors.has(letter) ? ' active' : '');
      b.textContent = letter;
      b.addEventListener('click', () => {
        if (model.colors.has(letter)) model.colors.delete(letter);
        else { model.colors.add(letter); model.colorlessOnly = false; }
        b.classList.toggle('active');
        clBtn.classList.toggle('active', model.colorlessOnly);
        refreshBadge(); onChange();
      });
      grp.appendChild(b);
    }
    const clBtn = document.createElement('button');
    clBtn.className = 'color-btn color-C' + (model.colorlessOnly ? ' active' : '');
    clBtn.textContent = 'C';
    clBtn.title = 'Colorless only';
    clBtn.addEventListener('click', () => {
      model.colorlessOnly = !model.colorlessOnly;
      if (model.colorlessOnly) model.colors.clear();
      grp.querySelectorAll('.color-btn').forEach(x =>
        x.classList.toggle('active',
          x === clBtn ? model.colorlessOnly : model.colors.has(x.textContent)));
      refreshBadge(); onChange();
    });
    grp.appendChild(clBtn);
    panel.appendChild(grp);
  }

  // Types
  if (facets.has('types')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Types</span>';
    for (const ty of TYPE_OPTIONS) {
      const lab = document.createElement('label');
      lab.className = 'check-pill';
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = model.types.has(ty);
      cb.addEventListener('change', () => {
        if (cb.checked) model.types.add(ty); else model.types.delete(ty);
        refreshBadge(); onChange();
      });
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(ty));
      grp.appendChild(lab);
    }
    panel.appendChild(grp);
  }

  // CMC range
  if (facets.has('cmc')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Mana value</span>';
    const mk = (key, ph) => {
      const inp = document.createElement('input');
      inp.type = 'number'; inp.min = '0'; inp.className = 'cmc-input';
      inp.placeholder = ph;
      if (model[key] != null) inp.value = model[key];
      inp.addEventListener('input', () => {
        model[key] = inp.value === '' ? null : parseFloat(inp.value);
        refreshBadge(); onChange();
      });
      return inp;
    };
    grp.appendChild(mk('cmcMin', 'min'));
    grp.appendChild(document.createTextNode('–'));
    grp.appendChild(mk('cmcMax', 'max'));
    panel.appendChild(grp);
  }

  // Tags
  if (facets.has('tags') && tagOptions.length) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Tags</span>';
    for (const tag of tagOptions) {
      const lab = document.createElement('label');
      lab.className = 'check-pill';
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = model.tags.has(tag);
      cb.addEventListener('change', () => {
        if (cb.checked) model.tags.add(tag); else model.tags.delete(tag);
        refreshBadge(); onChange();
      });
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(tag));
      grp.appendChild(lab);
    }
    panel.appendChild(grp);
  }

  // Clear
  const clearBtn = document.createElement('button');
  clearBtn.className = 'clear-filters-btn action-btn';
  clearBtn.textContent = 'Clear';
  clearBtn.addEventListener('click', () => {
    const keepText = model.text;
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText }));
    buildFilterControls(container, config);  // re-render to reset control state
    onChange();
  });
  panel.appendChild(clearBtn);

  refreshBadge();
  container.appendChild(sortSel);
  container.appendChild(dirBtn);
  container.appendChild(filterBtn);
  container.appendChild(panel);
}
```

- [ ] **Step 3: Add styles**

Append to `static/style.css`:

```css
.filter-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; position: relative; }
.sort-select { padding: 4px 6px; }
.dir-btn, .filters-btn, .clear-filters-btn { padding: 4px 8px; }
.filter-badge { display: inline-block; min-width: 16px; padding: 0 4px; border-radius: 8px;
  background: #c33; color: #fff; font-size: 11px; text-align: center; }
.filter-badge.hidden { display: none; }
.filter-panel { position: absolute; top: 110%; left: 0; z-index: 20;
  background: #1e1e24; border: 1px solid #444; border-radius: 6px; padding: 12px;
  display: flex; flex-direction: column; gap: 10px; min-width: 280px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4); }
.filter-panel.hidden { display: none; }
.filter-group { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.filter-group-label { font-size: 12px; opacity: 0.7; width: 80px; }
.color-btn { width: 26px; height: 26px; border-radius: 50%; border: 1px solid #555;
  background: #2a2a32; color: #ddd; cursor: pointer; }
.color-btn.active { outline: 2px solid #6cf; }
.check-pill { display: inline-flex; align-items: center; gap: 4px; font-size: 12px;
  padding: 2px 6px; border: 1px solid #444; border-radius: 12px; cursor: pointer; }
.cmc-input { width: 50px; padding: 3px; }
```

- [ ] **Step 4: Verify the pure functions in the browser console**

Start the app: `uvicorn app:app --reload`, open `http://localhost:8000`, open DevTools console, paste:

```javascript
const m = makeFilterModel({ sort: 'power', dir: 'asc' });
const cards = [
  { name: 'A', power: '2', cmc: 2, type_line: 'Creature', color_identity: 'G' },
  { name: 'B', power: '*', cmc: 1, type_line: 'Creature', color_identity: 'G' },
  { name: 'C', power: '0', cmc: 1, type_line: 'Creature', color_identity: '' },
];
console.log(cards.slice().sort(sortComparator(m)).map(c => c.name)); // ["C","A","B"]
m.colors = new Set(['G']);
console.log(applyFilters(cards, m).map(c => c.name)); // ["A","B","C"] (colorless passes subset)
m.colorlessOnly = true; m.colors = new Set();
console.log(applyFilters(cards, m).map(c => c.name)); // ["C"]
```
Expected: the three logged arrays match the inline comments.

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: shared filter/sort module (model, comparator, controls)"
```

---

## Task 7: Wire the Cards page (server-side filter/sort)

**Files:**
- Modify: `static/index.html:18-30` (add a control container in the browser view)
- Modify: `static/app.js` — `API.searchCards` (line 4), `state` (line 150), `onSearchInput`/`loadCards` (lines 300-321), `init` (line 794)

- [ ] **Step 1: Add the control container to the Cards view**

In `static/index.html`, inside `#view-browser .search-bar`, after the `<input id="search-input">` (line 28-ish, before `</div>`), add:

```html
        <div id="browser-filter-controls"></div>
```

- [ ] **Step 2: Extend `API.searchCards` to pass extra params**

In `static/app.js`, replace the `searchCards` method (lines 4-9):

```javascript
  async searchCards(q = '', limit = 40, offset = 0, extra = {}) {
    const p = new URLSearchParams({ q, limit, offset, ...extra });
    const r = await fetch(`/api/cards?${p}`);
    if (!r.ok) throw new Error('Search failed');
    return r.json();
  },
```

- [ ] **Step 3: Add a filter model to the Cards `state`**

In `static/app.js`, add to the `state` object (after `modalCard: null,`):

```javascript
  filter:     null,   // filter/sort model, initialized in init()
```

- [ ] **Step 4: Pass params from `loadCards`; reset on filter change**

In `loadCards` (line 321), change the fetch call to include params:

```javascript
    const cards = await API.searchCards(state.query, LIMIT, state.offset, modelToParams(state.filter));
```

Add a reload helper near `onSearchInput`:

```javascript
function reloadCards() {
  state.offset = 0;
  state.hasMore = true;
  state.cards = [];
  clearGrid();
  loadCards();
}
```

In `onSearchInput`, set `state.filter.text` alongside `state.query` so the badge reflects it (optional but consistent):

```javascript
    state.query = q;
    state.filter.text = q;
    reloadCards();
```
(Replace the existing `state.offset/hasMore/cards/clearGrid/loadCards` lines with `reloadCards()`.)

- [ ] **Step 5: Initialize the controls in `init`**

In `init()` (line 794), after the existing setup, add:

```javascript
  state.filter = makeFilterModel();
  buildFilterControls(document.getElementById('browser-filter-controls'), {
    model: state.filter,
    facets: new Set(['colors', 'types', 'cmc']),
    sortOptions: SORT_OPTIONS_BASE,
    onChange: reloadCards,
  });
```

- [ ] **Step 6: Manual verification**

Run `uvicorn app:app --reload`, open the Cards page:
- Choose **Sort: Mana value**, toggle direction → grid reorders.
- Open **Filters**, pick type **Creature** → only creatures show; the badge shows `1`.
- Set mana value `min 3` → results update; scrolling still loads more matching cards.
- **Clear** → filters reset, full results return.

Expected: all behaviors as described; network tab shows `/api/cards?...&types=Creature&sort=cmc...`.

- [ ] **Step 7: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: wire filter/sort controls into Cards page"
```

---

## Task 8: Wire the Collection page (client-side filter/sort within groups)

**Files:**
- Modify: `static/index.html:32-49` (add control container in collection view)
- Modify: `static/app.js` — `collectionState` (line 815), `renderCollectionGrid` (line 899), `loadCollectionView` (line 886), collection-search handler (line 933)

- [ ] **Step 1: Add the control container**

In `static/index.html`, inside `#view-collection .search-bar`, after the `#collection-group-by` select, add:

```html
        <div id="collection-filter-controls"></div>
```

- [ ] **Step 2: Add a filter model to `collectionState`**

In `static/app.js`, change the `collectionState` object to include:

```javascript
const collectionState = {
  cards: [],
  query: '',
  groupBy: 'none',
  filter: makeFilterModel(),
};
```

- [ ] **Step 3: Apply filters + sort (within groups) in `renderCollectionGrid`**

Replace the body of `renderCollectionGrid` (lines 899-931) with:

```javascript
function renderCollectionGrid() {
  const grid = document.getElementById('collection-grid');
  const countEl = document.getElementById('collection-count');
  grid.innerHTML = '';

  collectionState.filter.text = collectionState.query;   // name/text box feeds model
  const filtered = applyFilters(collectionState.cards, collectionState.filter);
  const cmp = sortComparator(collectionState.filter);

  const totalCopies = filtered.reduce((s, c) => s + c.quantity, 0);
  countEl.textContent = filtered.length
    ? `${totalCopies} card${totalCopies !== 1 ? 's' : ''} · ${filtered.length} unique`
    : '';

  if (!filtered.length) {
    const msg = document.createElement('div');
    msg.className = 'grid-message';
    msg.textContent = collectionState.query ? 'No matches.' : 'No cards in collection yet.';
    grid.appendChild(msg);
    return;
  }

  if (collectionState.groupBy !== 'none') {
    const groups = groupCards(filtered, 'collection_tags');
    for (const g of groups) g.cards.sort(cmp);
    renderGroupedGrid(grid, groups, buildCardTile, collectionGroupCollapsed);
  } else {
    const frag = document.createDocumentFragment();
    for (const card of [...filtered].sort(cmp)) frag.appendChild(buildCardTile(card));
    grid.appendChild(frag);
  }
}
```

- [ ] **Step 4: Build the controls when the collection loads**

In `loadCollectionView` (line 886), after `collectionState.cards = rows;` and before `renderCollectionGrid();`, add:

```javascript
    const tagOptions = await API.listCollectionTags();
    buildFilterControls(document.getElementById('collection-filter-controls'), {
      model: collectionState.filter,
      facets: new Set(['colors', 'types', 'cmc', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions,
      onChange: renderCollectionGrid,
    });
```

- [ ] **Step 5: Manual verification**

Run the app, open Collection (import a few cards first if empty):
- **Sort: Quantity ↓** → highest-count cards first.
- Set **Group: Tag** then **Sort: Mana value** → within each tag group, cards are CMC-ordered; group headers/order unchanged.
- Open **Filters**, pick a color → list narrows; the name box still filters by substring.
- **Clear** resets filters (name box value is preserved).

Expected: sorting applies within groups; filters compose with the name box.

- [ ] **Step 6: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: wire filter/sort controls into Collection page"
```

---

## Task 9: Wire the Decks page (deck-contents filter/sort)

**Files:**
- Modify: `static/index.html:71-80` (add control container in deck editor header)
- Modify: `static/app.js` — `deckState` (line 1109), `renderDeckGrid` (line 1190), `renderDeckText` (line 1246), deck load (`openDeck`/`renderDeckContent` path), and the group-by handler (line 1462)

- [ ] **Step 1: Add the control container to the deck editor header**

In `static/index.html`, inside `.deck-editor-acts` (after the `#deck-group-by` select, ~line 75), add:

```html
                <div id="deck-filter-controls"></div>
```

- [ ] **Step 2: Add a filter model to `deckState`**

In `static/app.js`, add to `deckState`:

```javascript
  filter:         makeFilterModel(),
```

- [ ] **Step 3: Apply filters + sort within `renderDeckGrid`**

Replace the body of `renderDeckGrid` (lines 1190-1211) with:

```javascript
function renderDeckGrid() {
  const el = document.getElementById('deck-grid-view');
  el.innerHTML = '';
  const filtered = applyFilters(deckState.deckCards, deckState.filter);
  if (!filtered.length) {
    el.innerHTML = '<div class="deck-empty-msg">No cards match — adjust filters or search to add some.</div>';
    return;
  }
  const cmp = sortComparator(deckState.filter);
  if (deckState.groupBy !== 'none') {
    const tagField = deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags';
    const groups = groupCards(filtered, tagField);
    for (const g of groups) g.cards.sort(cmp);
    renderGroupedGrid(el, groups, buildDeckCardTile, deckGroupCollapsed);
  } else {
    const sorted = [...filtered].sort((a, b) => {
      if (a.is_commander && !b.is_commander) return -1;   // commander pinned first
      if (!a.is_commander && b.is_commander) return 1;
      return cmp(a, b);
    });
    const frag = document.createDocumentFragment();
    for (const card of sorted) frag.appendChild(buildDeckCardTile(card));
    el.appendChild(frag);
  }
}
```

- [ ] **Step 4: Honor the filter in the text view**

In `renderDeckText` (line 1246), change the loop source from `deckState.deckCards` to the filtered set. Replace the line `for (const card of deckState.deckCards) {` with:

```javascript
  for (const card of applyFilters(deckState.deckCards, deckState.filter)) {
```

(Leave the empty-state check using `deckState.deckCards.length` so an all-filtered-out deck still shows "No cards yet" only when truly empty; the per-section loop simply produces empty sections that are skipped by the existing `if (!cards.length) continue;`.)

- [ ] **Step 5: Build deck controls when a deck opens**

Find the function that loads a deck's cards (where `deckState.deckCards` is assigned, near `renderDeckContent` callers). After `deckState.deckCards = ...;` and before the render call, add:

```javascript
    const collTags = await API.listCollectionTags();
    const deckTags = await API.listDeckTags(deckState.currentDeckId);
    buildFilterControls(document.getElementById('deck-filter-controls'), {
      model: deckState.filter,
      facets: new Set(['colors', 'types', 'cmc', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions: [...new Set([...collTags, ...deckTags])].sort(),
      onChange: renderDeckContent,
    });
```

> Locate the exact assignment with: `grep -n "deckState.deckCards =" static/app.js`. Add the snippet immediately after it, inside that `async` function.

- [ ] **Step 6: Reset the deck filter when switching decks**

In the same deck-open function, before reassigning `deckState.deckCards`, reset the model so filters don't leak between decks:

```javascript
    deckState.filter = makeFilterModel();
```

- [ ] **Step 7: Manual verification**

Run the app, open a deck with several cards:
- **Sort: Mana value** → grid orders by CMC; a commander (if set) stays pinned at the top.
- **Group: Collection tag** + **Sort: Type** → cards ordered by type within each tag group.
- Open **Filters**, pick **Creature** → only creatures show in both grid and text views.
- Switch to another deck → filters are reset.

Expected: commander pinning holds in flat view; filters/sort apply in both grid and text views.

- [ ] **Step 8: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: wire filter/sort controls into Decks page"
```

---

## Task 10: Cross-page polish — Esc/`/` keys, panel close-on-outside-click

**Files:**
- Modify: `static/app.js` (the filter module — outside-click handler; the global keydown handler ~line 675)

- [ ] **Step 1: Close the filter panel on outside click**

In `buildFilterControls`, after `container.appendChild(panel);`, add:

```javascript
  document.addEventListener('click', (e) => {
    if (!container.contains(e.target)) panel.classList.add('hidden');
  });
```

- [ ] **Step 2: Esc closes any open filter panel**

In the global `document.addEventListener('keydown', ...)` handler (line 675), at the top of the handler add:

```javascript
  if (e.key === 'Escape') {
    const open = document.querySelector('.filter-panel:not(.hidden)');
    if (open) { open.classList.add('hidden'); return; }
  }
```

(Place it before the existing modal-close logic so an open panel takes priority; if no panel is open it falls through unchanged.)

- [ ] **Step 3: Manual verification**

Run the app:
- Open a Filters panel, click elsewhere → panel closes.
- Open a Filters panel, press **Esc** → panel closes (and does not also close the modal).
- `/` still focuses the active page's search box.

Expected: all three behaviors hold on all three pages.

- [ ] **Step 4: Run the full backend suite one more time**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: filter panel Esc/outside-click handling"
```

---

## Final verification checklist

- [ ] `python -m pytest -q` is green.
- [ ] `python importer.py` has been run once to backfill power/toughness (manual; required for P/T sort to show data).
- [ ] Cards page: server-side color/type/cmc filters + name/cmc/type/power/toughness sort, with infinite scroll intact.
- [ ] Collection page: color/type/cmc/tags filters + sort incl. quantity; sort applies within tag groups.
- [ ] Decks page: same filters/sort in grid and text views; commander pinned in flat grid view; filters reset between decks.
- [ ] Filter panel: badge count, Clear, Esc, and outside-click all work.
