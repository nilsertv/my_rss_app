"""
Servidor web Flask para la plataforma My RSS App:
- Frontend minimalista estilo Feedly (protegido por sesión/token).
- API REST protegida para gestionar fuentes (config.yaml + PostgreSQL) y feeds personalizados.
- Endpoints públicos de RSS (/feed.xml y /feeds/<slug>.xml) para triggers de IFTTT y lectores externos.
"""
from functools import wraps
import hmac
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import Optional
import yaml

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_file,
    session,
)

import src.config as config_mod
from src.config import (
    FEED_DIR,
    HOST,
    PORT,
    SECRET_KEY,
    get_active_yaml_path,
    get_app_config,
    load_yaml_config,
)
from src.core.fetcher import Fetcher
from src.core.rss_generator import RSSGenerator

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / 'templates'),
    static_folder=str(Path(__file__).resolve().parent / 'static'),
)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# Configuración de Logging
log_dir = Path('./logs')
log_dir.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger('WebServerLogger')
logger.setLevel(logging.INFO)

if not logger.handlers:
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

# Instancia compartida de Fetcher inicializada bajo demanda
_fetcher_instance: Optional[Fetcher] = None


def get_fetcher() -> Fetcher:
    """Obtiene o inicializa el servicio Fetcher compartido."""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = Fetcher(get_app_config())
    return _fetcher_instance


def get_admin_token() -> str:
    """Obtiene el ADMIN_TOKEN vigente."""
    import os
    return os.getenv('ADMIN_TOKEN') or config_mod.ADMIN_TOKEN


def is_request_authenticated() -> bool:
    """Verifica si la petición actual posee sesión válida o token Bearer/Header."""
    if session.get('authenticated') is True:
        return True

    expected = get_admin_token()
    if not expected:
        return False

    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        provided = auth_header[7:].strip()
        if hmac.compare_digest(provided, expected):
            return True

    header_token = request.headers.get('X-Admin-Token', '').strip()
    if header_token and hmac.compare_digest(header_token, expected):
        return True

    return False


def require_auth(f):
    """Decorador que protege todos los endpoints de lectura interna y escritura en BD/config.yaml."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_request_authenticated():
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Autenticación requerida para acceder a la API de gestión.'
            }), 401
        return f(*args, **kwargs)
    return decorated


def _public_base_url() -> str:
    """Construye la URL base pública del servidor."""
    return request.host_url.rstrip('/')


# =====================================================================
# Rutas de Interfaz y Metadatos
# =====================================================================

@app.route('/')
def index():
    """Sirve la aplicación web estilo Feedly o metadatos JSON si se solicita explícitamente."""
    if request.args.get('format') == 'json':
        return jsonify({
            'service': 'RSS Feed Server',
            'status': 'running',
            'endpoints': {
                '/feed': 'RSS Feed XML',
                '/feed.xml': 'RSS Feed XML (alias)',
                '/feeds/<slug>.xml': 'Custom Public RSS Feed XML',
                '/health': 'Health check'
            }
        })
    return render_template('index.html')


@app.route('/api/info')
def api_info():
    """Metadatos públicos básicos del servidor."""
    return jsonify({
        'service': 'RSS Feed Server',
        'status': 'running',
        'endpoints': {
            '/feed': 'RSS Feed XML',
            '/feed.xml': 'RSS Feed XML (alias)',
            '/feeds/<slug>.xml': 'Custom Public RSS Feed XML',
            '/health': 'Health check'
        }
    })


# =====================================================================
# Autenticación del Panel / API
# =====================================================================

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Retorna si la sesión actual está autenticada."""
    return jsonify({'authenticated': is_request_authenticated()})


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Valida el token de administrador e inicia sesión segura."""
    data = request.get_json(silent=True) or {}
    provided = str(data.get('token', '')).strip()
    expected = get_admin_token()

    if provided and expected and hmac.compare_digest(provided, expected):
        session['authenticated'] = True
        session.permanent = True
        return jsonify({'authenticated': True, 'message': 'Sesión iniciada correctamente.'})

    return jsonify({
        'authenticated': False,
        'error': 'Invalid token',
        'message': 'Clave de acceso incorrecta.'
    }), 401


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Cierra la sesión activa."""
    session.clear()
    return jsonify({'authenticated': False})


# =====================================================================
# Endpoints Públicos de RSS (Accesibles por IFTTT y lectores externos)
# =====================================================================

