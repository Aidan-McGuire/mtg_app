import sqlite3
import main as main_module


def _make_v5_db(tmp_path):
    p = tmp_path / "mig.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL);")
    conn.execute("INSERT INTO schema_version VALUES (5);")
    # decks has existed since v1 — a real v5 database already has it, and the
    # v6->v7 migration (added for the built-flag feature) now ALTERs it too.
    conn.execute("""
        CREATE TABLE decks (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()
    return p


def test_migration_adds_cards_last_refreshed_column(tmp_path, monkeypatch):
    db = _make_v5_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()

    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(schema_version)")]
    version, last_refreshed = conn.execute(
        "SELECT version, cards_last_refreshed FROM schema_version"
    ).fetchone()
    conn.close()

    assert "cards_last_refreshed" in cols
    assert version == 7
    assert last_refreshed is None


def test_migration_is_idempotent(tmp_path, monkeypatch):
    db = _make_v5_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()
    main_module.migrate_database()  # must not error, must not re-add the column

    conn = sqlite3.connect(str(db))
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()

    assert version == 7


def _make_v6_db(tmp_path):
    p = tmp_path / "mig_v6.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, cards_last_refreshed TEXT);")
    conn.execute("INSERT INTO schema_version VALUES (6, NULL);")
    conn.execute("""
        CREATE TABLE decks (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.execute("INSERT INTO decks (name) VALUES ('Existing Deck');")
    conn.commit()
    conn.close()
    return p


def test_migration_adds_built_column_defaulting_to_zero(tmp_path, monkeypatch):
    db = _make_v6_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()

    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(decks)")]
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    built = conn.execute("SELECT built FROM decks WHERE name = 'Existing Deck'").fetchone()[0]
    conn.close()

    assert "built" in cols
    assert version == 7
    assert built == 0


def test_migration_v6_to_v7_is_idempotent(tmp_path, monkeypatch):
    db = _make_v6_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()
    main_module.migrate_database()  # must not error, must not re-add the column

    conn = sqlite3.connect(str(db))
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()

    assert version == 7
