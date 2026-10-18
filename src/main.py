import subprocess
import logging
import time
import signal
import sys
from pathlib import Path
from src.core.fetcher import Fetcher
from src.core.rss_generator import RSSGenerator
from src.utils.logger import setup_logger
from src.config import get_app_config, FEED_DIR, INTERVAL

# Variable global para el proceso hijo
current_process = None


def signal_handler(sig, frame):
    """Maneja señales de interrupción (SIGINT, SIGTERM) para terminación limpia."""
    logger = logging.getLogger('MainLogger')
    logger.info("Signal received, shutting down gracefully...")
    
    global current_process
    if current_process:
        logger.info("Terminating child process...")
        current_process.terminate()
        try:
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Process didn't terminate in time, killing it...")
            current_process.kill()
    
    logger.info("Shutdown complete.")
    sys.exit(0)


def run_process_rss():
    """Ejecuta de manera síncrona el worker de procesamiento y despacho IFTTT."""
    global current_process
    logger = logging.getLogger('MainLogger')
    logger.info("Executing process_rss.py synchronously...")

    try:
        current_process = subprocess.Popen(
            [sys.executable, "-m", "src.process_rss"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = current_process.communicate()

        if current_process.returncode == 0:
            logger.info("Finished executing process_rss.py successfully.")
            if stdout:
                logger.info(f"Output: {stdout.decode('utf-8', errors='replace').strip()}")
        else:
            logger.error(f"process_rss.py failed with exit status {current_process.returncode}")
            if stdout:
                logger.error(f"Output: {stdout.decode('utf-8', errors='replace').strip()}")
            if stderr:
                logger.error(f"Error Output: {stderr.decode('utf-8', errors='replace').strip()}")

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt caught in run_process_rss, terminating child process...")
        if current_process:
            current_process.terminate()
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                current_process.kill()
        raise

    except Exception as e:
        logger.error(f"An error occurred while executing process_rss.py: {e}")

    finally:
        current_process = None


def process_rss_entries(fetcher: Fetcher = None):
    """Ciclo principal de fetch, generación de feed y despacho."""
    config = get_app_config()
    logger = setup_logger(name='MainLogger', log_file='main.log')
    logger.info("Starting RSS processing cycle...")

    # Asegurar que el directorio de datos existe
    FEED_DIR.mkdir(parents=True, exist_ok=True)

    if fetcher is None:
        fetcher = Fetcher(config)
    
    # 1. Fetch nuevos posts y persistir en BD
    try:
        new_posts = fetcher.fetch_latest()
        logger.info(f"New posts fetched: {len(new_posts)}")
    except Exception as e:
        logger.error(f"Error fetching new posts: {e}")
        new_posts = []
    
    # 2. Obtener posts pendientes de enviar a IFTTT
    try:
        unsent_posts = fetcher.get_unsent_posts(limit=50)
        logger.info(f"Posts pending to send to IFTTT: {len(unsent_posts)}")
    except Exception as e:
        logger.error(f"Error getting unsent posts: {e}")
        unsent_posts = []
    
    # 3. Obtener los últimos 20 posts de la base de datos para el feed principal
    try:
        all_recent_posts = fetcher.get_recent_posts(limit=20, exclude_sections=['Youtube'])
        logger.info(f"Total posts in feed (excluding Youtube): {len(all_recent_posts)}")
    except Exception as e:
        logger.error(f"Error getting recent posts from database: {e}")
        all_recent_posts = []
    
    # Si la base de datos no está disponible o está vacía, pero tenemos posts en memoria
    if not all_recent_posts and new_posts:
        all_recent_posts = [p for p in new_posts if p.get('section') != 'Youtube'][:20]

    # 4. Generar RSS feed.xml principal
    rss_generator = RSSGenerator(all_recent_posts)
    rss_file_path = str(FEED_DIR / 'feed.xml')
    rss_generator.save_rss(filename=rss_file_path)
    logger.info(f"RSS feed updated at {rss_file_path} with {len(all_recent_posts)} posts.")
    
    # 5. Procesar y despachar a IFTTT si hay posts pendientes
    if unsent_posts:
        temp_rss = RSSGenerator(unsent_posts)
        temp_feed_path = str(FEED_DIR / 'feed_new.xml')
        temp_rss.save_rss(filename=temp_feed_path)
        logger.info(f"Temporary feed for unsent posts created at {temp_feed_path}")
        run_process_rss()
    else:
        logger.info("No unsent posts to send to IFTTT, skipping IFTTT dispatch.")


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    config = get_app_config()
    interval = config.get('interval', INTERVAL)
    logger = setup_logger(name='MainLogger', log_file='main.log')
    logger.info(f"RSS Worker daemon started. Polling interval: {interval} seconds.")
    
    fetcher_instance = Fetcher(config)
    try:
        while True:
            process_rss_entries(fetcher=fetcher_instance)
            logger.info(f"Sleeping for {interval} seconds until next cycle...")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
        fetcher_instance.close()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected fatal error: {e}", exc_info=True)
        fetcher_instance.close()
        sys.exit(1)
