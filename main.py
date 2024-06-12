import asyncio
import yaml
import time
from app.fetcher import Fetcher
from app.rss_generator import RSSGenerator
from app.logger import setup_logger

def load_config():
    with open('app/config.yaml', 'r') as file:
        return yaml.safe_load(file)

async def main():
    config = load_config()
    logger = setup_logger(config['log_file'])

    fetcher = Fetcher(config)
    while True:
        logger.info("Fetching latest posts...")
        latest_posts = fetcher.fetch_latest()
        rss_generator = RSSGenerator(latest_posts)
        rss_generator.save_rss()
        logger.info("RSS feed updated.")
        await asyncio.sleep(config['interval'])

if __name__ == '__main__':
    asyncio.run(main())
