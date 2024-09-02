import yaml
import subprocess
import logging
import time
from app.fetcher import Fetcher
from app.rss_generator import RSSGenerator
from app.logger import setup_logger

def load_config():
    with open('app/config.yaml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def run_process_rss():
    logger = logging.getLogger('RSSLogger')
    logger.info("Executing process_rss.py synchronously...")

    try:
        process = subprocess.Popen(
            ["python", "process_rss.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = process.communicate()  # Espera a que el proceso termine y captura stdout y stderr

        if process.returncode == 0:
            logger.info("Finished executing process_rss.py.")
            logger.info(f"Standard Output: {stdout.decode()}")
            logger.info(f"Standard Error: {stderr.decode()}")
        else:
            logger.error(f"process_rss.py failed with exit status {process.returncode}")
            logger.error(f"Standard Output: {stdout.decode() if stdout else 'No output'}")
            logger.error(f"Standard Error: {stderr.decode() if stderr else 'No error output'}")

    except Exception as e:
        logger.error(f"An error occurred while executing process_rss.py: {e}")

    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    return process

def process_rss_entries():
    config = load_config()
    logger = setup_logger()

    logger.info("Starting application...")

    fetcher = Fetcher(config)
    all_latest_posts = fetcher.fetch_latest()

    if all_latest_posts:
        logger.info(f"Latest posts fetched: {all_latest_posts}")
    else:
        logger.warning("No latest posts fetched.")
    
    rss_generator = RSSGenerator(all_latest_posts)
    rss_file_path = 'feed.xml'
    rss_generator.save_rss(filename=rss_file_path)
    logger.info(f"RSS feed updated at {rss_file_path}.")
    
    process = run_process_rss()
    while process.poll() is None:
        logger.info(f"Waiting for process_rss.py to finish...")
        time.sleep(10)
    
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        logger.error(f"process_rss.py failed with exit status {process.returncode}")
        logger.error(f"Standard Output: {stdout.decode()}")
        logger.error(f"Standard Error: {stderr.decode()}")
    else:
        logger.info("Finished executing process_rss.py.")
        logger.info(f"Standard Output: {stdout.decode()}")
        logger.info(f"Standard Error: {stderr.decode()}")

if __name__ == '__main__':
    config = load_config()
    interval = config.get('interval', 600)
    while True:
        process_rss_entries()
        logger = logging.getLogger('RSSLogger')
        logger.info(f"Waiting for {interval} seconds before next run...")
        time.sleep(interval)
