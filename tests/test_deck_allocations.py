import sqlite3


def test_allocations_empty_when_no_other_built_decks(client):
    r = client.get("/api/decks/1/allocations")
    assert r.status_code == 200
    assert r.json() == {}


def test_allocations_excludes_the_deck_itself_even_if_built(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.status_code == 200
    assert r.json() == {}


def test_allocations_counts_other_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Other Built Deck', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 3)")
    conn.commit()
    conn.close()

    # From deck 1's perspective, card 1 is allocated 3 elsewhere (deck 2).
    r = client.get("/api/decks/1/allocations")
    assert r.json() == {"1": 3}

    # From deck 2's own perspective, its own 3 copies aren't "elsewhere" —
    # but deck 1's 4 copies would be, if deck 1 were built too. It isn't
    # (base fixture default), so deck 2 sees nothing allocated elsewhere.
    r2 = client.get("/api/decks/2/allocations")
    assert r2.json() == {}


def test_allocations_ignores_non_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Not Built', 0)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 3)")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.json() == {}


def test_allocations_ignores_considering_cards(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Other Built Deck', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity, is_considering) VALUES (2, 1, 3, 1)")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.json() == {}


def test_allocations_sums_across_multiple_other_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Built Deck Two', 1)")
    conn.execute("INSERT INTO decks (id, name, built) VALUES (3, 'Built Deck Three', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 2)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3, 1, 1)")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.json() == {"1": 3}
