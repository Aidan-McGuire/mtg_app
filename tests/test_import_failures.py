import sqlite3


def test_failed_collection_import_records_failure(client, db_path):
    r = client.post("/api/collection/import", json={"list": "1x Totally Fake Card Name"})
    assert r.status_code == 200
    assert "Totally Fake Card Name" in r.json()["not_found"]

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT source, deck_id, card_name, requested_qty, resolved_at FROM import_failures"
    ).fetchone()
    conn.close()
    assert row == ("collection", None, "Totally Fake Card Name", 1, None)


def test_failed_deck_import_records_failure(client, db_path):
    r = client.post("/api/decks/import", json={
        "name": "New Deck", "list": "2x Another Fake Card"
    })
    assert r.status_code == 201
    body = r.json()
    deck_id = body["deck"]["id"]
    assert "Another Fake Card" in body["not_found"]

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT source, deck_id, card_name, requested_qty, resolved_at FROM import_failures"
    ).fetchone()
    conn.close()
    assert row == ("deck", deck_id, "Another Fake Card", 2, None)


def test_successful_import_records_no_failure(client, db_path):
    r = client.post("/api/collection/import", json={"list": "1x Lightning Bolt"})
    assert r.status_code == 200
    assert r.json()["not_found"] == []

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM import_failures").fetchone()[0]
    conn.close()
    assert count == 0
