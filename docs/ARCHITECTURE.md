# 📐 Arquitectura del Sistema - Detallada

## Vista General del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FLY.IO MACHINE                             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      start.sh (PID 1)                        │  │
│  │                                                              │  │
│  │  ┌───────────────────┐         ┌─────────────────────┐      │  │
│  │  │  webserver.py     │         │     main.py         │      │  │
│  │  │  (Flask Server)   │         │   (RSS Worker)      │      │  │
│  │  │                   │         │                     │      │  │
│  │  │  Port: 8080       │         │  Loop: 600s         │      │  │
│  │  │  ┌─────────────┐  │         │  ┌──────────────┐   │      │  │
│  │  │  │ GET /       │  │         │  │   Fetcher    │   │      │  │
│  │  │  │ GET /feed   │  │         │  │   - RSS      │   │      │  │
│  │  │  │ GET /health │  │         │  │   - Web      │   │      │  │
│  │  │  └─────────────┘  │         │  │   - YouTube  │   │      │  │
│  │  │         │         │         │  └──────┬───────┘   │      │  │
│  │  │         │         │         │         │           │      │  │
│  │  │         ▼         │         │         ▼           │      │  │
│  │  │  ┌─────────────┐  │         │  ┌──────────────┐   │      │  │
│  │  │  │ /data/      │◄─┼─────────┼──┤RSS Generator │   │      │  │
│  │  │  │ feed.xml    │  │         │  │ (feed.xml)   │   │      │  │
│  │  │  └─────────────┘  │         │  └──────┬───────┘   │      │  │
│  │  └───────────────────┘         │         │           │      │  │
│  │                                │         ▼           │      │  │
│  │                                │  ┌──────────────┐   │      │  │
│  │                                │  │process_rss.py│   │      │  │
│  │                                │  │(IFTTT sender)│   │      │  │
│  │                                │  └──────────────┘   │      │  │
│  └────────────────────────────────┴─────────────────────┴──────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                   VOLUME: rss_feed_data                      │  │
│  │                   Mount Point: /data                         │  │
│  │                   Size: 1GB                                  │  │
│  │                   Persistent: Yes                            │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │   EXTERNAL SERVICES     │
                 │                         │
                 │  • PostgreSQL (History) │
                 │  • IFTTT Webhooks       │
                 │  • RSS Feeds            │
                 │  • YouTube API          │
                 │  • Web Pages            │
                 └─────────────────────────┘
```

## Flujo de Datos Detallado

### 1. Inicialización (Boot)

```
Container Start
    │
    ├─► start.sh ejecutado
    │       │
    │       ├─► Crea /data si no existe
    │       │
    │       ├─► Inicia webserver.py en background
    │       │       │
    │       │       └─► Flask app listening on :8080
    │       │
    │       └─► Inicia main.py en background
    │               │
    │               └─► RSS Worker loop iniciado
    │
    └─► Ambos procesos corriendo en paralelo
```

### 2. Ciclo de Actualización RSS (main.py)

```
[INICIO DEL CICLO - Cada 600s]
    │
    ├─► load_config()
    │       └─► Lee app/config.yaml
    │
    ├─► Fetcher.fetch_latest()
    │       │
    │       ├─► Para cada sección en config:
    │       │       │
    │       │       ├─► fetch_rss_feed(url)
    │       │       ├─► fetch_html_page(url)
    │       │       └─► fetch_youtube(url)
    │       │
    │       ├─► Genera URL hash (SHA-256)
    │       │
    │       ├─► Verifica en PostgreSQL si existe
    │       │       │
    │       │       └─► SELECT * FROM rss_history WHERE url_hash = ?
    │       │
    │       └─► Si es nuevo:
    │               └─► INSERT INTO rss_history
    │
    ├─► RSSGenerator.generate_rss()
    │       │
    │       ├─► Crea estructura XML
    │       │
    │       ├─► Para cada post:
    │       │       └─► <item>
    │       │               ├─► <title>#Seccion Titulo</title>
    │       │               ├─► <link>URL</link>
    │       │               └─► <description>Content</description>
    │       │
    │       └─► Guarda en /data/feed.xml
    │
    ├─► process_rss.py ejecutado
    │       │
    │       ├─► Lee /data/feed.xml
    │       │
    │       ├─► Para cada <item>:
    │       │       │
    │       │       ├─► POST a IFTTT webhook
    │       │       │       └─► { value1: title, value2: link, value3: desc }
    │       │       │
    │       │       └─► Espera post_delay (225s)
    │       │
    │       └─► Finaliza
    │
    ├─► Sleep(interval)
    │
    └─► [REINICIA EL CICLO]
