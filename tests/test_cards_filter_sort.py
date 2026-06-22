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


def _names(resp):
    return sorted(c["name"] for c in resp.json())


def test_filter_by_type(client, seed_cards):
    r = client.get("/api/cards", params={"types": "Sorcery"})
    assert _names(r) == ["Ancestral Vision"]


def test_filter_by_multiple_types_is_or(client, seed_cards):
    r = client.get("/api/cards", params={"types": "Sorcery,Artifact"})
    assert _names(r) == ["Ancestral Vision", "Steel Wall"]


def test_filter_by_cmc_range(client, seed_cards):
    r = client.get("/api/cards", params={"cmc_min": 2, "cmc_max": 5})
    assert _names(r) == ["Grizzly Bears", "Wise Elephant"]


def test_filter_by_text(client, seed_cards):
    r = client.get("/api/cards", params={"text": "draw"})
    assert _names(r) == ["Ancestral Vision", "Wise Elephant"]


def test_filter_by_colors_subset_includes_colorless(client, seed_cards):
    # Selecting G returns green cards AND colorless cards (subset semantics).
    r = client.get("/api/cards", params={"colors": "G"})
    assert _names(r) == ["Grizzly Bears", "Mystery Hydra", "Steel Wall", "Wise Elephant"]


def test_filter_colorless_only(client, seed_cards):
    r = client.get("/api/cards", params={"colorless": "1"})
    assert _names(r) == ["Steel Wall"]
