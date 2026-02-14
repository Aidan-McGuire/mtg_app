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

    # only insert version if empty
    cur.execute("SELECT COUNT(*) FROM schema_version;")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO schema_version (version) VALUES (1);")

    conn.commit()
    conn.close()
    print("Database initialized at", DB_PATH.resolve())

if __name__ == "__main__":
    initialize_database()
