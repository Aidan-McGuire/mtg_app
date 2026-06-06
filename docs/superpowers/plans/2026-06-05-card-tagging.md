# Card Tagging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two-tier free-form card tagging — collection-scoped tags (persist across decks) and deck-scoped tags (per card per deck) — with tag chips on tiles, inline editing in the detail modal, and group-by-tag in collection and deck grid views.

**Architecture:** Two new SQLite tables (`collection_tags`, `deck_card_tags`) added via migration in `main.py`. Tags are returned alongside existing card list responses; six mutation endpoints handle add/remove; two autocomplete endpoints return all tags in use. Frontend renders tag chips on tiles, an async tag editor in the modal, and a group-by dropdown in collection and deck views.

**Tech Stack:** Python 3.11+, FastAPI, SQLite (stdlib sqlite3), pytest + httpx TestClient, vanilla JS (ES2020), no build step.

---

## File Map

| File | Change |
|------|--------|
| `main.py` | Add `migrate_database()` for v2 schema |
| `app.py` | Add 8 new endpoints; modify `get_collection`, `get_deck_cards`, `remove_card_from_deck`, `decrement_collection` |
| `static/index.html` | Add group-by selects to collection toolbar and deck editor header |
| `static/style.css` | Add tag chip, tag input, group section styles |
| `static/app.js` | Tag chips on tiles, modal tag editor, group-by rendering |
| `tests/conftest.py` | Create: pytest fixtures with in-memory test DB |
| `tests/test_tags.py` | Create: backend tag endpoint tests |

---

## Task 1: Schema migration

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add `migrate_database()` to `main.py`**

Add after `initialize_database()`:

```python
def migrate_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT version FROM schema_version LIMIT 1;")
    version = cur.fetchone()[0]

    if version < 2:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS collection_tags (
                id      INTEGER PRIMARY KEY,
                card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                tag     TEXT    NOT NULL,
                UNIQUE(card_id, tag)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deck_card_tags (
                id      INTEGER PRIMARY KEY,
                deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id INTEGER NOT NULL REFERENCES cards(id),
                tag     TEXT    NOT NULL,
                UNIQUE(deck_id, card_id, tag)
            );
        """)
        cur.execute("UPDATE schema_version SET version = 2;")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_database()
    migrate_database()
    print("Migration complete.")
```

- [ ] **Step 2: Call `migrate_database()` at app startup in `app.py`**

Add near the top of `app.py`, after `IMAGE_CACHE_DIR.mkdir(exist_ok=True)`:

```python
from main import migrate_database
migrate_database()
```

- [ ] **Step 3: Run migration manually and verify tables exist**

```bash
python main.py
sqlite3 mtg.db ".tables"
```

Expected output includes `collection_tags` and `deck_card_tags`.

- [ ] **Step 4: Commit**

```bash
git add main.py app.py
git commit -m "feat: add collection_tags and deck_card_tags schema (v2 migration)"
```

---

## Task 2: Test infrastructure

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_tags.py`

- [ ] **Step 1: Install pytest and httpx if not present**

```bash
pip install pytest httpx
```

- [ ] **Step 2: Create `tests/__init__.py`**

```python
```
(empty file)

- [ ] **Step 3: Create `tests/conftest.py`**

```python
import pytest
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient

