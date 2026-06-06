def test_collection_returns_collection_tags_field(client):
    r = client.get("/api/collection")
    assert r.status_code == 200
    cards = r.json()
    assert len(cards) == 1
    assert "collection_tags" in cards[0]
    assert cards[0]["collection_tags"] == []


def test_deck_cards_returns_both_tag_fields(client):
    r = client.get("/api/decks/1/cards")
    assert r.status_code == 200
    cards = r.json()
    assert len(cards) == 1
    assert "collection_tags" in cards[0]
    assert "deck_tags" in cards[0]
    assert cards[0]["collection_tags"] == []
    assert cards[0]["deck_tags"] == []


def test_get_collection_card_tags_empty(client):
    r = client.get("/api/collection/1/tags")
    assert r.status_code == 200
    assert r.json() == []


def test_list_collection_tags_empty(client):
    r = client.get("/api/collection/tags")
    assert r.status_code == 200
    assert r.json() == []


def test_list_deck_tags_empty(client):
    r = client.get("/api/decks/1/tags")
    assert r.status_code == 200
    assert r.json() == []


def test_add_collection_tag(client):
    r = client.post("/api/collection/1/tags", json={"tag": "  Foil  "})
    assert r.status_code == 200
    assert r.json() == ["foil"]  # normalized to lowercase, trimmed


def test_add_duplicate_collection_tag_is_noop(client):
    client.post("/api/collection/1/tags", json={"tag": "foil"})
    r = client.post("/api/collection/1/tags", json={"tag": "foil"})
    assert r.status_code == 200
    assert r.json() == ["foil"]  # still just one


def test_delete_collection_tag(client):
    client.post("/api/collection/1/tags", json={"tag": "foil"})
    r = client.delete("/api/collection/1/tags/foil")
    assert r.status_code == 204
    tags = client.get("/api/collection/1/tags").json()
    assert tags == []


def test_collection_tags_appear_in_list(client):
    client.post("/api/collection/1/tags", json={"tag": "ramp"})
    r = client.get("/api/collection/tags")
    assert "ramp" in r.json()


def test_decrement_to_zero_deletes_collection_tags(client):
    client.post("/api/collection/1/tags", json={"tag": "foil"})
    # Decrement 4 times to reach 0 (card has qty=4 in fixture)
    for _ in range(4):
        client.post("/api/collection/1/decrement")
    tags = client.get("/api/collection/1/tags").json()
    assert tags == []


def test_add_deck_tag(client):
    r = client.post("/api/decks/1/cards/1/tags", json={"tag": "  Ramp  "})
    assert r.status_code == 200
    assert r.json() == ["ramp"]


def test_add_duplicate_deck_tag_is_noop(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "ramp"})
    r = client.post("/api/decks/1/cards/1/tags", json={"tag": "ramp"})
    assert r.status_code == 200
    assert r.json() == ["ramp"]


def test_delete_deck_tag(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "ramp"})
    r = client.delete("/api/decks/1/cards/1/tags/ramp")
    assert r.status_code == 204
    tags = client.get("/api/decks/1/cards/1/tags").json()
    assert tags == []


def test_deck_tags_appear_in_autocomplete(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "wincon"})
    r = client.get("/api/decks/1/tags")
    assert "wincon" in r.json()


def test_deck_tags_in_deck_cards_response(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "removal"})
    r = client.get("/api/decks/1/cards")
    card = r.json()[0]
    assert "removal" in card["deck_tags"]


def test_remove_card_from_deck_deletes_its_deck_tags(client):
    client.post("/api/decks/1/cards/1/tags", json={"tag": "removal"})
    client.delete("/api/decks/1/cards/1")
    # Card removed from deck; add it back and check tags are gone
    client.post("/api/decks/1/cards", json={"card_id": 1})
    tags = client.get("/api/decks/1/cards/1/tags").json()
    assert tags == []
