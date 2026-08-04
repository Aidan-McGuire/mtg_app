import sqlite3
from pathlib import Path

DB_PATH = Path("mtg.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")  # enforce foreign keys
    conn.execute("PRAGMA journal_mode = WAL;") # safer for desktop apps
    return conn

def initialize_database():
    conn = get_connection()
    cur = conn.cursor()

    # version table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );
    """)

    # cards table (minimal)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cards (
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
    """)

    # Full Text Search card table
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS cards_fts
        USING fts5(
            name,
            oracle_text,
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS collection (
            id INTEGER PRIMARY KEY,
            card_id INTEGER NOT NULL UNIQUE REFERENCES cards(id),
            quantity INTEGER NOT NULL DEFAULT 0
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS decks (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS deck_cards (
            id INTEGER PRIMARY KEY,
            deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
            card_id INTEGER NOT NULL REFERENCES cards(id),
            quantity INTEGER NOT NULL DEFAULT 1,
            is_commander INTEGER NOT NULL DEFAULT 0,
            UNIQUE(deck_id, card_id)
        );
    """)

    # only insert version if empty
    cur.execute("SELECT COUNT(*) FROM schema_version;")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO schema_version (version) VALUES (1);")

    conn.commit()
    conn.close()
    print("Database initialized at", DB_PATH.resolve())

def migrate_database():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT version FROM schema_version LIMIT 1;")
    row = cur.fetchone()
    version = row[0] if row else 0

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

    if version < 3:
        cur.execute("ALTER TABLE cards ADD COLUMN power TEXT;")
        cur.execute("ALTER TABLE cards ADD COLUMN toughness TEXT;")
        cur.execute("UPDATE schema_version SET version = 3;")

    if version < 4:
        cur.execute("ALTER TABLE deck_cards ADD COLUMN is_considering INTEGER NOT NULL DEFAULT 0;")
        cur.execute("UPDATE schema_version SET version = 4;")

    if version < 5:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS import_failures (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                deck_id INTEGER REFERENCES decks(id) ON DELETE CASCADE,
                card_name TEXT NOT NULL,
                requested_qty INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT
            );
        """)
        cur.execute("UPDATE schema_version SET version = 5;")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_database()
    migrate_database()
    print("Migration complete.")