_SCHEMA = """
CREATE TABLE schema_version (version INTEGER NOT NULL);
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
    image_path TEXT
);
CREATE TABLE collection (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL UNIQUE REFERENCES cards(id),
    quantity INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE decks (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE deck_cards (
    id INTEGER PRIMARY KEY,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    is_commander INTEGER NOT NULL DEFAULT 0,
    UNIQUE(deck_id, card_id)
);
CREATE TABLE collection_tags (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    UNIQUE(card_id, tag)
);
CREATE TABLE deck_card_tags (
    id INTEGER PRIMARY KEY,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    tag TEXT NOT NULL,
    UNIQUE(deck_id, card_id, tag)
);
INSERT INTO schema_version VALUES (2);
INSERT INTO cards (id, oracle_id, name, type_line) VALUES (1, 'bolt-uuid', 'Lightning Bolt', 'Instant');
INSERT INTO cards (id, oracle_id, name, type_line) VALUES (2, 'forest-uuid', 'Forest', 'Basic Land');
INSERT INTO collection (card_id, quantity) VALUES (1, 4);
INSERT INTO decks (id, name) VALUES (1, 'Test Deck');
INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (1, 1, 4);
"""


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in _SCHEMA.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def client(db_path, monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    # Suppress static file mount errors in test environment
    with TestClient(app_module.app, raise_server_exceptions=True) as c:
        yield c
```

- [ ] **Step 4: Create `tests/test_tags.py` with a smoke test**

```python
def test_collection_returns_collection_tags_field(client):
    r = client.get("/api/collection")
    assert r.status_code == 200
    cards = r.json()
    assert len(cards) == 1
    assert "collection_tags" in cards[0]
    assert cards[0]["collection_tags"] == []
```

- [ ] **Step 5: Run test — expect FAIL (field not yet added)**

```bash
cd /Users/mcg/projects/mtg_app
pytest tests/test_tags.py -v
```

Expected: `FAILED tests/test_tags.py::test_collection_returns_collection_tags_field`

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: add tag test infrastructure and initial failing test"
```

---

## Task 3: Tags in list responses + read/autocomplete endpoints

**Files:**
- Modify: `app.py`
- Modify: `tests/test_tags.py`

- [ ] **Step 1: Add tag helper functions to `app.py`**

Add after the `CARD_COLS` constants:

```python
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
```

- [ ] **Step 2: Modify `get_collection` to include `collection_tags`**

Replace the existing `get_collection` function body:

```python
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
```

- [ ] **Step 3: Modify `get_deck_cards` to include both tag types**

Replace the existing `get_deck_cards` function body:

```python
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
```

- [ ] **Step 4: Add read endpoints for a single card's tags**

Add these two endpoints before the `# Static files` section. Define them BEFORE the `{card_id}` routes to avoid routing conflicts:

```python
@app.get("/api/collection/{card_id}/tags")
def get_collection_card_tags(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        return fetch_collection_tags(cur, card_id)


@app.get("/api/decks/{deck_id}/cards/{card_id}/tags")
def get_deck_card_tags(deck_id: int, card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        return fetch_deck_tags(cur, deck_id, card_id)
```

- [ ] **Step 5: Add autocomplete endpoints**

```python
@app.get("/api/collection/tags")
def list_collection_tags():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT tag FROM collection_tags ORDER BY tag")
        return [r[0] for r in cur.fetchall()]


@app.get("/api/decks/{deck_id}/tags")
def list_deck_tags(deck_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT tag FROM deck_card_tags WHERE deck_id = ? ORDER BY tag",
            (deck_id,)
        )
        return [r[0] for r in cur.fetchall()]
```

**Important:** In `app.py`, `GET /api/collection/tags` (literal) must be defined **before** any `GET /api/collection/{card_id}` routes. FastAPI resolves literal routes first, but order matters for same-length paths. Place this route before `get_collection_card_tags`.

- [ ] **Step 6: Run the existing test — expect PASS**

```bash
pytest tests/test_tags.py::test_collection_returns_collection_tags_field -v
```

Expected: `PASSED`

- [ ] **Step 7: Add more tests to `tests/test_tags.py`**

```python
def test_deck_cards_returns_both_tag_fields(client):
    r = client.get("/api/decks/1/cards")
    assert r.status_code == 200
    cards = r.json()
    assert len(cards) == 1
    assert "collection_tags" in cards[0]
    assert "deck_tags" in cards[0]
    assert cards[0]["collection_tags"] == []
    assert cards[0]["deck_tags"] == []


def test_get_collection_card_tags_empty(client):
    r = client.get("/api/collection/1/tags")
    assert r.status_code == 200
    assert r.json() == []


def test_list_collection_tags_empty(client):
    r = client.get("/api/collection/tags")
    assert r.status_code == 200
    assert r.json() == []


def test_list_deck_tags_empty(client):
    r = client.get("/api/decks/1/tags")
    assert r.status_code == 200
    assert r.json() == []
```

- [ ] **Step 8: Run all tests**

```bash
pytest tests/test_tags.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add app.py tests/test_tags.py
git commit -m "feat: include tags in collection and deck list responses, add read/autocomplete endpoints"
```

---

## Task 4: Collection tag mutation endpoints + cascade cleanup

**Files:**
- Modify: `app.py`
- Modify: `tests/test_tags.py`

- [ ] **Step 1: Add failing tests first**

Append to `tests/test_tags.py`:

```python
def test_add_collection_tag(client):
    r = client.post("/api/collection/1/tags", json={"tag": "  Foil  "})
    assert r.status_code == 200
    assert r.json() == ["foil"]  # normalized to lowercase, trimmed


def test_add_duplicate_collection_tag_is_noop(client):
    client.post("/api/collection/1/tags", json={"tag": "foil"})
    r = client.post("/api/collection/1/tags", json={"tag": "foil"})
    assert r.status_code == 200
    assert r.json() == ["foil"]  # still just one


def test_delete_collection_tag(client):
    client.post("/api/collection/1/tags", json={"tag": "foil"})
    r = client.delete("/api/collection/1/tags/foil")
    assert r.status_code == 204
    tags = client.get("/api/collection/1/tags").json()
    assert tags == []


def test_collection_tags_appear_in_list(client):
    client.post("/api/collection/1/tags", json={"tag": "ramp"})
    r = client.get("/api/collection/tags")
    assert "ramp" in r.json()


def test_decrement_to_zero_deletes_collection_tags(client):
    client.post("/api/collection/1/tags", json={"tag": "foil"})
    # Decrement 4 times to reach 0
    for _ in range(4):
        client.post("/api/collection/1/decrement")
    tags = client.get("/api/collection/1/tags").json()
    assert tags == []
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_tags.py -k "collection_tag or decrement_to_zero" -v
```

Expected: All 5 new tests FAIL.

- [ ] **Step 3: Add the Pydantic model and mutation endpoints to `app.py`**

Add a model (near the other Pydantic models):

```python
class TagAdd(BaseModel):
    tag: str
```

Add the endpoints (before the `# Static files` section):

```python
@app.post("/api/collection/{card_id}/tags")
def add_collection_tag(card_id: int, body: TagAdd):
    tag = body.tag.strip().lower()
    if not tag:
        raise HTTPException(400, "Tag cannot be empty")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM cards WHERE id = ?", (card_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Card not found")
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
```

- [ ] **Step 4: Modify `decrement_collection` to delete tags when qty reaches 0**

Replace the existing `decrement_collection` function:

```python
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
```

- [ ] **Step 5: Run tests — expect all PASS**

```bash
pytest tests/test_tags.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_tags.py
git commit -m "feat: add collection tag mutation endpoints, clean up tags on decrement-to-zero"
```

---

## Task 5: Deck tag mutation endpoints + cascade cleanup

**Files:**
- Modify: `app.py`
- Modify: `tests/test_tags.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_tags.py`:

```python
def test_add_deck_tag(client):
    r = client.post("/api/decks/1/cards/1/tags", json={"tag": "  Ramp  "})
    assert r.status_code == 200
    assert r.json() == ["ramp"]


def test_add_duplicate_deck_tag_is_noop(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "ramp"})
    r = client.post("/api/decks/1/cards/1/tags", json={"tag": "ramp"})
    assert r.status_code == 200
    assert r.json() == ["ramp"]


def test_delete_deck_tag(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "ramp"})
    r = client.delete("/api/decks/1/cards/1/tags/ramp")
    assert r.status_code == 204
    tags = client.get("/api/decks/1/cards/1/tags").json()
    assert tags == []


def test_deck_tags_appear_in_autocomplete(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "wincon"})
    r = client.get("/api/decks/1/tags")
    assert "wincon" in r.json()


def test_deck_tags_in_deck_cards_response(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "removal"})
    r = client.get("/api/decks/1/cards")
    card = r.json()[0]
    assert "removal" in card["deck_tags"]


def test_remove_card_from_deck_deletes_its_deck_tags(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "removal"})
    client.delete("/api/decks/1/cards/1")
    # Card removed from deck; add it back and check tags are gone
    client.post("/api/decks/1/cards", json={"card_id": 1})
    tags = client.get("/api/decks/1/cards/1/tags").json()
    assert tags == []
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/test_tags.py -k "deck_tag or remove_card_from_deck_deletes" -v
```

Expected: All 6 new tests FAIL.

- [ ] **Step 3: Add deck tag mutation endpoints to `app.py`**

```python
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
```

- [ ] **Step 4: Modify `remove_card_from_deck` to delete deck tags**

Replace the existing `remove_card_from_deck` function:

```python
@app.delete("/api/decks/{deck_id}/cards/{card_id}", status_code=204)
def remove_card_from_deck(deck_id: int, card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM deck_card_tags WHERE deck_id = ? AND card_id = ?",
            (deck_id, card_id)
        )
        cur.execute(
            "DELETE FROM deck_cards WHERE deck_id = ? AND card_id = ?",
            (deck_id, card_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Card not in deck")
        conn.commit()
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/test_tags.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_tags.py
git commit -m "feat: add deck tag mutation endpoints, clean up deck tags on card removal"
```

---

## Task 6: Frontend — CSS for tags and group sections

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Append tag and group styles to `static/style.css`**

```css
/* ── Tag chips ─────────────────────────────────────────────────────────────── */
.tag-chips-row {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 4px;
}

.tag-chip {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  white-space: nowrap;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.6;
}
.tag-chip.collection-tag {
  background: rgba(200, 155, 60, 0.15);
  color: var(--accent);
  border: 1px solid rgba(200, 155, 60, 0.35);
}
.tag-chip.deck-tag {
  background: rgba(80, 160, 200, 0.15);
  color: #5aa0c8;
  border: 1px solid rgba(80, 160, 200, 0.35);
}

/* ── Modal tag editor ──────────────────────────────────────────────────────── */
.modal-tags-section {
  margin-top: 18px;
}
.modal-tags-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--muted);
  margin-bottom: 6px;
}
.modal-tags-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  align-items: center;
}
.modal-tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  line-height: 1.5;
}
.modal-tag-chip.collection-tag {
  background: rgba(200, 155, 60, 0.15);
  color: var(--accent);
  border: 1px solid rgba(200, 155, 60, 0.35);
}
.modal-tag-chip.deck-tag {
  background: rgba(80, 160, 200, 0.15);
  color: #5aa0c8;
  border: 1px solid rgba(80, 160, 200, 0.35);
}
.modal-tag-remove {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
  padding: 0;
  line-height: 1;
  opacity: 0.6;
  transition: opacity 0.1s;
}
.modal-tag-remove:hover { opacity: 1; }

.modal-tag-input {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--text);
  font-size: 12px;
  padding: 2px 10px;
  outline: none;
  width: 120px;
  transition: border-color 0.12s;
}
.modal-tag-input:focus { border-color: var(--accent); }
.modal-tag-input::placeholder { color: var(--muted); font-size: 11px; }

/* ── Group-by control ──────────────────────────────────────────────────────── */
.group-by-select {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 4px;
  color: var(--text);
  font-size: 12px;
  padding: 5px 8px;
  cursor: pointer;
  outline: none;
}
.group-by-select:focus { border-color: var(--accent); }

/* ── Group sections ────────────────────────────────────────────────────────── */
.group-section { margin-bottom: 20px; }

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 4px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border);
  margin-bottom: 10px;
}
.group-header:hover { color: var(--text); }

.group-header-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent);
  flex: 1;
}
.group-header-count {
  font-size: 11px;
  color: var(--muted);
}
.group-header-chevron {
  font-size: 10px;
  color: var(--muted);
  transition: transform 0.15s;
}
.group-header.collapsed .group-header-chevron { transform: rotate(-90deg); }

.group-body {
  display: grid;
  gap: 10px;
}
.group-body.hidden { display: none; }
```

- [ ] **Step 2: Verify the server starts without errors**

```bash
uvicorn app:app --reload
```

Open `http://localhost:8000` — no visual change yet, just confirm it loads.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: add CSS for tag chips, modal tag editor, and group sections"
```

---

## Task 7: Frontend — tag chips on card tiles

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Add tag chip HTML helper**

Add after the `esc()` function:

```javascript
function tagChipsHtml(tags, type) {
  if (!tags || !tags.length) return '';
  return `<div class="tag-chips-row">${
    tags.map(t => `<span class="tag-chip ${type}" title="${esc(t)}">${esc(t)}</span>`).join('')
  }</div>`;
}
```

- [ ] **Step 2: Modify `buildCardTile` to render collection tag chips**

In `buildCardTile`, find the `div.innerHTML = \`...\`` block. Add `tagChipsHtml` after the `qty-row` div:

```javascript
  div.innerHTML = `
    <div class="card-img-wrap">${imgHtml}</div>
    <div class="card-info">
      <div class="card-name">${esc(card.name)}</div>
      <div class="card-meta">${esc(meta)}</div>
      <div class="qty-row">
        <button class="qty-btn" data-action="dec" title="Remove from collection (-)">−</button>
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <button class="qty-btn" data-action="inc" title="Add to collection (+)">+</button>
      </div>
      ${tagChipsHtml(card.collection_tags, 'collection-tag')}
    </div>`;
```

- [ ] **Step 3: Modify `buildDeckCardTile` to render both tag types**

In `buildDeckCardTile`, find the `div.innerHTML = \`...\`` block. Add both chip rows after `.deck-card-row`:

```javascript
  div.innerHTML = `
    <div class="deck-card-img-wrap">${imgHtml}</div>
    <div class="deck-card-info">
      <div class="deck-card-name">${esc(card.name)}</div>
      <div class="deck-card-row">
        <button class="qty-btn" data-action="dec" title="−">−</button>
        <span class="qty-label owned">${card.quantity}</span>
        <button class="qty-btn" data-action="inc" title="+">+</button>
        <button class="deck-cmd-btn${card.is_commander ? ' active' : ''}" title="Toggle commander">♛</button>
        <button class="deck-remove-btn" title="Remove">×</button>
      </div>
      ${tagChipsHtml(card.collection_tags, 'collection-tag')}
      ${tagChipsHtml(card.deck_tags, 'deck-tag')}
    </div>`;
```

- [ ] **Step 4: Verify manually**

Start the server. Go to Collection view — tag chips should appear (empty for now until you add tags via modal in Task 8). Go to Decks view — same.

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: render collection and deck tag chips on card tiles"
```

---

## Task 8: Frontend — tag editing in modal

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Add tag API methods to the `API` object**

Add these inside the `API` object after `importCollection`:

```javascript
  async getCollectionCardTags(cardId) {
    const r = await fetch(`/api/collection/${cardId}/tags`);
    return r.ok ? r.json() : [];
  },
  async addCollectionTag(cardId, tag) {
    const r = await fetch(`/api/collection/${cardId}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag }),
    });
    if (!r.ok) throw new Error('Failed to add tag');
    return r.json();
  },
  async removeCollectionTag(cardId, tag) {
    await fetch(`/api/collection/${cardId}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
  },
  async getDeckCardTags(deckId, cardId) {
    const r = await fetch(`/api/decks/${deckId}/cards/${cardId}/tags`);
    return r.ok ? r.json() : [];
  },
  async addDeckTag(deckId, cardId, tag) {
    const r = await fetch(`/api/decks/${deckId}/cards/${cardId}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag }),
    });
    if (!r.ok) throw new Error('Failed to add tag');
    return r.json();
  },
  async removeDeckTag(deckId, cardId, tag) {
    await fetch(`/api/decks/${deckId}/cards/${cardId}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
  },
  async listCollectionTags() {
    const r = await fetch('/api/collection/tags');
    return r.ok ? r.json() : [];
  },
  async listDeckTags(deckId) {
    const r = await fetch(`/api/decks/${deckId}/tags`);
    return r.ok ? r.json() : [];
  },
```

- [ ] **Step 2: Update `openModal` signature to accept deck context**

Change `function openModal(card)` to:

```javascript
function openModal(card, deckContext = null) {
```

Update callers in `buildDeckCardTile`:

```javascript
  div.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
```

Update caller in `renderDeckText` (the row click handler):

```javascript
      row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
```

- [ ] **Step 3: Add `loadModalTags` function**

Add after `loadPrintings`:

```javascript
async function loadModalTags(card, deckContext) {
  const section = document.getElementById('modal-tags-section');
  if (!section) return;

  const inCollection = qty(card.id) > 0;

  // Fetch fresh tag data
  const [collTags, deckTags] = await Promise.all([
    inCollection ? API.getCollectionCardTags(card.id) : Promise.resolve([]),
    deckContext ? API.getDeckCardTags(deckContext.deckId, card.id) : Promise.resolve([]),
  ]);

  // Autocomplete suggestions
  const [allCollTags, allDeckTags] = await Promise.all([
    inCollection ? API.listCollectionTags() : Promise.resolve([]),
    deckContext ? API.listDeckTags(deckContext.deckId) : Promise.resolve([]),
  ]);

  if (!section.isConnected) return;
  section.innerHTML = '';

  if (inCollection) {
    section.appendChild(buildTagEditor({
      label: 'Collection tags',
      chipClass: 'collection-tag',
      tags: collTags,
      suggestions: allCollTags,
      onAdd: async (tag) => {
        const updated = await API.addCollectionTag(card.id, tag);
        syncCollectionTagsOnCard(card.id, updated);
        return updated;
      },
      onRemove: async (tag) => {
        await API.removeCollectionTag(card.id, tag);
        const updated = await API.getCollectionCardTags(card.id);
        syncCollectionTagsOnCard(card.id, updated);
        return updated;
      },
    }));
  }

  if (deckContext) {
    section.appendChild(buildTagEditor({
      label: 'Deck tags',
      chipClass: 'deck-tag',
      tags: deckTags,
      suggestions: allDeckTags,
      onAdd: async (tag) => {
        const updated = await API.addDeckTag(deckContext.deckId, card.id, tag);
        syncDeckTagsOnCard(card.id, updated);
        return updated;
      },
      onRemove: async (tag) => {
        await API.removeDeckTag(deckContext.deckId, card.id, tag);
        const updated = await API.getDeckCardTags(deckContext.deckId, card.id);
        syncDeckTagsOnCard(card.id, updated);
        return updated;
      },
    }));
  }
}
```

- [ ] **Step 4: Add `buildTagEditor` helper**

Add before `loadModalTags`:

```javascript
function buildTagEditor({ label, chipClass, tags, suggestions, onAdd, onRemove }) {
  const wrapper = document.createElement('div');
  wrapper.className = 'modal-tags-section';

  let currentTags = [...tags];

  function render() {
    wrapper.innerHTML = `
      <div class="modal-tags-label">${esc(label)}</div>
      <div class="modal-tags-chips">
        ${currentTags.map(t => `
          <span class="modal-tag-chip ${chipClass}" data-tag="${esc(t)}">
            ${esc(t)}
            <button class="modal-tag-remove" title="Remove">×</button>
          </span>`).join('')}
        <input class="modal-tag-input" list="tag-suggestions-${chipClass}"
          placeholder="Add tag…" autocomplete="off">
        <datalist id="tag-suggestions-${chipClass}">
          ${suggestions.map(s => `<option value="${esc(s)}">`).join('')}
        </datalist>
      </div>`;

    wrapper.querySelectorAll('.modal-tag-remove').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const tag = btn.closest('[data-tag]').dataset.tag;
        currentTags = await onRemove(tag);
        render();
      });
    });

    const input = wrapper.querySelector('.modal-tag-input');
    input.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        const val = input.value.trim().toLowerCase().replace(/,/g, '');
        if (!val) return;
        currentTags = await onAdd(val);
        render();
      }
    });
  }

  render();
  return wrapper;
}
```

- [ ] **Step 5: Add tag sync helpers**

Add after `loadModalTags`:

```javascript
function syncCollectionTagsOnCard(cardId, tags) {
  // Update collectionState so re-renders show fresh tags
  const card = collectionState.cards.find(c => c.id === cardId);
  if (card) { card.collection_tags = tags; renderCollectionGrid(); }
}

