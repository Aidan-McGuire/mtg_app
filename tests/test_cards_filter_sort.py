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


def test_filter_combined_with_query(client, seed_cards):
    # q falls back to LIKE name-match (no FTS table in test DB); cmc filter also applies
    r = client.get("/api/cards", params={"q": "Wise", "cmc_min": 4})
    assert _names(r) == ["Wise Elephant"]


def test_query_with_filter_excludes_nonmatching(client, seed_cards):
    r = client.get("/api/cards", params={"q": "Grizzly", "types": "Sorcery"})
    assert r.json() == []


def _ordered(resp):
    return [c["name"] for c in resp.json()]


def test_sort_by_cmc_asc(client, seed_cards):
    r = client.get("/api/cards", params={"sort": "cmc", "dir": "asc"})
    cmcs = [c["cmc"] for c in r.json()]
    assert cmcs == sorted(cmcs)


def test_sort_by_cmc_desc(client, seed_cards):
    r = client.get("/api/cards", params={"sort": "cmc", "dir": "desc"})
    cmcs = [c["cmc"] for c in r.json()]
    assert cmcs == sorted(cmcs, reverse=True)


def test_sort_by_power_puts_nonnumeric_and_missing_last(client, seed_cards):
    # power values: Steel Wall 0, Grizzly Bears 2, Wise Elephant 3,
    # Mystery Hydra '*' (non-numeric -> last), Ancestral Vision NULL (-> last)
    r = client.get("/api/cards", params={"sort": "power", "dir": "asc"})
    names = _ordered(r)
    assert names[:3] == ["Steel Wall", "Grizzly Bears", "Wise Elephant"]
    assert set(names[3:]) == {"Mystery Hydra", "Ancestral Vision"}
