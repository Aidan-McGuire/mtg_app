import sqlite3


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


def test_filter_by_power_range(client, seed_cards):
    # powers: Steel Wall 0, Grizzly Bears 2, Wise Elephant 3, Mystery Hydra '*', Ancestral Vision NULL
    r = client.get("/api/cards", params={"power_min": 1, "power_max": 3})
    assert _names(r) == ["Grizzly Bears", "Wise Elephant"]


def test_filter_by_toughness_range(client, seed_cards):
    # toughness: Grizzly Bears 2, Steel Wall 4, Wise Elephant 5, Mystery Hydra '*', Ancestral Vision NULL
    r = client.get("/api/cards", params={"toughness_min": 2, "toughness_max": 4})
    assert _names(r) == ["Grizzly Bears", "Steel Wall"]


def test_filter_by_power_excludes_variable_power(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, power, toughness) "
        "VALUES ('variable', 'Battlefield Construct', '{2}', 2, 'Creature — Construct', '1+*', '1+*')"
    )
    conn.commit()
    conn.close()
    # CAST('1+*' AS REAL) == 1.0 in SQLite, so a naive numeric check would wrongly
    # let this card pass power_min=1; the stricter digits-and-dot-only check excludes it.
    r = client.get("/api/cards", params={"power_min": 1})
    assert "Battlefield Construct" not in _names(r)


def test_filter_by_power_combined_with_cmc(client, seed_cards):
    # Grizzly Bears: power 2, cmc 2 -> matches both.
    # Wise Elephant: power 3, but cmc 5 -> excluded by cmc_max.
    r = client.get("/api/cards", params={"power_min": 2, "cmc_max": 2})
    assert _names(r) == ["Grizzly Bears"]


def test_filter_by_exact_colors_single_letter(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, colors, color_identity) "
        "VALUES ('deathrite', 'Deathrite Shaman', '{B/G}', 1, 'Creature — Elf Shaman', 'BG', 'BG')"
    )
    conn.commit()
    conn.close()
    # exact G match returns only the mono-green seeded cards, excluding the
    # multicolor Deathrite Shaman even though it contains green.
    r = client.get("/api/cards", params={"exact_colors": "G"})
    assert _names(r) == ["Grizzly Bears", "Mystery Hydra", "Wise Elephant"]


def test_filter_by_exact_colors_multicolor(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, colors, color_identity) "
        "VALUES ('deathrite', 'Deathrite Shaman', '{B/G}', 1, 'Creature — Elf Shaman', 'BG', 'BG')"
    )
    conn.commit()
    conn.close()
    r = client.get("/api/cards", params={"exact_colors": "B,G"})
    assert _names(r) == ["Deathrite Shaman"]


def test_filter_exact_colorless(client, seed_cards):
    r = client.get("/api/cards", params={"exact_colorless": "1"})
    assert _names(r) == ["Steel Wall"]


def test_filter_color_identity_and_exact_colors_combined(client, seed_cards, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO cards (oracle_id, name, mana_cost, cmc, type_line, colors, color_identity) "
        "VALUES ('deathrite', 'Deathrite Shaman', '{B/G}', 1, 'Creature — Elf Shaman', 'BG', 'BG')"
    )
    conn.commit()
    conn.close()
    # Deathrite satisfies exact_colors=B,G but fails colors=G (identity BG is not
    # a subset of {G}); bears/ele/hydra satisfy colors=G but fail exact_colors=B,G
    # (their colors is 'G', not 'BG'). No card satisfies both filters at once, so
    # an empty result proves the two are ANDed rather than ORed.
    r = client.get("/api/cards", params={"colors": "G", "exact_colors": "B,G"})
    assert r.json() == []