```

### 3. Servidor Web (webserver.py)

```
Flask App
    │
    ├─► GET /
    │       └─► JSON: { service: "...", endpoints: [...] }
    │
    ├─► GET /feed
    │   GET /feed.xml
    │       │
    │       ├─► Verifica si existe /data/feed.xml
    │       │       │
    │       │       ├─► Sí: send_file(feed.xml, mimetype='application/xml')
    │       │       │
    │       │       └─► No: 404 JSON { error: "Feed not found" }
    │       │
    │       └─► Respuesta
    │
    └─► GET /health
            │
            ├─► Verifica /data/feed.xml
            │
            └─► JSON: {
                    status: "healthy",
                    feed_exists: true/false,
                    feed_size: bytes,
                    feed_path: "/data/feed.xml"
                }
```

## Componentes del Sistema

### 🐳 Container (Docker)

```dockerfile
FROM python:3.9-slim
WORKDIR /
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
RUN chmod +x start.sh
RUN mkdir -p /data
EXPOSE 8080
CMD ["sh", "start.sh"]
```

### 📦 Volumen Persistente

```yaml
[mounts]
  source = "rss_feed_data"  # Volumen en Fly.io
  destination = "/data"      # Mount point en container
```

**Características:**
- Tamaño: 1GB
- Persistente: Sobrevive reinicios y redeploys
- Compartido: Accesible por webserver.py y main.py
- Ubicación: Mismo datacenter que la app

### 🔄 Gestión de Procesos (start.sh)

```bash
start.sh
    │
    ├─► python webserver.py &  (Background)
    │       └─► WEBSERVER_PID=$!
    │
    ├─► python main.py &        (Background)
    │       └─► WORKER_PID=$!
    │
    └─► Monitoring Loop
            │
            ├─► Check WEBSERVER_PID alive
            │       └─► Si murió: Reiniciar
            │
            ├─► Check WORKER_PID alive
            │       └─► Si murió: Reiniciar
            │
            └─► Sleep 10s y repetir
```

## Endpoints y Respuestas

### GET /

```json
{
  "service": "RSS Feed Server",
  "endpoints": {
    "/feed": "RSS Feed XML",
    "/feed.xml": "RSS Feed XML (alias)",
    "/health": "Health check"
  }
}
```

### GET /feed, /feed.xml

**Headers:**
```
Content-Type: application/xml
```

**Body:**
```xml
<?xml version='1.0' encoding='utf-8'?>
<rss version="2.0">
  <channel>
    <title>Latest Posts and Videos</title>
    <link>http://example.com/rss</link>
    <description>This RSS feed contains...</description>
    <item>
      <title>#Noticias Título del artículo</title>
      <link>https://example.com/article</link>
      <description>Contenido del artículo...</description>
    </item>
    <!-- más items -->
  </channel>
</rss>
```

### GET /health

```json
{
  "status": "healthy",
  "feed_exists": true,
  "feed_size": 12345,
  "feed_path": "/data/feed.xml"
}
```

## Base de Datos PostgreSQL

### Tabla: rss_history

```sql
CREATE TABLE rss_history (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    url_hash TEXT UNIQUE NOT NULL,
    title TEXT,
    content TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);
```

**Propósito:** Evitar duplicados de artículos procesados

**Flujo:**
1. Generar SHA-256 hash de la URL
2. Verificar si existe en la tabla
3. Si no existe, insertar y procesar
4. Si existe, saltar (ya fue procesado)

## Variables de Entorno

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `FEED_DIR` | `/data` | Directorio del volumen persistente |
| `PORT` | `8080` | Puerto del servidor web Flask |

## Puertos y Networking

```
Internet
    │
    ├─► https://my-rss-app.fly.dev
    │       │
    │       └─► Fly.io Proxy
    │               │
    │               └─► Container :8080
    │                       │
    │                       └─► Flask App (webserver.py)
    │
    └─► Usuarios/Clientes RSS
```

## Ciclo de Vida

```
Deploy → Build → Start → Monitor → Update → Restart
   │        │       │        │         │        │
   │        │       │        │         │        └─► Mantiene /data
   │        │       │        │         │
   │        │       │        │         └─► fly deploy
   │        │       │        │
   │        │       │        └─► Health checks cada 30s
   │        │       │
   │        │       └─► start.sh inicia ambos procesos
   │        │
   │        └─► Dockerfile build
   │
   └─► fly deploy comando
```

## Resiliencia y Recuperación

### Proceso Muere
```
start.sh detecta proceso muerto
    │
    └─► Reinicia automáticamente
```

### Container Reinicia
```
Fly.io reinicia container
    │
    ├─► /data persiste (volumen)
    │
    └─► start.sh inicia ambos procesos
```

### Feed Corrupto
```
Siguiente ciclo de main.py
    │
    └─► Regenera feed.xml desde DB
```

## Monitoreo y Logs

```
fly logs
    │
    ├─► webserver.py logs
    │       ├─► Requests recibidos
    │       └─► Errores de servidor
    │
    └─► main.py logs
            ├─► Fetcher actividad
            ├─► RSS generation
            └─► Process_rss ejecución
```

---

**Última actualización:** Noviembre 5, 2025
