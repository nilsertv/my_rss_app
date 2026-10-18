"""Punto de entrada para ejecutar el paquete src como módulo (python -m src)."""
import signal
import time
import logging
import sys

from src.main import signal_handler, process_rss_entries
from src.config import get_app_config, INTERVAL
from src.core.fetcher import Fetcher
from src.utils.logger import setup_logger

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    config = get_app_config()
    interval = config.get('interval', INTERVAL)
    logger = setup_logger(name='MainLogger', log_file='main.log')
    logger.info(f"Starting src module daemon. Polling interval: {interval}s")
    
    fetcher_instance = Fetcher(config)
    try:
        while True:
            process_rss_entries(fetcher=fetcher_instance)
            logger.info(f"Waiting {interval} seconds before next cycle...")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Application stopped by user.")
        fetcher_instance.close()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        fetcher_instance.close()
        sys.exit(1)
