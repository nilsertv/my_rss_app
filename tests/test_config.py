import os
from pathlib import Path
from src.config import get_app_config, load_yaml_config


def test_load_yaml_config():
    config = load_yaml_config()
    assert isinstance(config, dict)
    assert 'sections' in config
    assert isinstance(config['sections'], dict)


def test_get_app_config_defaults():
    config = get_app_config()
    assert 'interval' in config
    assert 'feed_dir' in config
    assert 'port' in config
    assert isinstance(config['interval'], int)
    assert isinstance(config['port'], int)


def test_config_env_override(monkeypatch):
    monkeypatch.setenv('PORT', '9090')
    monkeypatch.setenv('INTERVAL', '300')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://test:test@localhost:5432/testdb')
    
    # Reload or fetch updated config
    import importlib
    import src.config
    importlib.reload(src.config)
    
    cfg = src.config.get_app_config()
    assert cfg['port'] == 9090
    assert cfg['interval'] == 300
    assert cfg['database_url'] == 'postgresql://test:test@localhost:5432/testdb'
