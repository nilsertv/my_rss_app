import asyncio
import yaml
import subprocess
import logging
from app.fetcher import Fetcher
from app.rss_generator import RSSGenerator
from app.logger import setup_logger

def load_config():
    with open('app/config.yaml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

async def run_process_rss():
    logger = logging.getLogger('RSSLogger')
    logger.info("Executing process_rss.py asynchronously...")
    process = await asyncio.create_subprocess_exec(
        "python", "process_rss.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logger.error(f"process_rss.py failed with exit status {process.returncode}")
        logger.error(f"Standard Output: {stdout.decode()}")
        logger.error(f"Standard Error: {stderr.decode()}")
    else:
        logger.info("Finished executing process_rss.py.")
        logger.info(f"Standard Output: {stdout.decode()}")
        logger.info(f"Standard Error: {stderr.decode()}")

async def main():
    config = load_config()
    logger = setup_logger(config['log_file'])

    logger.info("Starting application...")

    fetcher = Fetcher(config)
    
    logger.info("Fetching latest posts...")
    try:
        all_latest_posts = []
        for section, sources in config['sections'].items():
            logger.info(f"Fetching posts for section: {section}")
            latest_posts = fetcher.fetch_latest(sources)
            for post in latest_posts:
                post['section'] = section
            all_latest_posts.extend(latest_posts)
        
        if all_latest_posts:
            logger.info(f"Latest posts fetched: {all_latest_posts}")
        else:
            logger.warning("No latest posts fetched.")
        
        rss_generator = RSSGenerator(all_latest_posts)
        rss_file_path = 'feed.xml'
        rss_generator.save_rss(filename=rss_file_path)
        logger.info(f"RSS feed updated at {rss_file_path}.")
        
        # Ejecutar el script process_rss.py de manera asíncrona y continuar
        await run_process_rss()

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if str(e) != 'Event loop is closed':
            raise
