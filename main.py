import asyncio
import yaml
from app.fetcher import Fetcher
from app.rss_generator import RSSGenerator
from app.logger import setup_logger

def load_config():
    with open('app/config.yaml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

async def main():
    config = load_config()
    logger = setup_logger(config['log_file'])

    logger.info("Starting application...")

    fetcher = Fetcher(config)
    while True:
        logger.info("Fetching latest posts...")
        try:
            latest_posts = fetcher.fetch_latest()
            if latest_posts:
                logger.info(f"Latest posts fetched: {latest_posts}")
            else:
                logger.warning("No latest posts fetched.")
            
            rss_generator = RSSGenerator(latest_posts)
            rss_file_path = 'feed.xml'
            rss_generator.save_rss(filename=rss_file_path)
            logger.info(f"RSS feed updated at {rss_file_path}.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        
        logger.info(f"Sleeping for {config['interval']} seconds...")
        await asyncio.sleep(config['interval'])

if __name__ == '__main__':
    asyncio.run(main())
