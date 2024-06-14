import asyncio
import yaml
import subprocess
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
            
            # Ejecutar el script process_rss.py
            logger.info("Executing process_rss.py...")
            result = subprocess.run(["python", "process_rss.py"], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"process_rss.py failed with exit status {result.returncode}")
                logger.error(f"Standard Output: {result.stdout}")
                logger.error(f"Standard Error: {result.stderr}")
            else:
                logger.info("Finished executing process_rss.py.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        
        logger.info(f"Sleeping for {config['interval']} seconds...")
        await asyncio.sleep(config['interval'])

if __name__ == '__main__':
    asyncio.run(main())
