def test_set_preferred_printing_updates_and_returns_card(client):
    new_uri = "https://cards.scryfall.io/normal/front/a/b/some-other-printing.jpg"
    r = client.post("/api/cards/1/preferred-printing", json={"image_uri": new_uri})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert body["image_uri"] == new_uri
    assert body["name"] == "Lightning Bolt"

    # Response shape matches GET /api/cards/{id}.
    get_r = client.get("/api/cards/1")
    assert get_r.status_code == 200
    assert get_r.json() == body


def test_set_preferred_printing_persists(client):
    new_uri = "https://cards.scryfall.io/normal/front/a/b/some-other-printing.jpg"
    client.post("/api/cards/1/preferred-printing", json={"image_uri": new_uri})
    r = client.get("/api/cards/1")
    assert r.json()["image_uri"] == new_uri


def test_set_preferred_printing_card_not_found(client):
    r = client.post("/api/cards/9999/preferred-printing", json={"image_uri": "https://example.com/x.jpg"})
    assert r.status_code == 404
    assert r.json() == {"detail": "Card not found"}