function syncDeckTagsOnCard(cardId, tags) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (card) { card.deck_tags = tags; renderDeckContent(); }
}
```

- [ ] **Step 6: Wire `loadModalTags` into `openModal`**

In `openModal`, add a `<div id="modal-tags-section">` to the `modal-details` HTML, then call `loadModalTags`. In the `contentEl.innerHTML` template, add after `.modal-collection`:

```javascript
      <div id="modal-tags-section" class="modal-tags-section"></div>
```

Then after the `loadPrintings(card)` call add:

```javascript
  loadModalTags(card, deckContext);
```

- [ ] **Step 7: Verify manually**

Start server. Open a card from Collection view — modal should show a "Collection tags" section with an input. Type a tag and press Enter — chip appears. Click × — chip removed. Open same card from Decks view — both "Collection tags" and "Deck tags" sections appear.

- [ ] **Step 8: Commit**

```bash
git add static/app.js
git commit -m "feat: add tag editor to card detail modal with autocomplete"
```

---

## Task 9: Frontend — group-by control

**Files:**
- Modify: `static/index.html`
- Modify: `static/app.js`

- [ ] **Step 1: Add group-by select to collection toolbar in `index.html`**

In `#view-collection .search-bar`, add after the `import-collection-btn` button:

```html
        <select id="collection-group-by" class="group-by-select">
          <option value="none">Group: None</option>
          <option value="collection-tag">Group: Tag</option>
        </select>
```

