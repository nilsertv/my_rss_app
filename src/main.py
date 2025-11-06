import yaml
import subprocess
import logging
import time
import os
import signal
import sys
from pathlib import Path
from src.core.fetcher import Fetcher
from src.core.rss_generator import RSSGenerator
from src.utils.logger import setup_logger

# Directorio de datos persistente
DATA_DIR_STR = os.getenv('FEED_DIR', './data')
DATA_DIR = Path(DATA_DIR_STR).resolve()  # Convertir a ruta absoluta

# Variable global para el proceso hijo
current_process = None

def signal_handler(sig, frame):
    """Maneja señales de interrupción (CTRL+C)"""
    logger = logging.getLogger('MainLogger')
    logger.info("Interrupt received, shutting down gracefully...")
    
    global current_process
    if current_process:
        logger.info("Terminating child process...")
        current_process.terminate()
        try:
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Process didn't terminate, killing it...")
            current_process.kill()
    
    logger.info("Shutdown complete.")
    sys.exit(0)

def load_config():
    with open('src/config.yaml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def run_process_rss():
    global current_process
    logger = logging.getLogger('MainLogger')
    logger.info("Executing process_rss.py synchronously...")

    try:
        current_process = subprocess.Popen(
            ["poetry", "run", "python", "src/process_rss.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = current_process.communicate()  # Espera a que el proceso termine y captura stdout y stderr

        if current_process.returncode == 0:
            logger.info("Finished executing process_rss.py.")
            logger.info(f"Standard Output: {stdout.decode('utf-8', errors='replace')}")
            logger.info(f"Standard Error: {stderr.decode('utf-8', errors='replace')}")
        else:
            logger.error(f"process_rss.py failed with exit status {current_process.returncode}")
            logger.error(f"Standard Output: {stdout.decode('utf-8', errors='replace') if stdout else 'No output'}")
            logger.error(f"Standard Error: {stderr.decode('utf-8', errors='replace') if stderr else 'No error output'}")

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt caught in run_process_rss, terminating process...")
        if current_process:
            current_process.terminate()
            try:
                current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                current_process.kill()
        raise  # Re-raise para que el manejador principal lo capture

    except Exception as e:
        logger.error(f"An error occurred while executing process_rss.py: {e}")

    finally:
        if current_process:
            if current_process.stdout:
                current_process.stdout.close()
            if current_process.stderr:
                current_process.stderr.close()
            current_process = None

    return current_process

def process_rss_entries():
    config = load_config()
    logger = setup_logger(name='MainLogger', log_file='main.log')

    logger.info("Starting application...")

    # Asegurar que el directorio de datos existe desde el inicio
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fetcher = Fetcher(config)
    
    # Fetch nuevos posts y guardarlos en la base de datos
    try:
        new_posts = fetcher.fetch_latest()
        
        if new_posts:
            logger.info(f"New posts fetched: {len(new_posts)}")
        else:
            logger.info("No new posts found.")
    except Exception as e:
        logger.error(f"Error fetching new posts: {e}")
        new_posts = []
    
    # Obtener posts pendientes de enviar a IFTTT
    try:
        unsent_posts = fetcher.get_unsent_posts(limit=50)
        logger.info(f"Posts pending to send to IFTTT: {len(unsent_posts)}")
    except Exception as e:
        logger.error(f"Error getting unsent posts: {e}")
        unsent_posts = []
    
    # Obtener los últimos 20 posts de la base de datos para el feed
    # Excluir posts de Youtube del feed principal (feed.xml)
    try:
        all_recent_posts = fetcher.get_recent_posts(limit=20, exclude_sections=['Youtube'])
        logger.info(f"Total posts in feed (excluding Youtube): {len(all_recent_posts)}")
    except Exception as e:
        logger.error(f"Error getting recent posts from database: {e}")
        all_recent_posts = []
    
    # Generar RSS con todos los posts recientes (excluyendo Youtube, siempre aunque esté vacío)
    rss_generator = RSSGenerator(all_recent_posts)
    rss_file_path = str(DATA_DIR / 'feed.xml')
    rss_generator.save_rss(filename=rss_file_path)
    logger.info(f"RSS feed updated at {rss_file_path} with {len(all_recent_posts)} posts (excluding Youtube).")
    
    # Procesar y enviar a IFTTT los posts pendientes
    if unsent_posts:
        # Generar un feed temporal solo con posts pendientes para IFTTT (incluye Youtube)
        temp_rss = RSSGenerator(unsent_posts)
        temp_feed_path = str(DATA_DIR / 'feed_new.xml')
        temp_rss.save_rss(filename=temp_feed_path)
        logger.info(f"Temporary feed for unsent posts created at {temp_feed_path} (includes Youtube)")
        
        # Ejecutar process_rss.py para enviar posts a IFTTT
        # Nota: process_rss.py marcará cada post como sent_to_ifttt=TRUE inmediatamente después de enviarlo
        run_process_rss()
    else:
        logger.info("No unsent posts to send to IFTTT, skipping process_rss.py")

if __name__ == '__main__':
    # Registrar manejador de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    config = load_config()
    interval = config.get('interval', 600)
    
    try:
        while True:
            process_rss_entries()
            logger = logging.getLogger('MainLogger')
            logger.info(f"Waiting for {interval} seconds before next run...")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger = logging.getLogger('MainLogger')
        logger.info("Application stopped by user.")
        sys.exit(0)
