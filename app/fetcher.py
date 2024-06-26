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
        for site in sources:
            if site['type'] == 'rss':
                latest_post = self.fetch_rss_feed(site['url'])
            elif site['type'] == 'web':
                latest_post = self.fetch_html_page(site['url'])
            elif site['type'] == 'youtube':
                latest_post = self.fetch_youtube(site['url'])

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
