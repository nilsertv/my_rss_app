import xml.etree.ElementTree as ET
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import aiohttp
import os
from pathlib import Path
import sys
import psycopg2
from typing import List, Dict, Any

from src.config import IFTTT_WEBHOOK_URL, POST_DELAY, DATABASE_URL, FEED_DIR

# Configurar el logger con archivo y consola
log_dir = Path('./logs')
log_dir.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger('ProcessRSSLogger')
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore
except Exception:
    pass
logger.addHandler(console_handler)

file_handler = RotatingFileHandler(
    log_dir / 'process_rss.log',
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(console_formatter)
logger.addHandler(file_handler)

FEED_FILE = FEED_DIR / 'feed_new.xml'


async def read_rss(filename: Path) -> List[Dict[str, str]]:
    """Lee y parsea las entradas de un feed RSS XML."""
    logger.info(f"Reading RSS feed from {filename}...")
    try:
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
                    'title': title_elem.text if title_elem is not None and title_elem.text else 'No Title',
                    'link': link_elem.text if link_elem is not None and link_elem.text else '',
                    'description': desc_elem.text if desc_elem is not None and desc_elem.text else 'No Content'
                }
                entries.append(entry)
        else:
            logger.error("No channel found in the RSS feed XML.")
        return entries
    except Exception as e:
        logger.error(f"Error parsing RSS XML from {filename}: {e}")
        return []


async def post_to_ifttt(entry: Dict[str, str], webhook_url: str) -> bool:
    """Envía un post a IFTTT webhook."""
    if not webhook_url or "TU_IFTTT_KEY" in webhook_url:
        logger.warning(f"IFTTT_WEBHOOK_URL is not configured. Simulating post for: {entry.get('title')}")
        return True

    data = {
        'value1': entry.get('title', ''),
        'value2': entry.get('link', ''),
        'value3': entry.get('description', '')
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=data, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status == 200:
                    logger.info(f"Successfully posted to IFTTT: {entry.get('title')}")
                    return True
                else:
                    logger.error(f"Failed to post to IFTTT: {entry.get('title')} with status {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Exception posting to IFTTT for {entry.get('title')}: {e}")
        return False


def mark_post_as_sent(url: str, db_url: str):
    """Marca un post como enviado a IFTTT en la base de datos."""
    if not db_url or db_url.startswith("${"):
        return
    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE rss_history 
                    SET sent_to_ifttt = TRUE 
                    WHERE url = %s
                """, (url,))
                conn.commit()
                logger.info(f"Marked post as sent in DB: {url}")
    except Exception as e:
        logger.error(f"Error marking post as sent in DB: {e}")


async def process_entries(entries: List[Dict[str, str]], webhook_url: str, delay: int, db_url: str):
    """Procesa y despacha secuencialmente las entradas a IFTTT respetando rate limits."""
    try:
        total = len(entries)
        for i, entry in enumerate(entries):
            if entry.get('description') == "No Content":
                logger.info(f"Skipping entry without content: {entry.get('title')}")
                continue

            logger.info(f"[{i+1}/{total}] Processing entry: {entry.get('title')}")
            success = await post_to_ifttt(entry, webhook_url)
            
            if success and entry.get('link'):
                mark_post_as_sent(entry['link'], db_url)

            if i < total - 1:
                logger.info(f"Sleeping for {delay} seconds before next post...")
                await asyncio.sleep(delay)
    except Exception as e:
        logger.error(f"Error processing entries: {e}")


async def main():
    logger.info("Starting process_rss runner...")
    if not FEED_FILE.exists():
        logger.warning(f"Temporary feed file not found at {FEED_FILE}. Nothing to dispatch.")
        return

    entries = await read_rss(FEED_FILE)
    if entries:
        await process_entries(
            entries=entries,
            webhook_url=IFTTT_WEBHOOK_URL,
            delay=POST_DELAY,
            db_url=DATABASE_URL
        )
    logger.info("Finished process_rss run.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Unhandled exception in process_rss: {e}", exc_info=True)
