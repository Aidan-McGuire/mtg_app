def test_collection_includes_oracle_text_and_pt(client, seed_cards):
    r = client.get("/api/collection")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["name"] == "Grizzly Bears")
    assert card["power"] == "2"
    assert card["toughness"] == "2"
    assert "oracle_text" in card


def test_deck_cards_include_pt(client, seed_cards):
    r = client.get("/api/decks/1/cards")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["name"] == "Grizzly Bears")
    assert card["power"] == "2"
    assert card["toughness"] == "2"
