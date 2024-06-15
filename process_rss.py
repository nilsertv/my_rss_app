import xml.etree.ElementTree as ET
import requests
import json
import logging
import asyncio
import aiohttp

# Configurar el logger
logging.basicConfig(filename='process_rss.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cargar la configuración
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

ifttt_webhook_url = config['ifttt_webhook_url']
delay_seconds = config.get('delay_seconds', 225)  # Valor predeterminado de 225 segundos

async def read_rss(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    entries = []

    channel = root.find('channel')
    if channel is not None:
        for item in channel.findall('item'):
            entry = {
                'title': item.find('title').text,
                'link': item.find('link').text,
                'description': item.find('description').text
            }
            entries.append(entry)
    else:
        logging.error("No channel found in the RSS feed.")
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
                logging.info(f"Successfully posted to IFTTT: {entry['title']}")
            else:
                logging.error(f"Failed to post to IFTTT: {entry['title']} with status code {response.status}")

async def process_entries(entries):
    try:
        for entry in entries:
            if entry['description'] == "No Content":
                logging.info(f"Skipping entry with 'No Content': {entry['title']}")
                continue

            logging.info(f"Processing entry: {entry['title']}")
            await post_to_ifttt(entry)
            logging.info(f"Waiting for {delay_seconds} seconds before processing the next entry...")
            await asyncio.sleep(delay_seconds)
    except Exception as e:
        logging.error(f"Error processing entries: {e}")

async def main():
    logging.info("Starting to process RSS entries...")
    entries = await read_rss('feed.xml')
    await process_entries(entries)
    logging.info("Finished processing RSS entries.")

if __name__ == '__main__':
    asyncio.run(main())
