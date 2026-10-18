"""
Servidor web Flask para servir el feed RSS generado (feed.xml) y health checks.
Compatible con Gunicorn en producción y app.run en desarrollo local.
"""
from flask import Flask, send_file, jsonify, Response
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from src.config import FEED_DIR, PORT, HOST

app = Flask(__name__)

# Configuración de Logging
log_dir = Path('./logs')
log_dir.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger('WebServerLogger')
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore
except Exception:
    pass
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    log_dir / 'webserver.log',
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(console_formatter)
logger.addHandler(file_handler)

FEED_FILE = FEED_DIR / 'feed.xml'


@app.route('/')
def index():
    """Página de inicio con metadatos del servicio y endpoints disponibles."""
    return jsonify({
        'service': 'RSS Feed Server',
        'status': 'running',
        'endpoints': {
            '/feed': 'RSS Feed XML',
            '/feed.xml': 'RSS Feed XML (alias)',
            '/health': 'Health check'
        }
    })


@app.route('/feed')
@app.route('/feed.xml')
def serve_feed():
    """Sirve el archivo feed.xml generado."""
    try:
        if FEED_FILE.exists():
            return send_file(
                str(FEED_FILE),
                mimetype='application/xml',
                as_attachment=False
            )
        else:
            logger.warning(f"Feed file not found at {FEED_FILE}")
            return jsonify({
                'status': 'initializing',
                'error': 'Feed not found',
                'message': 'The RSS feed has not been generated yet. Please wait for the first worker cycle.'
            }), 404
    except Exception as e:
        logger.error(f"Error serving feed: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/health')
def health():
    """Endpoint de salud para monitorización de Coolify y orquestadores."""
    feed_exists = FEED_FILE.exists()
    feed_size = FEED_FILE.stat().st_size if feed_exists else 0
    mtime = FEED_FILE.stat().st_mtime if feed_exists else None

    # Consideramos healthy si el servicio web responde
    status = 'healthy' if feed_exists else 'initializing'
    
    return jsonify({
        'status': status,
        'feed_exists': feed_exists,
        'feed_size_bytes': feed_size,
        'feed_last_modified': mtime,
        'feed_path': str(FEED_FILE)
    }), 200


def create_app():
    """Factory para tests y wsgi."""
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    return app


if __name__ == '__main__':
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting development Flask server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT)
