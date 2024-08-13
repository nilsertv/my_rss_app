import json
import psycopg2
import hashlib

def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    return data

def generate_url_hash(url):
    # Generar un hash único basado en la URL
    return hashlib.sha256(url.encode('utf-8')).hexdigest()

def update_url_hashes_from_json(data, db_config):
    conn = psycopg2.connect(db_config['connection_url'])
    cursor = conn.cursor()

    # Preparar la consulta de actualización
    update_query = "UPDATE rss_history SET url_hash = %s WHERE url = %s"

    for entry in data:
        posts = entry.get('posts', [])
        for post in posts:
            url = post.get('url')
            if url:
                url_hash = generate_url_hash(url)
                cursor.execute(update_query, (url_hash, url))

    # Confirmar los cambios en la base de datos
    conn.commit()

    cursor.close()
    conn.close()

if __name__ == '__main__':
    # Configuración de la base de datos
    db_config = {
        'connection_url': 'postgresql://ntejedov:1Al5yWnyXIKRDCDRz9c51thpN7DVUA3m@dpg-cqtg83bv2p9s73dff6ig-a.oregon-postgres.render.com/rss_app_db'
    }

    # Ruta al archivo JSON
    file_path = '.\history.json'

    # Cargar los datos del archivo JSON
    data = load_json(file_path)

    # Actualizar los hashes de las URLs en la base de datos
    update_url_hashes_from_json(data, db_config)

    print("Los hashes de las URLs se han actualizado correctamente en la base de datos.")
