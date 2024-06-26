import logging
from logging.handlers import RotatingFileHandler

def setup_logger(log_file):
    logger = logging.getLogger('RSSLogger')
    logger.setLevel(logging.INFO)
    
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    if not logger.hasHandlers():
        logger.addHandler(handler)
    
    return logger