- [ ] **Step 2: Add group-by select to deck editor header in `index.html`**

In `.deck-editor-acts` div, add before the view-toggle span:

```html
                <select id="deck-group-by" class="group-by-select">
                  <option value="none">Group: None</option>
                  <option value="collection-tag">Collection tag</option>
                  <option value="deck-tag">Deck tag</option>
                </select>
```

- [ ] **Step 3: Add group-by state and helpers to `app.js`**

Add to `collectionState`:

```javascript
const collectionState = {
  cards: [],
  query: '',
  groupBy: 'none',   // 'none' | 'collection-tag'
};
```

Add to `deckState`:

```javascript
const deckState = {
  // ... existing fields ...
  groupBy: 'none',   // 'none' | 'collection-tag' | 'deck-tag'
};
```

- [ ] **Step 4: Add `groupCards` helper to `app.js`**

Add before `renderCollectionGrid`:

```javascript
/**
 * Groups an array of card objects by a tag type.
 * Returns [{ label, cards }, ...] sorted alphabetically, "Untagged" last.
 * A card with N tags appears in N groups.
 */
function groupCards(cards, tagField) {
  const map = new Map(); // label → Set of card objects
  for (const card of cards) {
    const tags = card[tagField] || [];
    if (!tags.length) {
      if (!map.has('Untagged')) map.set('Untagged', []);
      map.get('Untagged').push(card);
    } else {
      for (const tag of tags) {
        if (!map.has(tag)) map.set(tag, []);
        map.get(tag).push(card);
      }
    }
  }
  const groups = [];
  for (const [label, groupCards] of map) {
    if (label !== 'Untagged') groups.push({ label, cards: groupCards });
  }
  groups.sort((a, b) => a.label.localeCompare(b.label));
  if (map.has('Untagged')) groups.push({ label: 'Untagged', cards: map.get('Untagged') });
  return groups;
}
```