@app.route('/feed')
@app.route('/feed.xml')
def serve_feed():
    """
    Sirve el archivo feed.xml principal o genera un feed RSS dinámico al vuelo
    si se especifican parámetros de filtro (?sections=..., ?exclude=..., ?q=..., ?limit=...).
    Público para consumo directo en IFTTT y lectores RSS.
    """
    try:
        sections_param = request.args.get('sections', '').strip()
        exclude_param = request.args.get('exclude', '').strip()
        search_param = request.args.get('q', '').strip()
        limit_param = request.args.get('limit', '').strip()

        has_dynamic_filters = bool(sections_param or exclude_param or search_param or limit_param)

        if has_dynamic_filters:
            fetcher = get_fetcher()
            sections_list = [s.strip() for s in sections_param.split(',') if s.strip()] if sections_param else None
            exclude_list = [s.strip() for s in exclude_param.split(',') if s.strip()] if exclude_param else None
            limit_val = int(limit_param) if limit_param.isdigit() else 25

            posts = fetcher.query_posts(
                sections=sections_list,
                exclude_sections=exclude_list,
                search_query=search_param,
                limit=limit_val
            )
            title_suffix = f" ({', '.join(sections_list)})" if sections_list else ""
            rss_gen = RSSGenerator(
                posts,
                title=f"Latest Posts{title_suffix}",
                description="Custom filtered RSS feed.",
                feed_url=request.url
            )
            return Response(rss_gen.to_xml_bytes(), mimetype='application/xml')

        if FEED_FILE.exists():
            return send_file(
                str(FEED_FILE),
                mimetype='application/xml',
                as_attachment=False
            )

        logger.warning(f"Feed file not found at {FEED_FILE}")
        return jsonify({
            'status': 'initializing',
            'error': 'Feed not found',
            'message': 'The RSS feed has not been generated yet. Please wait for the first worker cycle.'
        }), 404
    except Exception as e:
        logger.error(f"Error serving feed: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/feeds/<slug>.xml')
@app.route('/feeds/<slug>')
def serve_custom_feed(slug: str):
    """
    Endpoint RSS público personalizado por slug (/feeds/<slug>.xml).
    Diseñado para usarse directamente como URL de trigger RSS en IFTTT u otras apps.
    """
    try:
        fetcher = get_fetcher()
        clean_slug = slug[:-4] if slug.endswith('.xml') else slug
        feed_cfg = fetcher.get_custom_feed(clean_slug)
        if not feed_cfg:
            return jsonify({
                'error': 'Custom feed not found',
                'message': f"No existe ningún feed personalizado con el identificador '{clean_slug}'."
            }), 404

        posts = fetcher.query_posts(
            sections=feed_cfg.get('sections') or None,
            exclude_sections=feed_cfg.get('exclude_sections') or None,
            search_query=feed_cfg.get('search_query') or None,
            limit=int(feed_cfg.get('max_items', 25))
        )
        rss_gen = RSSGenerator(
            posts,
            title=feed_cfg.get('name', f"Feed {clean_slug}"),
            description=f"Feed RSS público personalizado ({clean_slug})",
            feed_url=request.url
        )
        return Response(rss_gen.to_xml_bytes(), mimetype='application/xml')
    except Exception as e:
        logger.error(f"Error serving custom feed {slug}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/health')
def health():
    """Endpoint de salud para monitorización de Coolify y orquestadores."""
    feed_exists = FEED_FILE.exists()
    feed_size = FEED_FILE.stat().st_size if feed_exists else 0
    mtime = FEED_FILE.stat().st_mtime if feed_exists else None

    status = 'healthy' if feed_exists else 'initializing'

    return jsonify({
        'status': status,
        'feed_exists': feed_exists,
        'feed_size_bytes': feed_size,
        'feed_last_modified': mtime,
        'feed_path': str(FEED_FILE)
    }), 200


# =====================================================================
# API Protegida: Artículos, Fuentes (config.yaml) y Feeds Personalizados
# =====================================================================

@app.route('/api/posts', methods=['GET'])
@require_auth
def api_get_posts():
    """Lista artículos filtrados y conteos por sección para el lector estilo Feedly."""
    fetcher = get_fetcher()
    sections_param = request.args.get('sections', '') or request.args.get('section', '')
    exclude_param = request.args.get('exclude', '')
    search_query = request.args.get('q', '').strip()
    limit = int(request.args.get('limit', 40))
    offset = int(request.args.get('offset', 0))

    sections_list = [s.strip() for s in sections_param.split(',') if s.strip()] if sections_param else None
    exclude_list = [s.strip() for s in exclude_param.split(',') if s.strip()] if exclude_param else None

    posts = fetcher.query_posts(
        sections=sections_list,
        exclude_sections=exclude_list,
        search_query=search_query,
        limit=limit,
        offset=offset
    )
    counts = fetcher.get_section_counts()
    sections = sorted(list(set(list(fetcher.sections.keys()) + list(counts.keys()))))

    return jsonify({
        'posts': posts,
        'counts': counts,
        'total_articles': sum(counts.values()),
        'sections': sections
    })


@app.route('/api/sources', methods=['GET'])
@require_auth
def api_get_sources():
    """Obtiene todas las fuentes activas agrupadas y en lista."""
    fetcher = get_fetcher()
    sources = fetcher.get_sources()
    sections = sorted(list(set(list(fetcher.sections.keys()) + [s['section'] for s in sources])))
    return jsonify({
        'sources': sources,
        'sections': sections
    })


@app.route('/api/sources', methods=['POST'])
@require_auth
def api_add_source():
    """Agrega una fuente RSS/YouTube/Web a una sección y sincroniza config.yaml + PostgreSQL."""
    data = request.get_json(silent=True) or {}
    section = str(data.get('section', '')).strip()
    url = str(data.get('url', '')).strip()
    source_type = str(data.get('type', 'rss')).strip().lower()

    if not section or not url:
        return jsonify({'error': 'La sección y la URL son obligatorias.'}), 400

    try:
        fetcher = get_fetcher()
        created = fetcher.add_source(section=section, url=url, source_type=source_type)
        return jsonify({
            'source': created,
            'sources': fetcher.get_sources(),
            'message': f"Fuente agregada en '{section}' y sincronizada en config.yaml."
        }), 201
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Error adding source: {e}")
        return jsonify({'error': 'No se pudo guardar la fuente.'}), 500


@app.route('/api/sources/<int:source_id>', methods=['DELETE'])
@require_auth
def api_delete_source_by_id(source_id: int):
    """Elimina una fuente por su ID y actualiza config.yaml + PostgreSQL."""
    try:
        fetcher = get_fetcher()
        url_param = request.args.get('url', '').strip() or None
        deleted = fetcher.delete_source(source_id=source_id, url=url_param)
        if not deleted and url_param:
            deleted = fetcher.delete_source(url=url_param)
        if not deleted:
            return jsonify({'error': 'Fuente no encontrada.'}), 404
        return jsonify({
            'deleted': True,
            'sources': fetcher.get_sources(),
            'message': 'Fuente eliminada y config.yaml actualizado.'
        })
    except Exception as e:
        logger.error(f"Error deleting source {source_id}: {e}")
        return jsonify({'error': 'Error al eliminar la fuente.'}), 500


@app.route('/api/sources', methods=['DELETE'])
@require_auth
def api_delete_source_by_url():
    """Elimina una fuente por su URL."""
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or request.args.get('url') or '').strip()
    if not url:
        return jsonify({'error': 'URL requerida para eliminar.'}), 400
    fetcher = get_fetcher()
    deleted = fetcher.delete_source(url=url)
    if not deleted:
        return jsonify({'error': 'Fuente no encontrada.'}), 404
    return jsonify({
        'deleted': True,
        'sources': fetcher.get_sources(),
        'message': 'Fuente eliminada de config.yaml y base de datos.'
    })


@app.route('/api/config/yaml', methods=['GET'])
@require_auth
def api_get_yaml_config():
    """Obtiene el contenido actual de config.yaml."""
    yaml_path = get_active_yaml_path()
    raw_text = yaml_path.read_text(encoding='utf-8') if yaml_path.exists() else ''
    parsed = load_yaml_config(yaml_path)
    return jsonify({
        'yaml': raw_text,
        'parsed': parsed,
        'path': str(yaml_path)
    })


@app.route('/api/config/yaml', methods=['PUT'])
@require_auth
def api_update_yaml_config():
    """Reemplaza y sincroniza config.yaml completo desde el editor del frontend."""
    data = request.get_json(silent=True) or {}
    raw_yaml = data.get('yaml')
    if not raw_yaml or not isinstance(raw_yaml, str):
        return jsonify({'error': 'El contenido YAML es obligatorio.'}), 400

    try:
        parsed = yaml.safe_load(raw_yaml)
        if not isinstance(parsed, dict) or 'sections' not in parsed or not isinstance(parsed['sections'], dict):
            return jsonify({'error': "El YAML debe contener la clave raíz 'sections' con sus categorías."}), 400

        fetcher = get_fetcher()
        total_sources = fetcher.replace_all_sources_from_yaml(parsed)
        yaml_path = get_active_yaml_path()
        updated_text = yaml_path.read_text(encoding='utf-8') if yaml_path.exists() else raw_yaml

        return jsonify({
            'status': 'updated',
            'total_sources': total_sources,
            'yaml': updated_text,
            'sources': fetcher.get_sources(),
            'message': f'config.yaml sincronizado ({total_sources} fuentes activas).'
        })
    except yaml.YAMLError as ye:
        return jsonify({'error': f'Error de sintaxis YAML: {ye}'}), 400
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Error updating YAML config: {e}")
        return jsonify({'error': 'Error interno al actualizar config.yaml.'}), 500


@app.route('/api/custom-feeds', methods=['GET'])
@require_auth
def api_list_custom_feeds():
    """Lista los feeds públicos personalizados con sus URLs listas para IFTTT."""
    fetcher = get_fetcher()
    base = _public_base_url()
    feeds = fetcher.list_custom_feeds()
    for f in feeds:
        f['public_url'] = f"{base}/feeds/{f['slug']}.xml"
    return jsonify({'feeds': feeds})


@app.route('/api/custom-feeds', methods=['POST'])
@require_auth
def api_create_custom_feed():
    """Crea o actualiza un feed público personalizado."""
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    slug = str(data.get('slug', '') or name).strip()
    sections = data.get('sections') or []
    exclude_sections = data.get('exclude_sections') or []
    search_query = str(data.get('search_query', '')).strip()
    max_items = int(data.get('max_items', 25))

    if isinstance(sections, str):
        sections = [s.strip() for s in sections.split(',') if s.strip()]
    if isinstance(exclude_sections, str):
        exclude_sections = [s.strip() for s in exclude_sections.split(',') if s.strip()]

    try:
        fetcher = get_fetcher()
        saved = fetcher.save_custom_feed(
            name=name,
            slug=slug,
            sections=sections,
            exclude_sections=exclude_sections,
            search_query=search_query,
            max_items=max_items
        )
        base = _public_base_url()
        saved['public_url'] = f"{base}/feeds/{saved['slug']}.xml"
        return jsonify({
            'feed': saved,
            'public_url': saved['public_url'],
            'message': f"Feed público '{saved['name']}' listo para usar."
        }), 201
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.error(f"Error saving custom feed: {e}")
        return jsonify({'error': 'No se pudo guardar el feed personalizado.'}), 500


@app.route('/api/custom-feeds/<slug>', methods=['DELETE'])
@require_auth
def api_delete_custom_feed(slug: str):
    """Elimina un feed personalizado."""
    fetcher = get_fetcher()
    deleted = fetcher.delete_custom_feed(slug)
    if not deleted:
        return jsonify({'error': 'Feed no encontrado.'}), 404
    return jsonify({'deleted': True, 'message': 'Feed personalizado eliminado.'})


@app.route('/api/fetch', methods=['POST'])
@require_auth
def api_trigger_fetch():
    """Ejecuta un ciclo de actualización de fuentes RSS bajo demanda y regenera feed.xml."""
    try:
        fetcher = get_fetcher()
        new_posts = fetcher.fetch_latest()
        recent_posts = fetcher.get_recent_posts(limit=20, exclude_sections=['Youtube'])
        if not recent_posts and new_posts:
            recent_posts = [p for p in new_posts if p.get('section') != 'Youtube'][:20]

        FEED_FILE.parent.mkdir(parents=True, exist_ok=True)
        RSSGenerator(recent_posts).save_rss(filename=str(FEED_FILE))

        return jsonify({
            'status': 'ok',
            'new_posts_count': len(new_posts),
            'feed_posts_count': len(recent_posts),
            'message': f'Sincronización completada: {len(new_posts)} artículos nuevos.'
        })
    except Exception as e:
        logger.error(f"Error in manual fetch trigger: {e}")
        return jsonify({'error': f'Error al sincronizar fuentes: {e}'}), 500


def create_app():
    """Factory para tests y wsgi."""
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    return app


if __name__ == '__main__':
    FEED_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting development Flask server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT)
