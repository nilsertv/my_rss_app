import hashlib
from bs4 import BeautifulSoup
from unittest.mock import MagicMock
from src.core.fetcher import Fetcher


def test_generate_url_hash():
    url = "https://example.com/noticia-1"
    expected = hashlib.sha256(url.encode('utf-8')).hexdigest()
    assert Fetcher.generate_url_hash(url) == expected


def test_fetcher_without_db():
    config = {'sections': {}, 'database_url': ''}
    fetcher = Fetcher(config)
    assert fetcher.pool is None
    
    # Should not crash and return empty/safe defaults
    assert fetcher.filter_existing_hashes(["hash1", "hash2"]) == set()
    assert fetcher.is_post_in_history("hash1") is False
    assert fetcher.get_recent_posts() == []
    assert fetcher.get_unsent_posts() == []
    
    # Closing a null pool should not throw
    fetcher.close()


def test_extract_image_from_html():
    config = {'sections': {}, 'database_url': ''}
    fetcher = Fetcher(config)
    
    html = '<div><p>Texto</p><img src="https://example.com/imagen.jpg" /></div>'
    soup = BeautifulSoup(html, 'html.parser')
    img = fetcher._extract_image_from_html(soup, "https://example.com")
    assert img == "https://example.com/imagen.jpg"
    
    html_no_img = '<div><p>Texto sin imagen</p></div>'
    soup_no_img = BeautifulSoup(html_no_img, 'html.parser')
    assert fetcher._extract_image_from_html(soup_no_img, "https://example.com") is None


def test_extract_image_from_rss():
    config = {'sections': {}, 'database_url': ''}
    fetcher = Fetcher(config)
    
    # Mock media_content
    entry = MagicMock()
    entry.media_content = [{'url': 'https://example.com/media.jpg'}]
    entry.media_thumbnail = []
    entry.enclosures = []
    assert fetcher._extract_image_from_rss(entry) == 'https://example.com/media.jpg'
    
    # Mock media_thumbnail
    entry2 = MagicMock()
    entry2.media_content = []
    entry2.media_thumbnail = [{'url': 'https://example.com/thumb.jpg'}]
    entry2.enclosures = []
    assert fetcher._extract_image_from_rss(entry2) == 'https://example.com/thumb.jpg'


def _fake_get(monkeypatch, body):
    from src.core import fetcher as fetcher_module

    calls = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def raise_for_status(self):
            pass

        headers = {}
        is_redirect = False

        def __init__(self):
            chunks = iter([body])
            self.raw = type("Raw", (), {"read1": lambda _s, n: next(chunks, b"")})()

    def fake_get(url, **kwargs):
        calls.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(fetcher_module._session, "get", fake_get)
    return fetcher_module.Fetcher, calls


def test_parse_feed_uses_timeout(monkeypatch):
    body = b"<rss version='2.0'><channel><title>t</title></channel></rss>"
    fetcher_cls, calls = _fake_get(monkeypatch, body)
    feed = fetcher_cls._parse_feed("http://example.com/feed")
    assert calls["timeout"] == 10
    assert feed.feed.title == "t"


def test_parse_feed_does_not_open_local_paths(monkeypatch, tmp_path):
    local = tmp_path / "secret.xml"
    local.write_text("<rss version='2.0'><channel><title>LOCAL</title></channel></rss>")
    fetcher_cls, _ = _fake_get(monkeypatch, str(local).encode())
    feed = fetcher_cls._parse_feed("http://example.com/feed")
    assert feed.feed.get("title") != "LOCAL"


def test_parse_feed_rejects_oversized(monkeypatch):
    import pytest

    fetcher_cls, _ = _fake_get(monkeypatch, b"x" * 100)
    with pytest.raises(ValueError):
        fetcher_cls._parse_feed("http://example.com/feed", max_bytes=10)


def test_parse_feed_rejects_compressed(monkeypatch):
    import pytest

    fetcher_cls, calls = _fake_get(monkeypatch, b"x")
    from src.core import fetcher as fetcher_module

    orig = fetcher_module._session.get

    def gz_get(url, **kw):
        r = orig(url, **kw)
        r.headers = {"Content-Encoding": "gzip"}
        return r

    monkeypatch.setattr(fetcher_module._session, "get", gz_get)
    with pytest.raises(ValueError):
        fetcher_cls._parse_feed("http://example.com/feed")
    assert calls["headers"]["Accept-Encoding"] == "identity"


