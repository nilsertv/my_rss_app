import hashlib
import requests
import feedparser
import logging
from bs4 import BeautifulSoup
import psycopg2
from psycopg2 import sql, extras
from datetime import datetime

class Fetcher:
    def __init__(self, config):
        from src.utils.logger import setup_logger
        self.logger = setup_logger(name='FetcherLogger', log_file='fetcher.log')
        self.sections = config['sections']
        self.connection_url = config['database']['connection_url']
        self.batch_size = 1000  # Tamaño del lote para las inserciones
        self.init_db()

    def init_db(self):
        with psycopg2.connect(self.connection_url) as conn:
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
                
                # Crear índices para optimizar consultas
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

    def generate_url_hash(self, url):
        # Generar un hash único basado en la URL
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def is_post_in_history(self, url_hash):
        with psycopg2.connect(self.connection_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(1) FROM rss_history WHERE url_hash = %s", (url_hash,))
                result = cursor.fetchone()
                return result[0] > 0 if result else False

    def save_posts_to_history(self, posts):
        with psycopg2.connect(self.connection_url) as conn:
            with conn.cursor() as cursor:
                insert_query = sql.SQL("""
                    INSERT INTO rss_history (url, url_hash, title, content, section, image_url, timestamp)
                    VALUES %s
                    ON CONFLICT (url_hash) DO NOTHING
                """)
                extras.execute_values(cursor, insert_query, posts)
                conn.commit()

    def get_recent_posts(self, limit=20, exclude_sections=None):
        """Obtiene los últimos N posts de la base de datos para el feed RSS
        
        Args:
            limit: Número máximo de posts a retornar
            exclude_sections: Lista de secciones a excluir (ej: ['Youtube'])
        """
        with psycopg2.connect(self.connection_url) as conn:
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

    def get_unsent_posts(self, limit=50):
        """Obtiene posts que aún no han sido enviados a IFTTT
        
        Args:
            limit: Número máximo de posts a retornar
        """
        with psycopg2.connect(self.connection_url) as conn:
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

    def mark_posts_as_sent(self, urls):
        """Marca posts como enviados a IFTTT
        
        Args:
            urls: Lista de URLs de posts que fueron enviados exitosamente
        """
        if not urls:
            return
            
        with psycopg2.connect(self.connection_url) as conn:
            with conn.cursor() as cursor:
                placeholders = ', '.join(['%s'] * len(urls))
                query = f"""
                    UPDATE rss_history 
                    SET sent_to_ifttt = TRUE 
                    WHERE url IN ({placeholders})
                """
                cursor.execute(query, urls)
                conn.commit()
                self.logger.info(f"Marked {cursor.rowcount} posts as sent to IFTTT")

    def fetch_latest(self):
        latest_posts = []
        for section, sources in self.sections.items():
            for site in sources:
                latest_post = None
                if site['type'] == 'rss':
                    latest_post = self.fetch_rss_feed(site['url'])
                elif site['type'] == 'web':
                    latest_post = self.fetch_html_page(site['url'])
                elif site['type'] == 'youtube':
                    latest_post = self.fetch_youtube(site['url'])

                if latest_post:
                    url_hash = self.generate_url_hash(latest_post['url'])
                    if not self.is_post_in_history(url_hash):
                        latest_post['url_hash'] = url_hash
                        latest_post['section'] = section  # Aquí se asigna la sección al post
                        latest_posts.append(latest_post)

        # Validar y almacenar en la base de datos
        if latest_posts:
            validated_posts = [
                (post['url'], post['url_hash'], post.get('title', 'No Title'), post.get('content', 'No Content'), post.get('section', 'Unknown'), post.get('image_url'), datetime.now())
                for post in latest_posts if post.get('url')
            ]
            self.save_posts_to_history(validated_posts)

        return latest_posts

    # Las funciones fetch_html_page, fetch_rss_feed, y fetch_youtube permanecen iguales

    def fetch_html_page(self, url):
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
                
                # Intentar extraer imagen
                image_url = self._extract_image_from_html(article, url)
                
                self.logger.info(f"Fetched HTML content from {url}")
                return {"url": link, "title": title, "content": content, "image_url": image_url}
            self.logger.error(f"No valid article found at {url}")
            return {"url": url, "title": "No Title", "content": "No Content", "image_url": None}
        except Exception as e:
            self.logger.error(f"Error fetching HTML from {url}: {e}")
            return {"url": url, "title": "No Title", "content": "No Content", "image_url": None}

    def _extract_image_from_html(self, element, base_url):
        """Extrae URL de imagen de un elemento HTML"""
        try:
            # Buscar meta og:image
            img_tag = element.find('img')
            if img_tag and img_tag.get('src'):
                return img_tag['src']
            return None
        except Exception:
            return None

    def _extract_image_from_rss(self, entry):
        """Extrae URL de imagen de una entrada RSS"""
        try:
            # Buscar media:content
            if hasattr(entry, 'media_content') and entry.media_content:
                return entry.media_content[0].get('url')
            
            # Buscar media:thumbnail
            if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
                return entry.media_thumbnail[0].get('url')
            
            # Buscar enclosure de imagen
            if hasattr(entry, 'enclosures'):
                for enclosure in entry.enclosures:
                    if 'image' in enclosure.get('type', ''):
                        return enclosure.get('href')
            
            return None
        except Exception:
            return None

    def fetch_rss_feed(self, url):
        self.logger.info(f"Fetching RSS feed from {url}")
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                self.logger.error(f"No entries found in RSS feed: {url}")
                return {"url": url, "title": "No Entries Found", "content": "", "image_url": None}
            
            latest_entry = feed.entries[0]
            title = latest_entry.get('title', 'No Title')
            link = latest_entry.get('link', url)
            content = latest_entry.get('summary', latest_entry.get('description', 'No Content'))
            
            # Extraer imagen
            image_url = self._extract_image_from_rss(latest_entry)
            
            self.logger.info(f"Fetched RSS feed content: {title}")
            return {"url": link, "title": title, "content": content, "image_url": image_url}
        except Exception as e:
            self.logger.error(f"Error fetching RSS feed from {url}: {e}")
            return {"url": url, "title": "No Entries Found", "content": "", "image_url": None}

    def fetch_youtube(self, feed_url):
        self.logger.info(f"Fetching YouTube content from {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            if not feed.entries:
                self.logger.error(f"No entries found for YouTube channel: {feed_url}")
                return {"url": feed_url, "title": "No Videos Found", "content": "", "image_url": None}
            
            latest_video = feed.entries[0]
            title = latest_video.get('title', 'No Title')
            link = latest_video.get('link', feed_url)
            content = latest_video.get('summary', 'No Content')
            
            # YouTube proporciona thumbnail en media:thumbnail
            image_url = self._extract_image_from_rss(latest_video)
            
            self.logger.info(f"Fetched YouTube content: {title}")
            return {"url": link, "title": title, "content": content, "image_url": image_url}
        except Exception as e:
            self.logger.error(f"Error fetching YouTube from {feed_url}: {e}")
            return {"url": feed_url, "title": "No Videos Found", "content": "", "image_url": None}
