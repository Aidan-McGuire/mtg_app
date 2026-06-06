def test_collection_returns_collection_tags_field(client):
    r = client.get("/api/collection")
    assert r.status_code == 200
    cards = r.json()
    assert len(cards) == 1
    assert "collection_tags" in cards[0]
    assert cards[0]["collection_tags"] == []
