def test_list_decks_includes_built_field_default_false(client):
    r = client.get("/api/decks")
    assert r.status_code == 200
    deck = next(d for d in r.json() if d["id"] == 1)
    assert deck["built"] is False


def test_patch_deck_sets_built_true(client):
    r = client.patch("/api/decks/1", json={"built": True})
    assert r.status_code == 200
    assert r.json()["built"] is True

    r2 = client.get("/api/decks")
    deck = next(d for d in r2.json() if d["id"] == 1)
    assert deck["built"] is True


def test_patch_deck_built_true_then_false(client):
    client.patch("/api/decks/1", json={"built": True})
    r = client.patch("/api/decks/1", json={"built": False})
    assert r.status_code == 200
    assert r.json()["built"] is False


def test_patch_deck_name_only_does_not_reset_built(client):
    client.patch("/api/decks/1", json={"built": True})
    r = client.patch("/api/decks/1", json={"name": "Renamed Deck"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed Deck"
    assert r.json()["built"] is True


def test_patch_deck_built_only_does_not_reset_name(client):
    r = client.patch("/api/decks/1", json={"built": True})
    assert r.status_code == 200
    assert r.json()["name"] == "Test Deck"


def test_patch_nonexistent_deck_404(client):
    r = client.patch("/api/decks/9999", json={"built": True})
    assert r.status_code == 404
