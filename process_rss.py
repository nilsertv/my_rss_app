import xml.etree.ElementTree as ET
import json
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import aiohttp
import os
from pathlib import Path
import sys
import yaml
import psycopg2

# Configurar el logger con archivo
log_dir = Path('./logs')
log_dir.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger('ProcessRSSLogger')
logger.setLevel(logging.INFO)

# Handler de consola con UTF-8
console_handler = logging.StreamHandler(sys.stdout)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore
except Exception:
    pass
logger.addHandler(console_handler)

# Handler de archivo con UTF-8
file_handler = RotatingFileHandler(
    log_dir / 'process_rss.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(console_formatter)
logger.addHandler(file_handler)

# Directorio de datos persistente
DATA_DIR_STR = os.getenv('FEED_DIR', './data')
DATA_DIR = Path(DATA_DIR_STR).resolve()
FEED_FILE = DATA_DIR / 'feed_new.xml'  # Feed temporal solo con posts nuevos

# Cargar la configuración desde config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

ifttt_webhook_url = config['ifttt_webhook_url']
post_delay = config.get('post_delay', 225)  # Obtiene el valor de post_delay, por defecto 225 segundos

# Cargar configuración de base de datos desde app/config.yaml
with open('app/config.yaml', 'r', encoding='utf-8') as yaml_file:
    app_config = yaml.safe_load(yaml_file)
    db_connection_url = app_config['database']['connection_url']

async def read_rss(filename):
    logger.info("Reading RSS feed...")
    tree = ET.parse(filename)
    root = tree.getroot()
    entries = []

    channel = root.find('channel')
    if channel is not None:
        for item in channel.findall('item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            
            entry = {
                'title': title_elem.text if title_elem is not None else 'No Title',
                'link': link_elem.text if link_elem is not None else '',
                'description': desc_elem.text if desc_elem is not None else 'No Content'
            }
            entries.append(entry)
    else:
        logger.error("No channel found in the RSS feed.")
    return entries

async def post_to_ifttt(entry):
    data = {
        'value1': entry['title'],
        'value2': entry['link'],
        'value3': entry['description']
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(ifttt_webhook_url, json=data) as response:
            if response.status == 200:
                logger.info(f"Successfully posted to IFTTT: {entry['title']}")
                return True
            else:
                logger.error(f"Failed to post to IFTTT: {entry['title']} with status code {response.status}")
                return False

def mark_post_as_sent(url):
    """Marca un post como enviado a IFTTT inmediatamente en la base de datos"""
    try:
        with psycopg2.connect(db_connection_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE rss_history 
                    SET sent_to_ifttt = TRUE 
                    WHERE url = %s
                """, (url,))
                conn.commit()
                logger.info(f"Marked post as sent: {url}")
    except Exception as e:
        logger.error(f"Error marking post as sent: {e}")

async def process_entries(entries):
    try:
        for i, entry in enumerate(entries):
            if entry['description'] == "No Content":
                logger.info(f"Skipping entry with 'No Content': {entry['title']}")
                continue

            logger.info(f"Processing entry: {entry['title']}")
            success = await post_to_ifttt(entry)
            
            # Marcar como enviado inmediatamente si fue exitoso
            if success:
                mark_post_as_sent(entry['link'])

            if i < len(entries) - 1:
                logger.info(f"Sleeping for {post_delay} seconds before processing the next entry...")
                await asyncio.sleep(post_delay)
    except Exception as e:
        logger.error(f"Error processing entries: {e}")

async def main():
    logger.info("Starting to process RSS entries...")
    if not FEED_FILE.exists():
        logger.error(f"Feed file not found at {FEED_FILE}")
        return
    entries = await read_rss(FEED_FILE)
    await process_entries(entries)
    logger.info("Finished processing RSS entries.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"An error occurred during execution: {e}")
