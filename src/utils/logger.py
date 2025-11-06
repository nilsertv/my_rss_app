import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

def setup_logger(name='RSSLogger', log_file=None, level=logging.INFO):
    """Configura un logger con handlers de consola y archivo
    
    Args:
        name: Nombre del logger
        log_file: Nombre del archivo de log (opcional, ej: 'main.log')
        level: Nivel de logging
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Evitar duplicar handlers si ya existen
    if logger.hasHandlers():
        return logger
    
    # Formato
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Handler de consola con encoding UTF-8 para evitar errores con emojis
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    # Configurar encoding UTF-8 para evitar UnicodeEncodeError en Windows
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore
    except Exception:
        pass  # Si falla, continuar sin reconfigurar
    logger.addHandler(console_handler)
    
    # Handler de archivo (si se especifica)
    if log_file:
        # Crear directorio de logs si no existe
        log_dir = Path('./logs')
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_path = log_dir / log_file
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # Especificar UTF-8 para archivos
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

