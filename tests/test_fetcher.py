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
