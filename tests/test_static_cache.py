"""Static assets must always be revalidated.

Without a Cache-Control header, a browser may serve a stale app.js against a
freshly-fetched index.html — the page renders new markup whose event handlers
were never registered, so buttons silently do nothing.
"""


def test_app_js_is_revalidated(client):
    r = client.get("/app.js")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"


def test_index_is_revalidated(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"


def test_style_css_is_revalidated(client):
    r = client.get("/style.css")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"


def test_etag_still_allows_304(client):
    """no-cache means revalidate, not re-download: unchanged files return 304."""
    first = client.get("/app.js")
    etag = first.headers["etag"]
    second = client.get("/app.js", headers={"If-None-Match": etag})
    assert second.status_code == 304
