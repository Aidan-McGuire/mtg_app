import pytest
import sqlite3
from datetime import datetime, timezone
from fastapi.testclient import TestClient

_SCHEMA = """
CREATE TABLE schema_version (version INTEGER NOT NULL, cards_last_refreshed TEXT);
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
    is_considering INTEGER NOT NULL DEFAULT 0,
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
CREATE TABLE import_failures (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    deck_id INTEGER REFERENCES decks(id) ON DELETE CASCADE,
    card_name TEXT NOT NULL,
    requested_qty INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);
INSERT INTO schema_version VALUES (6, NULL);
INSERT INTO cards (id, oracle_id, name, mana_cost, cmc, type_line) VALUES (1, 'bolt-uuid', 'Lightning Bolt', '{R}', 1, 'Instant');
INSERT INTO cards (id, oracle_id, name, mana_cost, cmc, type_line) VALUES (2, 'forest-uuid', 'Forest', NULL, 0, 'Basic Land');
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
    # Seed a fresh (not stale) refresh timestamp, computed at fixture-setup
    # time rather than hardcoded, so the background card-refresh startup
    # hook never fires during tests (see tests/test_card_refresh.py for its
    # dedicated coverage) — a hardcoded past date would eventually cross the
    # 7-day threshold and start making real network calls in test runs.
    conn.execute(
        "UPDATE schema_version SET cards_last_refreshed = ?",
        (datetime.now(timezone.utc).isoformat(),),
    )
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def client(db_path, monkeypatch):
    import app as app_module
    import main as main_module
    monkeypatch.setattr(app_module, "DB_PATH", db_path)
    monkeypatch.setattr(main_module, "DB_PATH", db_path)
    # Suppress static file mount errors in test environment
    with TestClient(app_module.app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def seed_cards(db_path):
    conn = sqlite3.connect(str(db_path))
    # Remove base stub cards so sort/filter tests see only the seeded set.
    conn.execute("DELETE FROM deck_cards WHERE card_id IN (SELECT id FROM cards WHERE oracle_id IN ('bolt-uuid', 'forest-uuid'))")
    conn.execute("DELETE FROM collection WHERE card_id IN (SELECT id FROM cards WHERE oracle_id IN ('bolt-uuid', 'forest-uuid'))")
    conn.execute("DELETE FROM cards WHERE oracle_id IN ('bolt-uuid', 'forest-uuid')")
    assert conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 0, \
        "seed_cards expected a clean cards table after deleting base stubs"
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
