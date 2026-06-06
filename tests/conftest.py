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
