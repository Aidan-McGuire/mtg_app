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