- [ ] **Step 5: Add `renderGroupedGrid` helper**

Add after `groupCards`:

```javascript
function renderGroupedGrid(container, groups, buildTileFn, collapsedState) {
  container.innerHTML = '';
  for (const group of groups) {
    const section = document.createElement('div');
    section.className = 'group-section';

    const isCollapsed = collapsedState.has(group.label);
    const header = document.createElement('div');
    header.className = 'group-header' + (isCollapsed ? ' collapsed' : '');
    header.innerHTML = `
      <span class="group-header-label">${esc(group.label)}</span>
      <span class="group-header-count">${group.cards.length}</span>
      <span class="group-header-chevron">▾</span>`;
    header.addEventListener('click', () => {
      if (collapsedState.has(group.label)) {
        collapsedState.delete(group.label);
      } else {
        collapsedState.add(group.label);
      }
      header.classList.toggle('collapsed');
      body.classList.toggle('hidden');
    });

    const body = document.createElement('div');
    body.className = 'group-body' + (isCollapsed ? ' hidden' : '');
    // Reuse the grid column layout
    body.style.gridTemplateColumns = container.style.gridTemplateColumns || '';
    body.style.gridAutoRows = container.style.gridAutoRows || '';

    for (const card of group.cards) body.appendChild(buildTileFn(card));

    section.appendChild(header);
    section.appendChild(body);
    container.appendChild(section);
  }
}
```

