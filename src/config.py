"""
Configuración centralizada para la aplicación RSS.
Maneja carga de variables de entorno y archivo YAML de secciones.
"""
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

# Configuración de red y servidor
PORT = int(os.getenv('PORT', 8080))
HOST = os.getenv('HOST', '0.0.0.0')

# Configuración de Base de Datos
DATABASE_URL = os.getenv('DATABASE_URL', '')

# Configuración de IFTTT
IFTTT_WEBHOOK_URL = os.getenv('IFTTT_WEBHOOK_URL', '')

# Parámetros operativos
INTERVAL = int(os.getenv('INTERVAL', 600))
POST_DELAY = int(os.getenv('POST_DELAY', 225))

# Mistral AI
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')


def load_yaml_config(config_path: Path = None) -> dict:
    """Carga la configuración de fuentes RSS desde config.yaml."""
    if config_path is None:
        config_path = SRC_DIR / 'config.yaml'
    
    if not config_path.exists():
        return {'sections': {}}
    
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data


def get_app_config() -> dict:
    """Retorna un diccionario unificado con la configuración completa."""
    yaml_config = load_yaml_config()
    
    return {
        'interval': int(os.getenv('INTERVAL', yaml_config.get('interval', INTERVAL))),
        'post_delay': POST_DELAY,
        'feed_dir': FEED_DIR,
        'port': PORT,
        'host': HOST,
        'database_url': DATABASE_URL,
        'ifttt_webhook_url': IFTTT_WEBHOOK_URL or yaml_config.get('ifttt_webhook_url', ''),
        'mistral_api_key': MISTRAL_API_KEY,
        'sections': yaml_config.get('sections', {})
    }
