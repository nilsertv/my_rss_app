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
    process = subprocess.Popen(
        ["python", "process_rss.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return process

def main():
    config = load_config()
    logger = setup_logger(config['log_file'])

    logger.info("Starting application...")

    fetcher = Fetcher(config)
    
    while True:
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
            
        except Exception as e:
            logger.error(f"An error occurred: {e}")

        # Ejecutar el script process_rss.py de manera síncrona y esperar a que termine
        process = run_process_rss()
        
        while process.poll() is None:
            logger.info(f"Waiting for process_rss.py to finish...")
            time.sleep(600)  # Espera adicional de 600 segundos si process_rss.py no ha terminado
        
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            logger.error(f"process_rss.py failed with exit status {process.returncode}")
            logger.error(f"Standard Output: {stdout.decode()}")
            logger.error(f"Standard Error: {stderr.decode()}")
        else:
            logger.info("Finished executing process_rss.py.")
            logger.info(f"Standard Output: {stdout.decode()}")
            logger.info(f"Standard Error: {stderr.decode()}")
        
        logger.info(f"Sleeping for {config['interval']} seconds before next cycle...")
        time.sleep(config['interval'])

if __name__ == '__main__':
    main()
