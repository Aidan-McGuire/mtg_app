"""Scryfall rejects requests with the default httpx User-Agent (400 Bad Request),
the same way it rejects the default python-requests User-Agent (see
tests/test_importer_idempotent.py and the fix for importer.py). The image
proxy endpoint must send a real User-Agent too, or cached card images never
load.
"""
import app as app_module


class _FakeAsyncResponse:
    def __init__(self, status_code=200, content=b"fake-image-bytes"):
        self.status_code = status_code
        self.content = content


class _FakeAsyncClient:
    """Records the headers used for the outbound Scryfall image request."""
    captured_headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, timeout=None, headers=None):
        _FakeAsyncClient.captured_headers = headers
        return _FakeAsyncResponse()


def test_proxy_image_sends_user_agent_header(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "IMAGE_CACHE_DIR", tmp_path)
    monkeypatch.setattr(app_module.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.captured_headers = None

    r = client.get("/api/image", params={"url": "https://cards.scryfall.io/normal/front/a/b/test.jpg"})

    assert r.status_code == 200
    assert _FakeAsyncClient.captured_headers == {"User-Agent": "MTGApp/1.0"}
