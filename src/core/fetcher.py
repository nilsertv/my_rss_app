import os
import json
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from psycopg2 import sql, extras, pool
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from src.utils.logger import setup_logger
import src.config as config_mod
from src.config import load_yaml_config, save_yaml_config, INTERVAL


def _normalize_source_item(item: Any) -> Optional[Dict[str, str]]:
    """Convierte un ítem de sección (str o dict) al formato {'url': ..., 'type': ...}."""
    if isinstance(item, str) and item.strip():
        return {'url': item.strip(), 'type': 'rss'}
    if isinstance(item, dict) and item.get('url'):
        url = str(item['url']).strip()
        stype = str(item.get('type', 'rss')).strip().lower()
        if stype not in ('rss', 'youtube', 'web'):
            stype = 'rss'
        if url:
            return {'url': url, 'type': stype}
    return None


def _normalize_sections_map(sections_raw: Any) -> Dict[str, List[Dict[str, str]]]:
    """Normaliza un diccionario de secciones aceptando tanto listas de strings como listas de dicts."""
    normalized: Dict[str, List[Dict[str, str]]] = {}
    if not isinstance(sections_raw, dict):
        return normalized
    for section, items in sections_raw.items():
        sec_name = str(section).strip()
        if not sec_name or not isinstance(items, list):
            continue
        norm_list = []
        for item in items:
            parsed = _normalize_source_item(item)
            if parsed:
                norm_list.append(parsed)
        if norm_list:
            normalized[sec_name] = norm_list
    return normalized


