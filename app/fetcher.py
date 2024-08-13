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
        self.logger = logging.getLogger('RSSLogger')
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
                        timestamp TIMESTAMPTZ DEFAULT NOW()
                    )
                ''')
                conn.commit()

    def generate_url_hash(self, url):
        # Generar un hash único basado en la URL
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def is_post_in_history(self, url_hash):
        with psycopg2.connect(self.connection_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(1) FROM rss_history WHERE url_hash = %s", (url_hash,))
                return cursor.fetchone()[0] > 0

    def save_posts_to_history(self, posts):
        with psycopg2.connect(self.connection_url) as conn:
            with conn.cursor() as cursor:
                insert_query = sql.SQL("""
                    INSERT INTO rss_history (url, url_hash, title, content, timestamp)
                    VALUES %s
                    ON CONFLICT (url_hash) DO NOTHING
                """)
                extras.execute_values(cursor, insert_query, posts)
                conn.commit()

    def fetch_latest(self):
        latest_posts = []
        for section, sources in self.sections.items():
            for site in sources:
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
                (post['url'], post['url_hash'], post.get('title', 'No Title'), post.get('content', 'No Content'), datetime.now())
                for post in latest_posts if post.get('url')
            ]
            self.save_posts_to_history(validated_posts)

        return latest_posts

    # Las funciones fetch_html_page, fetch_rss_feed, y fetch_youtube permanecen iguales

    def fetch_html_page(self, url):
        self.logger.info(f"Fetching HTML content from {url}")
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'lxml')

        article = soup.find('div', class_='latest-news')
        if article:
            title_tag = article.find('h1') or article.find('h2') or article.find('h3')
            title = title_tag.get_text(strip=True) if title_tag else "No Title"
            content = article.get_text(strip=True)
            link_tag = article.find('a', href=True)
            link = link_tag['href'] if link_tag else url
            self.logger.info(f"Fetched HTML content from {url}")
            return {"url": link, "title": title, "content": content}
        self.logger.error(f"No valid article found at {url}")
        return {"url": url, "title": "No Title", "content": "No Content"}

    def fetch_rss_feed(self, url):
        self.logger.info(f"Fetching RSS feed from {url}")
        feed = feedparser.parse(url)
        if not feed.entries:
            self.logger.error(f"No entries found in RSS feed: {url}")
            return {"url": url, "title": "No Entries Found", "content": ""}
        latest_entry = feed.entries[0]
        title = latest_entry.title
        link = latest_entry.link
        content = latest_entry.summary if 'summary' in latest_entry else latest_entry.description
        self.logger.info(f"Fetched RSS feed content: {title}")
        return {"url": link, "title": title, "content": content}

    def fetch_youtube(self, feed_url):
        self.logger.info(f"Fetching YouTube content from {feed_url}")
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            self.logger.error(f"No entries found for YouTube channel: {feed_url}")
            return {"url": feed_url, "title": "No Videos Found", "content": ""}
        latest_video = feed.entries[0]
        self.logger.info(f"Fetched YouTube content: {latest_video.title}")
        return {"url": latest_video.link, "title": latest_video.title, "content": latest_video.summary}