- [ ] **Step 6: Add collapse state trackers**

Add near the top of the state section:

```javascript
const collectionGroupCollapsed = new Set();
const deckGroupCollapsed = new Set();
```

- [ ] **Step 7: Modify `renderCollectionGrid` to support grouping**

In `renderCollectionGrid`, replace the card-appending block (after the filtered/empty check) with:

```javascript
  if (collectionState.groupBy !== 'none') {
    const tagField = 'collection_tags';
    const groups = groupCards(filtered, tagField);
    renderGroupedGrid(grid, groups, buildCardTile, collectionGroupCollapsed);
  } else {
    const frag = document.createDocumentFragment();
    for (const card of filtered) frag.appendChild(buildCardTile(card));
    grid.appendChild(frag);
  }
```

- [ ] **Step 8: Wire the collection group-by select**

Add after the collection-search event listeners:

```javascript
document.getElementById('collection-group-by').addEventListener('change', e => {
  collectionState.groupBy = e.target.value;
  collectionGroupCollapsed.clear();
  renderCollectionGrid();
});
```

- [ ] **Step 9: Modify `renderDeckGrid` to support grouping**

In `renderDeckGrid`, replace the sorted/frag block with:

```javascript
  if (deckState.groupBy !== 'none') {
    const tagField = deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags';
    const groups = groupCards(deckState.deckCards, tagField);
    renderGroupedGrid(el, groups, buildDeckCardTile, deckGroupCollapsed);
  } else {
    const sorted = [...deckState.deckCards].sort((a, b) => {
      if (a.is_commander && !b.is_commander) return -1;
      if (!a.is_commander && b.is_commander) return 1;
      return a.name.localeCompare(b.name);
    });
    const frag = document.createDocumentFragment();
    for (const card of sorted) frag.appendChild(buildDeckCardTile(card));
    el.appendChild(frag);
  }
```

