import os
import hashlib
import requests
import feedparser
import logging
from bs4 import BeautifulSoup
import psycopg2
from psycopg2 import sql, extras, pool
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from src.utils.logger import setup_logger


class Fetcher:
    def __init__(self, config: Dict[str, Any]):
        self.logger = setup_logger(name='FetcherLogger', log_file='fetcher.log')
        self.sections = config.get('sections', {})
        
        # Obtener DATABASE_URL desde config o entorno
        self.connection_url = os.environ.get('DATABASE_URL') or config.get('database', {}).get('connection_url') or config.get('database_url', '')
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
        """Crea tablas e índices si no existen."""
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
                    conn.commit()
        except Exception as e:
            self.logger.error(f"Error initializing database schema: {e}")

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

    def get_recent_posts(self, limit: int = 20, exclude_sections: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Obtiene los últimos N posts de la base de datos para el feed RSS."""
        if not self.pool:
            return []
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if exclude_sections:
                        placeholders = ', '.join(['%s'] * len(exclude_sections))
                        query = f"""
                            SELECT url, title, content, section, image_url, timestamp
                            FROM rss_history
                            WHERE section NOT IN ({placeholders})
                            ORDER BY timestamp DESC
                            LIMIT %s
                        """
                        cursor.execute(query, (*exclude_sections, limit))
                    else:
                        cursor.execute("""
                            SELECT url, title, content, section, image_url, timestamp
                            FROM rss_history
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
            self.logger.error(f"Error retrieving recent posts: {e}")
            return []

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
                    latest_post['url_hash'] = self.generate_url_hash(latest_post['url'])
                    latest_post['section'] = section
                    candidate_posts.append(latest_post)

        if not candidate_posts:
            return []

        # Filtrado en lote en una única consulta a la base de datos
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
