import logging
from logging.handlers import RotatingFileHandler

def setup_logger():
    logger = logging.getLogger('RSSLogger')
    logger.setLevel(logging.INFO)
    
    handler = RotatingFileHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    if not logger.hasHandlers():
        logger.addHandler(handler)
    
    return logger
