from flask import Flask, jsonify
import yaml
import subprocess
import logging
import time
import threading
import requests
from fetcher import Fetcher
from rss_generator import RSSGenerator
from logger import setup_logger

app = Flask(__name__)

def load_config():
    with open('app/config.yaml', 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def run_process_rss():
    logger = logging.getLogger('RSSLogger')
    logger.info("Executing process_rss.py synchronously...")
    process = subprocess.Popen(
        ["python", "process_rss.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return process

def process_rss_entries():
    config = load_config()
    logger = setup_logger(config['log_file'])

    logger.info("Starting application...")

    fetcher = Fetcher(config)
    all_latest_posts = []
    
    for section, sources in config['sections'].items():
        logger.info(f"Fetching posts for section: {section}")
        latest_posts = fetcher.fetch_latest(sources)
        for post in latest_posts:
            post['section'] = section
        all_latest_posts.extend(latest_posts)
    
    if all_latest_posts:
        logger.info(f"Latest posts fetched: {all_latest_posts}")
    else:
        logger.warning("No latest posts fetched.")
    
    rss_generator = RSSGenerator(all_latest_posts)
    rss_file_path = 'feed.xml'
    rss_generator.save_rss(filename=rss_file_path)
    logger.info(f"RSS feed updated at {rss_file_path}.")
    
    # Ejecutar el script process_rss.py de manera síncrona y esperar a que termine
    process = run_process_rss()
    
    while process.poll() is None:
        logger.info(f"Waiting for process_rss.py to finish...")
        time.sleep(10)  # Espera breve para no bloquear el servidor
    
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        logger.error(f"process_rss.py failed with exit status {process.returncode}")
        logger.error(f"Standard Output: {stdout.decode()}")
        logger.error(f"Standard Error: {stderr.decode()}")
    else:
        logger.info("Finished executing process_rss.py.")
        logger.info(f"Standard Output: {stdout.decode()}")
        logger.info(f"Standard Error: {stderr.decode()}")

    # Esperar 10 minutos (600 segundos)
    logger.info("Waiting for 10 minutes before triggering IFTTT webhook...")
    time.sleep(600)

    # Invocar el webhook de IFTTT
    try:
        ifttt_webhook_url = config['ifttt_webhook_url']
        response = requests.post(ifttt_webhook_url)
        if response.status_code == 200:
            logger.info("Successfully triggered IFTTT webhook.")
        else:
            logger.error(f"Failed to trigger IFTTT webhook, status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Error triggering IFTTT webhook: {e}")

def run_rss_process_background():
    thread = threading.Thread(target=process_rss_entries)
    thread.start()

@app.route('/run', methods=['POST'])
def run_rss_process():
    run_rss_process_background()
    return jsonify({"message": "RSS processing is running in the background."}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000)