- [ ] **Step 10: Wire the deck group-by select**

Add after the `.vtoggle-btn` event listeners:

```javascript
document.getElementById('deck-group-by').addEventListener('change', e => {
  deckState.groupBy = e.target.value;
  deckGroupCollapsed.clear();
  renderDeckContent();
});
```

- [ ] **Step 11: Verify manually**

Start server. In Collection view: set Group by Tag → tagged cards form sections with collapsible headers; untagged in "Untagged" section. In Decks view: test both Collection tag and Deck tag groupings. Collapsing a section hides its cards. Switching back to "None" returns flat grid.

- [ ] **Step 12: Commit**

```bash
git add static/index.html static/app.js
git commit -m "feat: add group-by-tag control to collection and deck views"
```

---

## Self-Review Checklist

- [x] Schema: both tables created with correct FK/UNIQUE constraints
- [x] Cascade gap documented and handled in endpoint logic (`decrement_collection`, `remove_card_from_deck`)
- [x] Route order: `GET /api/collection/tags` defined before `GET /api/collection/{card_id}/tags` — both 3-segment paths, FastAPI prefers literal
- [x] Tag normalization (lowercase + trim) applied at API layer in both `add_collection_tag` and `add_deck_card_tag`
- [x] `TagAdd` model reused for both collection and deck endpoints
- [x] `syncCollectionTagsOnCard` / `syncDeckTagsOnCard` keep in-memory state fresh after modal mutations so tiles re-render with new chips without a full reload
- [x] Group-by: a card with multiple tags appears in each tag's section (implemented in `groupCards`)
- [x] Untagged cards appear last in a dedicated "Untagged" section
- [x] Collapse state cleared when group-by selection changes
- [x] `deckGroupCollapsed` / `collectionGroupCollapsed` separate so deck and collection states don't interfere
