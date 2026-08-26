import sqlite3


def test_collection_row_includes_allocated_qty_zero_by_default(client, db_path):
    r = client.get("/api/collection")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 0


def test_allocated_qty_counts_built_deck_cards(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 4


def test_allocated_qty_ignores_non_built_deck_cards(client, db_path):
    # deck 1 is NOT built (default) and already holds 4 copies of card 1 per
    # the base fixture — allocated_qty must stay 0 until the deck is built.
    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 0


def test_allocated_qty_ignores_considering_cards_in_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.execute("UPDATE deck_cards SET is_considering = 1 WHERE deck_id = 1 AND card_id = 1")
    conn.commit()
    conn.close()

    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 0


def test_allocated_qty_sums_across_multiple_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Second Deck', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 2)")
    conn.commit()
    conn.close()

    r = client.get("/api/collection")
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["allocated_qty"] == 6
