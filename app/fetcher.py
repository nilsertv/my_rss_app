import requests
import feedparser
import json
from datetime import datetime

class Fetcher:
    def __init__(self, config):
        self.websites = config['websites']
        self.history_file = config['history_file']
        self.history = self.load_history()

    def load_history(self):
        try:
            with open(self.history_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            return []

    def save_history(self):
        with open(self.history_file, 'w') as file:
            json.dump(self.history, file)

    def fetch_latest(self):
        latest_posts = []
        for site in self.websites:
            if site['type'] == 'web':
                latest_posts.append(self.fetch_web(site['url']))
            elif site['type'] == 'youtube':
                latest_posts.append(self.fetch_youtube(site['url']))
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'posts': latest_posts
        })
        self.save_history()
        return latest_posts

    def fetch_web(self, url):
        response = requests.get(url)
        # Implementar lógica de scraping según el contenido de la página web
        return {"url": url, "content": response.text}

    def fetch_youtube(self, channel_url):
        feed_url = f"{channel_url}/videos?view=0&sort=dd&flow=grid"
        feed = feedparser.parse(feed_url)
        latest_video = feed.entries[0]
        return {"url": latest_video.link, "title": latest_video.title}

