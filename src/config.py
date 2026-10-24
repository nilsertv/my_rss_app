"""
Configuración centralizada para la aplicación RSS.
Maneja carga de variables de entorno, autenticación y archivo YAML de secciones.
"""
import hashlib
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

# Cargar variables de entorno desde .env si existe
load_dotenv()

# Rutas base
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = Path(__file__).resolve().parent

# Configuración de almacenamiento
FEED_DIR = Path(os.getenv('FEED_DIR', '/data' if os.path.exists('/data') else str(BASE_DIR / 'data'))).resolve()
DEFAULT_YAML_PATH = SRC_DIR / 'config.yaml'
PERSISTENT_YAML_PATH = FEED_DIR / 'config.yaml'

# Configuración de red y servidor
PORT = int(os.getenv('PORT', 8080))
HOST = os.getenv('HOST', '0.0.0.0')
APP_URL = os.getenv('APP_URL', 'https://my-rss-app.local')

# Configuración de Base de Datos
DATABASE_URL = os.getenv('DATABASE_URL', '')

# Configuración de IFTTT
IFTTT_WEBHOOK_URL = os.getenv('IFTTT_WEBHOOK_URL', '')

# Parámetros operativos
INTERVAL = int(os.getenv('INTERVAL', 600))
POST_DELAY = int(os.getenv('POST_DELAY', 225))

# Seguridad y Autenticación del Panel/API
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'rss-admin-2026')
SECRET_KEY = os.getenv('SECRET_KEY') or hashlib.sha256(
    f"my-rss-app-session:{ADMIN_TOKEN}:{DATABASE_URL}".encode('utf-8')
).hexdigest()


def get_active_yaml_path() -> Path:
    """Retorna la ruta activa de config.yaml priorizando el volumen persistente si ya existe."""
    if PERSISTENT_YAML_PATH.exists():
        return PERSISTENT_YAML_PATH
    return DEFAULT_YAML_PATH


def load_yaml_config(config_path: Path = None) -> dict:
    """Carga la configuración de fuentes RSS desde config.yaml."""
    if config_path is None:
        config_path = get_active_yaml_path()

    if not config_path.exists():
        return {'interval': INTERVAL, 'log_file': 'app.log', 'sections': {}}

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if 'sections' not in data or not isinstance(data.get('sections'), dict):
        data['sections'] = {}
    return data


def save_yaml_config(data: dict) -> None:
    """Guarda la configuración YAML de forma persistente en FEED_DIR y sincroniza SRC_DIR."""
    normalized = {
        'interval': int(data.get('interval', INTERVAL)),
        'log_file': data.get('log_file', 'app.log'),
        'sections': data.get('sections', {})
    }
    yaml_text = yaml.safe_dump(
        normalized,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False
    )

    try:
        FEED_DIR.mkdir(parents=True, exist_ok=True)
        with open(PERSISTENT_YAML_PATH, 'w', encoding='utf-8') as f:
            f.write(yaml_text)
    except Exception:
        pass

    try:
        with open(DEFAULT_YAML_PATH, 'w', encoding='utf-8') as f:
            f.write(yaml_text)
    except Exception:
        pass


def get_app_config() -> dict:
    """Retorna un diccionario unificado con la configuración completa."""
    yaml_config = load_yaml_config()

    return {
        'interval': int(os.getenv('INTERVAL', yaml_config.get('interval', INTERVAL))),
        'post_delay': POST_DELAY,
        'feed_dir': FEED_DIR,
        'port': PORT,
        'host': HOST,
        'app_url': APP_URL,
        'database_url': DATABASE_URL,
        'ifttt_webhook_url': IFTTT_WEBHOOK_URL or yaml_config.get('ifttt_webhook_url', ''),
        'admin_token': ADMIN_TOKEN,
        'sections': yaml_config.get('sections', {})
    }