def test_parse_feed_follows_redirects_without_reading_body(monkeypatch):
    import pytest
    from src.core import fetcher as fetcher_module

    body = b"<rss version='2.0'><channel><title>final</title></channel></rss>"
    fetcher_cls, calls = _fake_get(monkeypatch, body)
    orig = fetcher_module._session.get
    seen = []

    def redirect_get(url, **kw):
        r = orig(url, **kw)
        seen.append(url)
        if url.endswith("/old"):
            r.is_redirect = True
            r.headers = {"Location": "/new"}
        return r

    monkeypatch.setattr(fetcher_module._session, "get", redirect_get)
    feed = fetcher_cls._parse_feed("http://example.com/old")
    assert seen == ["http://example.com/old", "http://example.com/new"]
    assert calls["allow_redirects"] is False
    assert feed.feed.title == "final"

    def bad_scheme(url, **kw):
        r = orig(url, **kw)
        r.is_redirect = True
        r.headers = {"Location": "file:///etc/passwd"}
        return r

    monkeypatch.setattr(fetcher_module._session, "get", bad_scheme)
    with pytest.raises(ValueError):
        fetcher_cls._parse_feed("http://example.com/old")


def test_check_public_ip_blocks_internal_addresses():
    import pytest
    from src.core.fetcher import _check_public_ip

    for ip in ["127.0.0.1", "10.0.0.5", "172.17.0.2", "192.168.1.1", "169.254.169.254",
               "::1", "::ffff:127.0.0.1", "fe80::1", "0.0.0.0", "224.0.0.1"]:
        with pytest.raises(ValueError):
            _check_public_ip(ip)
    _check_public_ip("8.8.8.8")


def test_parse_feed_blocks_loopback_server():
    import http.server
    import threading
    import pytest
    from src.core.fetcher import Fetcher

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<rss version='2.0'><channel><title>x</title></channel></rss>")

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with pytest.raises(ValueError, match="Blocked non-public"):
            Fetcher._parse_feed(f"http://127.0.0.1:{srv.server_port}/")
    finally:
        srv.shutdown()


def _post(i, ts):
    return {"id": i, "url": f"http://x/{i}", "title": f"t{i}", "timestamp": ts}


def test_merge_feed_posts_keeps_picks_dedupes_and_sorts():
    from src.core.fetcher import merge_feed_posts

    picks = [_post(1, "2026-01-01"), _post(2, "2026-01-05")]
    rules = [_post(2, "2026-01-05"), _post(3, "2026-01-09"), _post(4, "2026-01-08")]
    merged = merge_feed_posts(picks, rules, max_items=3, has_rules=True)
    assert [p["id"] for p in merged] == [3, 2, 1]  # 2 not duplicated; rules fill only the free slot


def test_merge_feed_posts_never_drops_picks_over_limit():
    from src.core.fetcher import merge_feed_posts

    picks = [_post(i, f"2026-01-0{i}") for i in range(1, 5)]
    merged = merge_feed_posts(picks, [_post(9, "2026-02-01")], max_items=2, has_rules=True)
    assert sorted(p["id"] for p in merged) == [1, 2, 3, 4]


def test_merge_feed_posts_without_rules_serves_only_picks():
    from src.core.fetcher import merge_feed_posts

    merged = merge_feed_posts([_post(1, "2026-01-01")], [_post(2, "2026-01-02")], max_items=25, has_rules=False)
    assert [p["id"] for p in merged] == [1]


def test_get_feed_posts_manual_serves_only_picks(monkeypatch):
    from src.core.fetcher import Fetcher

    fetcher = Fetcher({"sections": {}, "database_url": ""})
    monkeypatch.setattr(fetcher, "get_picks", lambda slug: [_post(1, "2026-01-01")])
    monkeypatch.setattr(fetcher, "query_posts", lambda **kw: [_post(2, "2026-01-02")])
    manual = fetcher.get_feed_posts({"slug": "p", "max_items": 25, "manual": True})
    hybrid = fetcher.get_feed_posts({"slug": "p", "max_items": 25, "manual": False})
    assert [p["id"] for p in manual] == [1]
    assert [p["id"] for p in hybrid] == [2, 1]
