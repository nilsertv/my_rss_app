"""Entry point for running src package as a module."""
from src.main import *

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
            logger.info(f"Waiting {interval} seconds before next cycle...")
            time.sleep(interval)
    except Exception as e:
        logger = logging.getLogger('MainLogger')
        logger.error(f"Fatal error in main loop: {str(e)}", exc_info=True)
        sys.exit(1)
