import gzip
import io
import json
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


def test_fts_updated_on_reimport(tmp_path, monkeypatch):
    """UPDATE path must keep cards_fts in sync with the cards row."""
    db = _make_db(tmp_path)
    monkeypatch.setattr(importer, "DB_PATH", db)
    monkeypatch.setattr(importer, "get_bulk_download_url", lambda: "x")

    # First import: card with original oracle_text
    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([_card("elf-uuid", "Llanowar Elves", oracle_text="Tap for mana.")]),
    )
    importer.import_cards()

    # Second import: same card with updated oracle_text (errata)
    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([_card("elf-uuid", "Llanowar Elves", oracle_text="Add {G}.")]),
    )
    importer.import_cards()

    conn = sqlite3.connect(str(db))
    old_fts = conn.execute(
        "SELECT COUNT(*) FROM cards_fts WHERE oracle_text = 'Tap for mana.'"
    ).fetchone()[0]
    new_fts = conn.execute(
        "SELECT COUNT(*) FROM cards_fts WHERE oracle_text = 'Add {G}.'"
    ).fetchone()[0]
    total_fts = conn.execute("SELECT COUNT(*) FROM cards_fts").fetchone()[0]
    conn.close()

    assert total_fts == 1       # still only one FTS row
    assert old_fts == 0         # stale text gone
    assert new_fts == 1         # updated text searchable


class _FakeResponse:
    """Minimal stand-in for requests.Response, used to test real HTTP-facing
    importer functions without hitting the network."""
    def __init__(self, json_body=None, raw=None):
        self._json_body = json_body
        self.raw = raw

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_body


def test_get_bulk_download_url_uses_jsonl_field(monkeypatch):
    """Scryfall's /bulk-data response for 'default_cards' now only provides
    jsonl_download_uri (no download_uri) -- this is the real shape returned
    by the live API as of 2026-08-01."""
    api_response = {
        "data": [
            {"type": "oracle_cards", "jsonl_download_uri": "https://data.scryfall.io/oracle.jsonl.gz"},
            {
                "type": "default_cards",
                "jsonl_download_uri": "https://data.scryfall.io/default-cards/default-cards-20260801211246.jsonl.gz",
            },
        ]
    }
    monkeypatch.setattr(
        importer.requests, "get",
        lambda url, headers=None: _FakeResponse(json_body=api_response),
    )
    result = importer.get_bulk_download_url()
    assert result == "https://data.scryfall.io/default-cards/default-cards-20260801211246.jsonl.gz"


def test_stream_cards_parses_jsonl_gzip_format(monkeypatch):
    """The bulk file is JSONL (one complete JSON object per line), gzip-compressed --
    not a single top-level JSON array. Verified against the real file's format."""
    cards = [
        {"oracle_id": "forest-uuid", "name": "Forest", "type_line": "Basic Land — Forest"},
        {"oracle_id": "bolt-uuid", "name": "Lightning Bolt", "type_line": "Instant"},
    ]
    jsonl_bytes = "\n".join(json.dumps(c) for c in cards).encode("utf-8")
    gz_buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=gz_buffer, mode="wb") as gz:
        gz.write(jsonl_bytes)
    gz_buffer.seek(0)

    monkeypatch.setattr(
        importer.requests, "get",
        lambda url, stream=None, headers=None: _FakeResponse(raw=gz_buffer),
    )
    result = list(importer._stream_cards("https://fake-url/default-cards.jsonl.gz"))
    assert result == cards


def test_new_card_inserted_on_second_import(tmp_path, monkeypatch):
    """A brand-new oracle_id in a re-import must land in both cards and cards_fts."""
    db = _make_db(tmp_path)
    monkeypatch.setattr(importer, "DB_PATH", db)
    monkeypatch.setattr(importer, "get_bulk_download_url", lambda: "x")

    # First import: one card
    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([_card("elf-uuid", "Llanowar Elves")]),
    )
    importer.import_cards()

    # Second import: original card + a brand-new card
    monkeypatch.setattr(
        importer, "_stream_cards",
        lambda url: iter([
            _card("elf-uuid", "Llanowar Elves"),
            _card("bolt-uuid", "Lightning Bolt", type_line="Instant",
                  oracle_text="Lightning Bolt deals 3 damage to any target.",
                  colors=["R"], color_identity=["R"]),
        ]),
    )
    importer.import_cards()

    conn = sqlite3.connect(str(db))
    card_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    fts_count = conn.execute("SELECT COUNT(*) FROM cards_fts").fetchone()[0]
    bolt_cards = conn.execute(
        "SELECT COUNT(*) FROM cards WHERE oracle_id = 'bolt-uuid'"
    ).fetchone()[0]
    bolt_fts = conn.execute(
        "SELECT COUNT(*) FROM cards_fts WHERE name = 'Lightning Bolt'"
    ).fetchone()[0]
    conn.close()

    assert card_count == 2      # original + new card
    assert fts_count == 2       # FTS row inserted for new card too
    assert bolt_cards == 1      # new card present in cards
    assert bolt_fts == 1        # new card present in cards_fts
