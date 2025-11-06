"""
Servidor web simple para servir el archivo feed.xml
"""
from flask import Flask, send_file, jsonify
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

app = Flask(__name__)

# Configurar logger con archivo
log_dir = Path('./logs')
log_dir.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger('WebServerLogger')
logger.setLevel(logging.INFO)

# Handler de consola con UTF-8
console_handler = logging.StreamHandler(sys.stdout)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore
except Exception:
    pass
logger.addHandler(console_handler)

# Handler de archivo con UTF-8
file_handler = RotatingFileHandler(
    log_dir / 'webserver.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(console_formatter)
logger.addHandler(file_handler)

# Directorio donde se almacenará el feed
FEED_DIR_STR = os.getenv('FEED_DIR', '/data')
FEED_DIR = Path(FEED_DIR_STR).resolve()
FEED_FILE = FEED_DIR / 'feed.xml'

@app.route('/')
def index():
    """Página de inicio con información básica"""
    return jsonify({
        'service': 'RSS Feed Server',
        'endpoints': {
            '/feed': 'RSS Feed XML',
            '/feed.xml': 'RSS Feed XML (alias)',
            '/health': 'Health check'
        }
    })

@app.route('/feed')
@app.route('/feed.xml')
def serve_feed():
    """Sirve el archivo feed.xml"""
    try:
        if FEED_FILE.exists():
            return send_file(str(FEED_FILE), mimetype='application/xml')
        else:
            logger.warning(f"Feed file not found at {FEED_FILE}")
            return jsonify({
                'error': 'Feed not found',
                'message': 'The RSS feed has not been generated yet. Please wait for the next update cycle.'
            }), 404
    except Exception as e:
        logger.error(f"Error serving feed: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    feed_exists = FEED_FILE.exists()
    feed_size = FEED_FILE.stat().st_size if feed_exists else 0
    
    return jsonify({
        'status': 'healthy' if feed_exists else 'initializing',
        'feed_exists': feed_exists,
        'feed_size': feed_size,
        'feed_path': str(FEED_FILE)
    })

if __name__ == '__main__':
    # Crear directorio de datos si no existe
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Ejecutar servidor
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
