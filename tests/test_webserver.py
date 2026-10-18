import pytest
from pathlib import Path
from src.webserver import app, FEED_FILE
import src.webserver as webserver_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_feed = tmp_path / "feed.xml"
    monkeypatch.setattr(webserver_mod, 'FEED_FILE', test_feed)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client, test_feed


def test_index_endpoint(client):
    test_client, _ = client
    response = test_client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert data['service'] == 'RSS Feed Server'
    assert '/feed' in data['endpoints']
    assert '/health' in data['endpoints']


def test_health_endpoint_when_feed_missing(client):
    test_client, test_feed = client
    if test_feed.exists():
        test_feed.unlink()
    
    response = test_client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'initializing'
    assert data['feed_exists'] is False


def test_health_endpoint_when_feed_exists(client):
    test_client, test_feed = client
    test_feed.write_text("<rss></rss>", encoding='utf-8')
    
    response = test_client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['feed_exists'] is True
    assert data['feed_size_bytes'] > 0


def test_feed_endpoint_404_when_missing(client):
    test_client, test_feed = client
    if test_feed.exists():
        test_feed.unlink()
    
    response = test_client.get('/feed')
    assert response.status_code == 404
    data = response.get_json()
    assert data['error'] == 'Feed not found'


def test_feed_endpoint_200_when_present(client):
    test_client, test_feed = client
    content = '<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title></channel></rss>'
    test_feed.write_text(content, encoding='utf-8')
    
    response = test_client.get('/feed')
    assert response.status_code == 200
    assert 'application/xml' in response.content_type
    assert b"<title>Test</title>" in response.data
    
    # Test alias /feed.xml
    response_alias = test_client.get('/feed.xml')
    assert response_alias.status_code == 200
    assert b"<title>Test</title>" in response_alias.data