class Fetcher:
    def __init__(self, config: Dict[str, Any]):
        self.logger = setup_logger(name='FetcherLogger', log_file='fetcher.log')
        self.feed_dir = config.get('feed_dir')
        raw_sections = config.get('sections') or load_yaml_config().get('sections', {})
        self.sections: Dict[str, List[Dict[str, str]]] = _normalize_sections_map(raw_sections)

        self.connection_url = (
            os.environ.get('DATABASE_URL')
            or config.get('database', {}).get('connection_url')
            or config.get('database_url', '')
        )
        self.pool: Optional[pool.ThreadedConnectionPool] = None

        if self.connection_url and not self.connection_url.startswith("${"):
            try:
                self.pool = pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=self.connection_url)
                self.init_db()
                self.logger.info("Database connection pool initialized successfully.")
            except Exception as e:
                self.logger.error(f"Failed to initialize database connection pool: {e}")
                self.pool = None
        else:
            self.logger.warning("DATABASE_URL not configured or invalid. Database features disabled.")

    @contextmanager
    def get_connection(self):
        """Context manager para adquirir y devolver conexiones del pool de forma segura."""
        if not self.pool:
            raise RuntimeError("Database pool not available.")
        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    def close(self):
        """Cierra el pool de conexiones."""
        if self.pool:
            try:
                self.pool.closeall()
                self.logger.info("Database pool closed.")
            except Exception as e:
                self.logger.error(f"Error closing database pool: {e}")

    def init_db(self):
        """Crea tablas e índices de historial, fuentes dinámicas y feeds personalizados."""
        if not self.pool:
            return
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS rss_history (
                            id SERIAL PRIMARY KEY,
                            url TEXT UNIQUE NOT NULL,
                            url_hash TEXT UNIQUE NOT NULL,
                            title TEXT,
                            content TEXT,
                            section TEXT,
                            image_url TEXT,
                            sent_to_ifttt BOOLEAN DEFAULT FALSE,
                            timestamp TIMESTAMPTZ DEFAULT NOW()
                        )
                    ''')

                    cursor.execute('''
                        CREATE INDEX IF NOT EXISTS idx_rss_history_timestamp_desc 
                        ON rss_history (timestamp DESC)
                    ''')
                    cursor.execute('''
                        CREATE INDEX IF NOT EXISTS idx_rss_history_section_timestamp 
                        ON rss_history (section, timestamp DESC)
                    ''')
                    cursor.execute('''
                        CREATE INDEX IF NOT EXISTS idx_rss_history_sent_to_ifttt 
                        ON rss_history (sent_to_ifttt, timestamp DESC)
                    ''')

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS rss_sources (
                            id SERIAL PRIMARY KEY,
                            section TEXT NOT NULL,
                            url TEXT UNIQUE NOT NULL,
                            type TEXT NOT NULL DEFAULT 'rss',
                            enabled BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        )
                    ''')

                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS custom_feeds (
                            id SERIAL PRIMARY KEY,
                            slug TEXT UNIQUE NOT NULL,
                            name TEXT NOT NULL,
                            sections TEXT DEFAULT '',
                            exclude_sections TEXT DEFAULT '',
                            search_query TEXT DEFAULT '',
                            max_items INTEGER DEFAULT 25,
                            created_at TIMESTAMPTZ DEFAULT NOW()
                        )
                    ''')
                    conn.commit()

                    # Sembrar rss_sources desde config.yaml si la tabla está vacía
                    cursor.execute("SELECT COUNT(1) FROM rss_sources")
                    row = cursor.fetchone()
                    count = row[0] if row else 0
                    if count == 0 and self.sections:
                        seed_rows = []
                        for section, items in self.sections.items():
                            for item in items or []:
                                if item.get('url'):
                                    seed_rows.append((
                                        section,
                                        item['url'].strip(),
                                        item.get('type', 'rss').strip()
                                    ))
                        if seed_rows:
                            extras.execute_values(
                                cursor,
                                sql.SQL("""
                                    INSERT INTO rss_sources (section, url, type)
                                    VALUES %s
                                    ON CONFLICT (url) DO NOTHING
                                """),
                                seed_rows
                            )
                            conn.commit()
                            self.logger.info(f"Seeded {len(seed_rows)} sources from config.yaml into rss_sources.")

            self.reload_sections_from_db()
        except Exception as e:
            self.logger.error(f"Error initializing database schema: {e}")

    def reload_sections_from_db(self) -> Dict[str, List[Dict[str, str]]]:
        """Recarga el diccionario de secciones desde la tabla rss_sources o desde config.yaml si no hay BD."""
        if not self.pool:
            self.sections = _normalize_sections_map(load_yaml_config().get('sections', {}))
            return self.sections

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT section, url, type
                        FROM rss_sources
                        WHERE enabled = TRUE
                        ORDER BY section ASC, id ASC
                    """)
                    rows = cursor.fetchall()
                    grouped: Dict[str, List[Dict[str, str]]] = {}
                    for section, url, stype in rows:
                        grouped.setdefault(section, []).append({'url': url, 'type': stype})
                    if grouped:
                        self.sections = grouped
                    return self.sections
        except Exception as e:
            self.logger.error(f"Error reloading sections from DB: {e}")
            return self.sections

    def _sync_sections_to_yaml(self, interval: int = None):
        """Sincroniza el estado actual de self.sections hacia config.yaml."""
        current_yaml = load_yaml_config()
        save_yaml_config({
            'interval': interval or current_yaml.get('interval', INTERVAL),
            'log_file': current_yaml.get('log_file', 'app.log'),
            'sections': self.sections
        })

    def get_sources(self) -> List[Dict[str, Any]]:
        """Obtiene la lista completa de fuentes configuradas."""
        if self.pool:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT id, section, url, type, enabled, created_at
                            FROM rss_sources
                            ORDER BY section ASC, id ASC
                        """)
                        rows = cursor.fetchall()
                        return [
                            {
                                'id': r[0],
                                'section': r[1],
                                'url': r[2],
                                'type': r[3],
                                'enabled': r[4],
                                'created_at': r[5].isoformat() if hasattr(r[5], 'isoformat') else str(r[5])
                            }
                            for r in rows
                        ]
            except Exception as e:
                self.logger.error(f"Error getting sources from DB: {e}")

        # Fallback desde YAML
        sources = []
        idx = 1
        sections_map = _normalize_sections_map(load_yaml_config().get('sections', {}))
        for section, items in sections_map.items():
            for item in items or []:
                sources.append({
                    'id': idx,
                    'section': section,
                    'url': item.get('url', ''),
                    'type': item.get('type', 'rss'),
                    'enabled': True,
                    'created_at': None
                })
                idx += 1
        return sources

    def add_source(self, section: str, url: str, source_type: str = 'rss') -> Dict[str, Any]:
        """Agrega o actualiza una fuente en la base de datos y en config.yaml."""
        section = (section or '').strip()
        url = (url or '').strip()
        source_type = (source_type or 'rss').strip().lower()
        if not section or not url:
            raise ValueError("Section and URL are required.")
        if source_type not in ('rss', 'youtube', 'web'):
            raise ValueError("Invalid source type. Must be 'rss', 'youtube', or 'web'.")

        created_id = None
        if self.pool:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO rss_sources (section, url, type, enabled)
                        VALUES (%s, %s, %s, TRUE)
                        ON CONFLICT (url) DO UPDATE
                        SET section = EXCLUDED.section,
                            type = EXCLUDED.type,
                            enabled = TRUE
                        RETURNING id
                    """, (section, url, source_type))
                    row = cursor.fetchone()
                    created_id = row[0] if row else None
                    conn.commit()
            self.reload_sections_from_db()
        else:
            yaml_cfg = load_yaml_config()
            sections_map = _normalize_sections_map(yaml_cfg.get('sections', {}))
            for sec, items in list(sections_map.items()):
                sections_map[sec] = [i for i in (items or []) if i.get('url') != url]
            sections_map.setdefault(section, []).append({'url': url, 'type': source_type})
            self.sections = {k: v for k, v in sections_map.items() if v}

        self._sync_sections_to_yaml()
        return {'id': created_id, 'section': section, 'url': url, 'type': source_type, 'enabled': True}

    def delete_source(self, source_id: Optional[int] = None, url: Optional[str] = None) -> bool:
        """Elimina una fuente por ID o URL tanto de la base de datos como de config.yaml."""
        deleted = False
        if self.pool:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if source_id is not None:
                        cursor.execute("DELETE FROM rss_sources WHERE id = %s", (source_id,))
                    elif url:
                        cursor.execute("DELETE FROM rss_sources WHERE url = %s", (url,))
                    deleted = cursor.rowcount > 0
                    conn.commit()
            self.reload_sections_from_db()
        else:
            yaml_cfg = load_yaml_config()
            sections_map = _normalize_sections_map(yaml_cfg.get('sections', {}))
            idx = 1
            new_sections: Dict[str, List[Dict[str, str]]] = {}
            for sec, items in sections_map.items():
                kept = []
                for item in items or []:
                    match_id = (source_id is not None and idx == source_id)
                    match_url = (url is not None and item.get('url') == url)
                    if match_id or match_url:
                        deleted = True
                    else:
                        kept.append(item)
                    idx += 1
                if kept:
                    new_sections[sec] = kept
            self.sections = new_sections

        if deleted:
            self._sync_sections_to_yaml()
        return deleted

    def replace_all_sources_from_yaml(self, yaml_data: Dict[str, Any]) -> int:
        """Reemplaza todas las fuentes desde un diccionario YAML validado y sincroniza BD + archivo."""
        if not isinstance(yaml_data, dict) or 'sections' not in yaml_data or not isinstance(yaml_data['sections'], dict):
            raise ValueError("Invalid YAML structure: 'sections' dictionary is required.")

        cleaned_sections = _normalize_sections_map(yaml_data['sections'])
        flat_rows = [
            (sec_name, item['url'], item['type'])
            for sec_name, items in cleaned_sections.items()
            for item in items
        ]

        if self.pool:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM rss_sources")
                    if flat_rows:
                        extras.execute_values(
                            cursor,
                            sql.SQL("""
                                INSERT INTO rss_sources (section, url, type)
                                VALUES %s
                                ON CONFLICT (url) DO NOTHING
                            """),
                            flat_rows
                        )
                    conn.commit()

        self.sections = cleaned_sections
        interval = int(yaml_data.get('interval', INTERVAL))
        self._sync_sections_to_yaml(interval=interval)
        return len(flat_rows)

    # --- Custom Feeds Management ---

    def _custom_feeds_fallback_file(self):
        from pathlib import Path
        target_dir = Path(self.feed_dir) if self.feed_dir else config_mod.FEED_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / 'custom_feeds.json'

    def list_custom_feeds(self) -> List[Dict[str, Any]]:
        """Lista todos los feeds personalizados creados."""
        if self.pool:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            SELECT id, slug, name, sections, exclude_sections, search_query, max_items, created_at
                            FROM custom_feeds
                            ORDER BY created_at DESC
                        """)
                        rows = cursor.fetchall()
                        return [
                            {
                                'id': r[0],
                                'slug': r[1],
                                'name': r[2],
                                'sections': [s for s in (r[3] or '').split(',') if s],
                                'exclude_sections': [s for s in (r[4] or '').split(',') if s],
                                'search_query': r[5] or '',
                                'max_items': r[6] or 25,
                                'created_at': r[7].isoformat() if hasattr(r[7], 'isoformat') else str(r[7])
                            }
                            for r in rows
                        ]
            except Exception as e:
                self.logger.error(f"Error listing custom feeds: {e}")

        fb = self._custom_feeds_fallback_file()
        if fb.exists():
            try:
                return json.loads(fb.read_text(encoding='utf-8'))
            except Exception:
                return []
        return []

    def get_custom_feed(self, slug: str) -> Optional[Dict[str, Any]]:
        """Obtiene la definición de un feed personalizado por su slug."""
        slug = (slug or '').strip().lower()
        for f in self.list_custom_feeds():
            if f.get('slug') == slug:
                return f
        return None

    def save_custom_feed(
        self,
        name: str,
        slug: str,
        sections: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        search_query: str = '',
        max_items: int = 25
    ) -> Dict[str, Any]:
        """Crea o actualiza un feed público personalizado."""
        import re
        name = (name or '').strip()
        slug = re.sub(r'[^a-z0-9-]+', '-', (slug or name).strip().lower()).strip('-')
        if not name or not slug:
            raise ValueError("Feed name and valid slug are required.")

        sections_list = [s.strip() for s in (sections or []) if s and s.strip()]
        exclude_list = [s.strip() for s in (exclude_sections or []) if s and s.strip()]
        search_query = (search_query or '').strip()
        max_items = max(1, min(int(max_items or 25), 100))

        if self.pool:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO custom_feeds (slug, name, sections, exclude_sections, search_query, max_items)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (slug) DO UPDATE
                        SET name = EXCLUDED.name,
                            sections = EXCLUDED.sections,
                            exclude_sections = EXCLUDED.exclude_sections,
                            search_query = EXCLUDED.search_query,
                            max_items = EXCLUDED.max_items
                        RETURNING id, created_at
                    """, (
                        slug,
                        name,
                        ','.join(sections_list),
                        ','.join(exclude_list),
                        search_query,
                        max_items
                    ))
                    row = cursor.fetchone()
                    conn.commit()
                    return {
                        'id': row[0] if row else None,
                        'slug': slug,
                        'name': name,
                        'sections': sections_list,
                        'exclude_sections': exclude_list,
                        'search_query': search_query,
                        'max_items': max_items,
                        'created_at': row[1].isoformat() if row and hasattr(row[1], 'isoformat') else None
                    }

        # Fallback a archivo JSON
        feeds = [f for f in self.list_custom_feeds() if f.get('slug') != slug]
        entry = {
            'id': len(feeds) + 1,
            'slug': slug,
            'name': name,
            'sections': sections_list,
            'exclude_sections': exclude_list,
            'search_query': search_query,
            'max_items': max_items,
            'created_at': datetime.now().isoformat()
        }
        feeds.insert(0, entry)
        self._custom_feeds_fallback_file().write_text(json.dumps(feeds, ensure_ascii=False, indent=2), encoding='utf-8')
        return entry

    def delete_custom_feed(self, slug: str) -> bool:
        """Elimina un feed personalizado por su slug."""
        slug = (slug or '').strip().lower()
        if self.pool:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM custom_feeds WHERE slug = %s", (slug,))
                    deleted = cursor.rowcount > 0
                    conn.commit()
                    return deleted

        feeds = self.list_custom_feeds()
        filtered = [f for f in feeds if f.get('slug') != slug]
        if len(filtered) != len(feeds):
            self._custom_feeds_fallback_file().write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding='utf-8')
            return True
        return False

    @staticmethod
    def generate_url_hash(url: str) -> str:
        """Genera un hash SHA-256 único basado en la URL."""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def filter_existing_hashes(self, hashes: List[str]) -> set:
        """Verifica en lote qué hashes ya existen en la base de datos (1 sola consulta)."""
        if not self.pool or not hashes:
            return set()
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT url_hash FROM rss_history WHERE url_hash = ANY(%s)",
                        (list(hashes),)
                    )
                    rows = cursor.fetchall()
                    return {row[0] for row in rows}
        except Exception as e:
            self.logger.error(f"Error checking existing hashes: {e}")
            return set()

    def is_post_in_history(self, url_hash: str) -> bool:
        """Verifica si un hash específico ya existe en la base de datos."""
        return url_hash in self.filter_existing_hashes([url_hash])

    def save_posts_to_history(self, posts: List[tuple]):
        """Guarda una lista de posts en la base de datos en lote."""
        if not self.pool or not posts:
            return
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    insert_query = sql.SQL("""
                        INSERT INTO rss_history (url, url_hash, title, content, section, image_url, timestamp)
                        VALUES %s
                        ON CONFLICT (url_hash) DO NOTHING
                    """)
                    extras.execute_values(cursor, insert_query, posts)
                    conn.commit()
                    self.logger.info(f"Saved {len(posts)} posts to history.")
        except Exception as e:
            self.logger.error(f"Error saving posts to history: {e}")

    def query_posts(
        self,
        sections: Optional[List[str]] = None,
        exclude_sections: Optional[List[str]] = None,
        search_query: Optional[str] = None,
        limit: int = 25,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Consulta versátil de artículos con filtrado por secciones, exclusión y búsqueda."""
        if not self.pool:
            return []
        try:
            limit = max(1, min(int(limit or 25), 100))
            offset = max(0, int(offset or 0))
            clauses = []
            params: List[Any] = []

            if sections:
                clean_sec = [s.strip() for s in sections if s and s.strip()]
                if clean_sec:
                    clauses.append("section = ANY(%s)")
                    params.append(clean_sec)

            if exclude_sections:
                clean_exc = [s.strip() for s in exclude_sections if s and s.strip()]
                if clean_exc:
                    clauses.append("NOT (section = ANY(%s))")
                    params.append(clean_exc)

            if search_query and search_query.strip():
                q = f"%{search_query.strip()}%"
                clauses.append("(title ILIKE %s OR content ILIKE %s)")
                params.extend([q, q])

            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            query = f"""
                SELECT id, url, title, content, section, image_url, timestamp
                FROM rss_history
                {where_sql}
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])

            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, tuple(params))
                    rows = cursor.fetchall()
                    return [
                        {
                            'id': r[0],
                            'url': r[1],
                            'title': r[2],
                            'content': r[3],
                            'section': r[4],
                            'image_url': r[5],
                            'timestamp': r[6].isoformat() if hasattr(r[6], 'isoformat') else str(r[6])
                        }
                        for r in rows
                    ]
        except Exception as e:
            self.logger.error(f"Error querying posts: {e}")
            return []

    def get_section_counts(self) -> Dict[str, int]:
        """Obtiene el conteo total de artículos por sección."""
        counts: Dict[str, int] = {sec: 0 for sec in self.sections.keys()}
        if not self.pool:
            return counts
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT section, COUNT(*)
                        FROM rss_history
                        WHERE section IS NOT NULL
                        GROUP BY section
                    """)
                    for sec, cnt in cursor.fetchall():
                        counts[sec] = int(cnt)
            return counts
        except Exception as e:
            self.logger.error(f"Error getting section counts: {e}")
            return counts

    def get_recent_posts(self, limit: int = 20, exclude_sections: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Obtiene los últimos N posts de la base de datos para el feed RSS."""
        return self.query_posts(exclude_sections=exclude_sections, limit=limit)

    def get_unsent_posts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene posts pendientes de enviar a IFTTT."""
        if not self.pool:
            return []
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT url, title, content, section, image_url, timestamp
                        FROM rss_history
                        WHERE sent_to_ifttt = FALSE
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """, (limit,))
                    rows = cursor.fetchall()

                    posts = []
                    for row in rows:
                        posts.append({
                            'url': row[0],
                            'title': row[1],
                            'content': row[2],
                            'section': row[3],
                            'image_url': row[4],
                            'timestamp': row[5]
                        })
                    return posts
        except Exception as e:
            self.logger.error(f"Error retrieving unsent posts: {e}")
            return []

    def mark_posts_as_sent(self, urls: List[str]):
        """Marca posts como enviados a IFTTT."""
        if not self.pool or not urls:
            return
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE rss_history SET sent_to_ifttt = TRUE WHERE url = ANY(%s)",
                        (list(urls),)
                    )
                    conn.commit()
                    self.logger.info(f"Marked {cursor.rowcount} posts as sent to IFTTT.")
        except Exception as e:
            self.logger.error(f"Error marking posts as sent: {e}")

    def fetch_latest(self) -> List[Dict[str, Any]]:
        """Recupera los últimos posts de todas las secciones configuradas optimizando consultas."""
        self.reload_sections_from_db()
        candidate_posts = []
        for section, sources in self.sections.items():
            for site in sources:
                site_type = site.get('type')
                site_url = site.get('url')
                if not site_url:
                    continue

                latest_post = None
                if site_type == 'rss':
                    latest_post = self.fetch_rss_feed(site_url)
                elif site_type == 'web':
                    latest_post = self.fetch_html_page(site_url)
                elif site_type == 'youtube':
                    latest_post = self.fetch_youtube(site_url)

                if latest_post and latest_post.get('url'):
                    title = latest_post.get('title', '')
                    if title in ("No Entries Found", "No Videos Found", "No Title"):
                        continue
                    latest_post['url_hash'] = self.generate_url_hash(latest_post['url'])
                    latest_post['section'] = section
                    candidate_posts.append(latest_post)

        if not candidate_posts:
            return []

        all_hashes = [p['url_hash'] for p in candidate_posts]
        existing_hashes = self.filter_existing_hashes(all_hashes)

        new_posts = [p for p in candidate_posts if p['url_hash'] not in existing_hashes]

        if new_posts:
            validated_posts = [
                (
                    post['url'],
                    post['url_hash'],
                    post.get('title', 'No Title'),
                    post.get('content', 'No Content'),
                    post.get('section', 'Unknown'),
                    post.get('image_url'),
                    datetime.now()
                )
                for post in new_posts
            ]
            self.save_posts_to_history(validated_posts)

        return new_posts

    def fetch_html_page(self, url: str) -> Dict[str, Any]:
        self.logger.info(f"Fetching HTML content from {url}")
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'lxml')

            article = soup.find('div', class_='latest-news')
            if article:
                title_tag = article.find('h1') or article.find('h2') or article.find('h3')
                title = title_tag.get_text(strip=True) if title_tag else "No Title"
                content = article.get_text(strip=True)
                link_tag = article.find('a', href=True)
                link = link_tag['href'] if link_tag else url
                image_url = self._extract_image_from_html(article, url)

                return {"url": link, "title": title, "content": content, "image_url": image_url}
            self.logger.warning(f"No valid article found at {url}")
            return {"url": url, "title": "No Title", "content": "No Content", "image_url": None}
        except Exception as e:
            self.logger.error(f"Error fetching HTML from {url}: {e}")
            return {"url": url, "title": "No Title", "content": "No Content", "image_url": None}

    def _extract_image_from_html(self, element, base_url: str) -> Optional[str]:
        try:
            img_tag = element.find('img')
            if img_tag and img_tag.get('src'):
                return img_tag['src']
            return None
        except Exception:
            return None

    def _extract_image_from_rss(self, entry) -> Optional[str]:
        try:
            if hasattr(entry, 'media_content') and entry.media_content:
                return entry.media_content[0].get('url')
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                return entry.media_thumbnail[0].get('url')
            if hasattr(entry, 'enclosures'):
                for enclosure in entry.enclosures:
                    if 'image' in enclosure.get('type', ''):
                        return enclosure.get('href')
            return None
        except Exception:
            return None

    def fetch_rss_feed(self, url: str) -> Dict[str, Any]:
        self.logger.info(f"Fetching RSS feed from {url}")
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                self.logger.warning(f"No entries found in RSS feed: {url}")
                return {"url": url, "title": "No Entries Found", "content": "", "image_url": None}

            latest_entry = feed.entries[0]
            title = latest_entry.get('title', 'No Title')
            link = latest_entry.get('link', url)
            content = latest_entry.get('summary', latest_entry.get('description', 'No Content'))
            image_url = self._extract_image_from_rss(latest_entry)

            return {"url": link, "title": title, "content": content, "image_url": image_url}
        except Exception as e:
            self.logger.error(f"Error fetching RSS feed from {url}: {e}")
            return {"url": url, "title": "No Entries Found", "content": "", "image_url": None}

    def fetch_youtube(self, feed_url: str) -> Dict[str, Any]:
        self.logger.info(f"Fetching YouTube content from {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                self.logger.warning(f"No entries found for YouTube channel: {feed_url}")
                return {"url": feed_url, "title": "No Videos Found", "content": "", "image_url": None}

            latest_video = feed.entries[0]
            title = latest_video.get('title', 'No Title')
            link = latest_video.get('link', feed_url)
            content = latest_video.get('summary', 'No Content')
            image_url = self._extract_image_from_rss(latest_video)

            return {"url": link, "title": title, "content": content, "image_url": image_url}
        except Exception as e:
            self.logger.error(f"Error fetching YouTube from {feed_url}: {e}")
            return {"url": feed_url, "title": "No Videos Found", "content": "", "image_url": None}
