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


def test_lookup_matches_curly_apostrophe_against_straight_apostrophe_name(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line) "
        "VALUES ('beifong-uuid', \"Beifong's Bounty Hunters\", '{2}{W}', 3, 'Creature')"
    )
    conn.commit()
    conn.close()

    r = client.post("/api/collection/import", json={"list": "1x Beifong’s Bounty Hunters"})
    assert r.status_code == 200
    assert r.json()["not_found"] == []

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM import_failures").fetchone()[0]
    conn.close()
    assert count == 0


def test_lookup_strips_curly_brace_collector_number_suffix(client, db_path):
    r = client.post("/api/collection/import", json={"list": "1x Lightning Bolt {122}"})
    assert r.status_code == 200
    assert r.json()["not_found"] == []

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM import_failures").fetchone()[0]
    conn.close()
    assert count == 0


def _seed_failure(db_path, source="collection", deck_id=None, card_name="Ghost Card", qty=1, resolved=False):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO import_failures (source, deck_id, card_name, requested_qty, resolved_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (source, deck_id, card_name, qty, "2026-08-03T00:00:00" if resolved else None),
    )
    conn.commit()
    failure_id = conn.execute("SELECT id FROM import_failures WHERE card_name = ?", (card_name,)).fetchone()[0]
    conn.close()
    return failure_id


def test_get_import_failures_defaults_to_outstanding(client, db_path):
    _seed_failure(db_path, card_name="Outstanding One", resolved=False)
    _seed_failure(db_path, card_name="Resolved One", resolved=True)

    r = client.get("/api/import-failures")
    assert r.status_code == 200
    names = [f["card_name"] for f in r.json()]
    assert names == ["Outstanding One"]


def test_get_import_failures_resolved_true(client, db_path):
    _seed_failure(db_path, card_name="Outstanding One", resolved=False)
    _seed_failure(db_path, card_name="Resolved One", resolved=True)

    r = client.get("/api/import-failures?resolved=true")
    names = [f["card_name"] for f in r.json()]
    assert names == ["Resolved One"]


def test_get_import_failures_resolved_all(client, db_path):
    _seed_failure(db_path, card_name="Outstanding One", resolved=False)
    _seed_failure(db_path, card_name="Resolved One", resolved=True)

    r = client.get("/api/import-failures?resolved=all")
    names = sorted(f["card_name"] for f in r.json())
    assert names == ["Outstanding One", "Resolved One"]


def test_get_import_failures_includes_deck_name(client, db_path):
    # deck id 1 ("Test Deck") already exists per the base _SCHEMA seed data
    _seed_failure(db_path, source="deck", deck_id=1, card_name="Deck Miss")

    r = client.get("/api/import-failures")
    row = next(f for f in r.json() if f["card_name"] == "Deck Miss")
    assert row["deck_id"] == 1
    assert row["deck_name"] == "Test Deck"


def test_resolve_import_failure(client, db_path):
    failure_id = _seed_failure(db_path, card_name="To Resolve")

    r = client.post(f"/api/import-failures/{failure_id}/resolve")
    assert r.status_code == 200
    assert r.json()["resolved_at"] is not None

    remaining = client.get("/api/import-failures").json()
    assert all(f["id"] != failure_id for f in remaining)


def test_resolve_nonexistent_import_failure_404(client):
    r = client.post("/api/import-failures/9999/resolve")
    assert r.status_code == 404
