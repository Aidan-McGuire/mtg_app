def test_card_in_one_deck(client):
    r = client.get("/api/cards/1/decks")
    assert r.status_code == 200
    assert r.json() == [{"id": 1, "name": "Test Deck"}]


def test_card_in_no_decks(client):
    r = client.get("/api/cards/2/decks")
    assert r.status_code == 200
    assert r.json() == []


def test_card_in_multiple_decks_sorted_distinct(client, db_path):
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    # Two more decks; "Aggro" sorts before "Test Deck", "Zoo" after.
    conn.execute("INSERT INTO decks (id, name) VALUES (2, 'Zoo')")
    conn.execute("INSERT INTO decks (id, name) VALUES (3, 'Aggro')")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 2)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3, 1, 1)")
    conn.commit()
    conn.close()
    r = client.get("/api/cards/1/decks")
    assert r.status_code == 200
    assert r.json() == [
        {"id": 3, "name": "Aggro"},
        {"id": 1, "name": "Test Deck"},
        {"id": 2, "name": "Zoo"},
    ]


def test_card_not_found(client):
    r = client.get("/api/cards/9999/decks")
    assert r.status_code == 404
    assert r.json() == {"detail": "Card not found"}
