import pytest
from pathlib import Path
from src.webserver import app, FEED_FILE
import src.webserver as webserver_mod
import src.config as config_mod
from src.core.fetcher import Fetcher


@pytest.fixture
def client(tmp_path, monkeypatch):
    test_feed = tmp_path / "feed.xml"
    test_yaml = tmp_path / "config.yaml"
    test_yaml.write_text(
        "interval: 600\nlog_file: app.log\nsections:\n  Actualidad:\n    - https://example.com/rss.xml\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(webserver_mod, 'FEED_FILE', test_feed)
    monkeypatch.setattr(config_mod, 'FEED_DIR', tmp_path)
    monkeypatch.setattr(config_mod, 'PERSISTENT_YAML_PATH', test_yaml)
    monkeypatch.setattr(config_mod, 'DEFAULT_YAML_PATH', test_yaml)
    monkeypatch.setattr(config_mod, 'ADMIN_TOKEN', 'test-secret-token')
    monkeypatch.setenv('ADMIN_TOKEN', 'test-secret-token')

    test_fetcher = Fetcher({
        'sections': {'Actualidad': ['https://example.com/rss.xml']},
        'database_url': '',
        'feed_dir': tmp_path
    })
    monkeypatch.setattr(webserver_mod, '_fetcher_instance', test_fetcher)

    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client, test_feed


def test_index_endpoint_returns_html_and_json_format(client):
    test_client, _ = client
    # Default GET / serves the Feedly-like HTML interface
    response_html = test_client.get('/')
    assert response_html.status_code == 200
    assert 'text/html' in response_html.content_type
    assert b"Pulse" in response_html.data

    # GET /?format=json and GET /api/info return service metadata
    response_json = test_client.get('/?format=json')
    assert response_json.status_code == 200
    data = response_json.get_json()
    assert data['service'] == 'RSS Feed Server'
    assert '/feed' in data['endpoints']
    assert '/feeds/<slug>.xml' in data['endpoints']
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


def test_protected_endpoints_reject_unauthenticated_requests(client):
    test_client, _ = client
    assert test_client.get('/api/posts').status_code == 401
    assert test_client.get('/api/sources').status_code == 401
    assert test_client.post('/api/sources', json={'section': 'Tech', 'url': 'https://a.com/rss'}).status_code == 401
    assert test_client.put('/api/config/yaml', json={'yaml': 'sections: {}'}).status_code == 401
    assert test_client.post('/api/custom-feeds', json={'name': 'My Feed'}).status_code == 401


def test_login_and_manage_sources_and_yaml(client):
    test_client, _ = client
    # Invalid token fails
    bad_login = test_client.post('/api/auth/login', json={'token': 'wrong'})
    assert bad_login.status_code == 401

    # Valid token logs in via session cookie
    ok_login = test_client.post('/api/auth/login', json={'token': 'test-secret-token'})
    assert ok_login.status_code == 200
    assert ok_login.get_json()['authenticated'] is True

    # Add source dynamically
    add_res = test_client.post('/api/sources', json={
        'section': 'Tecnología',
        'url': 'https://tech.example.com/feed.xml'
    })
    assert add_res.status_code == 201
    sources = add_res.get_json()['sources']
    assert any(s['url'] == 'https://tech.example.com/feed.xml' and s['section'] == 'Tecnología' for s in sources)

    # Delete source by URL
    del_res = test_client.delete('/api/sources', json={'url': 'https://tech.example.com/feed.xml'})
    assert del_res.status_code == 200
    assert not any(s['url'] == 'https://tech.example.com/feed.xml' for s in del_res.get_json()['sources'])

    # Update full config.yaml via PUT
    new_yaml = (
        "interval: 600\n"
        "sections:\n"
        "  Ciencia:\n"
        "    - https://ciencia.example.com/rss\n"
    )
    yaml_res = test_client.put('/api/config/yaml', json={'yaml': new_yaml})
    assert yaml_res.status_code == 200
    assert yaml_res.get_json()['total_sources'] == 1


def test_custom_feed_creation_requires_auth_but_public_xml_is_open(client):
    test_client, _ = client
    headers = {'Authorization': 'Bearer test-secret-token'}

    create_res = test_client.post(
        '/api/custom-feeds',
        headers=headers,
        json={
            'name': 'IFTTT Policiales',
            'slug': 'ifttt-policiales',
            'sections': ['Policiales', 'Actualidad'],
            'max_items': 15
        }
    )
    assert create_res.status_code == 201
    feed_info = create_res.get_json()
    assert feed_info['feed']['slug'] == 'ifttt-policiales'
    assert feed_info['public_url'].endswith('/feeds/ifttt-policiales.xml')

    # Now access the public custom RSS XML WITHOUT any authentication headers/cookies
    test_client.post('/api/auth/logout')
    public_xml_res = test_client.get('/feeds/ifttt-policiales.xml')
    assert public_xml_res.status_code == 200
    assert 'application/xml' in public_xml_res.content_type
    assert b"<title>IFTTT Policiales</title>" in public_xml_res.data
    assert b"<rss" in public_xml_res.data

