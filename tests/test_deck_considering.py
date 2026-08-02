def test_update_deck_card_sets_is_considering(client):
    r = client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_considering"] is True
    assert body["is_commander"] is False


def test_setting_commander_clears_considering(client):
    client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    r = client.patch("/api/decks/1/cards/1", json={"is_commander": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_commander"] is True
    assert body["is_considering"] is False


def test_setting_considering_clears_commander(client):
    client.patch("/api/decks/1/cards/1", json={"is_commander": True})
    r = client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_considering"] is True
    assert body["is_commander"] is False


def test_setting_both_true_commander_wins(client):
    r = client.patch("/api/decks/1/cards/1", json={"is_commander": True, "is_considering": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_commander"] is True
    assert body["is_considering"] is False


def test_get_deck_cards_includes_is_considering(client):
    client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    r = client.get("/api/decks/1/cards")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["is_considering"] is True


def test_add_card_to_deck_response_includes_is_considering(client):
    r = client.post("/api/decks/1/cards", json={"card_id": 2, "quantity": 1})
    assert r.status_code == 201
    assert r.json()["is_considering"] is False


def test_list_decks_card_count_excludes_considering(client):
    client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    r = client.get("/api/decks")
    assert r.status_code == 200
    deck = next(d for d in r.json() if d["id"] == 1)
    assert deck["card_count"] == 0
