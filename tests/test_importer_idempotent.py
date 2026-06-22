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
