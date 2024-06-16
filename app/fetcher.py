import requests
import feedparser
import json
from datetime import datetime
import logging
from bs4 import BeautifulSoup

class Fetcher:
    def __init__(self, config):
        self.logger = logging.getLogger('RSSLogger')
        self.sections = config['sections']
        self.history_file = config['history_file']
        self.history = self.load_history()

    def load_history(self):
        try:
            with open(self.history_file, 'r') as file:
                history = json.load(file)
                self.logger.info(f"Loaded history from {self.history_file}")
                return history
        except FileNotFoundError:
            self.logger.warning(f"History file {self.history_file} not found. Starting with an empty history.")
            return []

    def save_history(self):
        with open(self.history_file, 'w') as file:
            json.dump(self.history, file)
        self.logger.info(f"Saved history to {self.history_file}")

    def fetch_latest(self, sources):
        latest_posts = []
        for source in sources:
            if source['type'] == 'web':
                latest_post = self.fetch_web(source['url'])
            elif source['type'] == 'youtube':
                latest_post = self.fetch_youtube(source['url'])

            if latest_post and not self.is_post_in_history(latest_post):
                latest_posts.append(latest_post)

        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'posts': latest_posts
        })
        self.save_history()
        return latest_posts

    def is_post_in_history(self, post):
        for entry in self.history:
            for recorded_post in entry.get('posts', []):
                if recorded_post['url'] == post['url']:
                    self.logger.info(f"Post already in history: {post['url']}")
                    return True
        return False

    def fetch_web(self, url):
        if 'rss' in url or 'feed' in url:
            return self.fetch_rss_feed(url)
        else:
            return self.fetch_html_page(url)

    def fetch_html_page(self, url):
        self.logger.info(f"Fetching HTML content from {url}")
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
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
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'xml')  # Utilizamos features="xml" aquí
        entries = soup.find_all('entry') or soup.find_all('item')
        if not entries:
            self.logger.error(f"No entries found in RSS feed: {url}")
            return {"url": url, "title": "No Entries Found", "content": ""}
        latest_entry = entries[0]
        title = latest_entry.title.get_text(strip=True)
        link = latest_entry.link.get('href') if latest_entry.link else latest_entry.find('link').get('href')
        content = latest_entry.summary.get_text(strip=True) if latest_entry.find('summary') else latest_entry.description.get_text(strip=True)
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
