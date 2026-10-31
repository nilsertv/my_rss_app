# 📰 My RSS App

Aplicación automatizada para agregar, procesar y distribuir contenido de múltiples fuentes RSS, páginas web y canales de YouTube.

> 🚀 **[Ver Guía Rápida de Inicio](QUICKSTART.md)** | 📚 **[Guía de Despliegue](DEPLOY.md)** | 📐 **[Arquitectura Detallada](ARCHITECTURE.md)**

## 📋 Descripción

**My RSS App** es un agregador de contenido inteligente que recopila las últimas publicaciones de diversas fuentes (feeds RSS, páginas web y videos de YouTube), las almacena en una base de datos PostgreSQL, genera un feed RSS unificado y las distribuye automáticamente a través de webhooks de IFTTT.

### ✨ Características Principales

- 🔄 **Agregación Multi-fuente**: Soporte para RSS feeds, scraping web y canales de YouTube
- 🗄️ **Persistencia en Base de Datos**: Almacenamiento en PostgreSQL con prevención de duplicados mediante hashing
- 📡 **Generación de RSS**: Creación de un feed RSS unificado con todas las publicaciones
- 🌐 **Servidor Web**: Servidor Flask para publicar el feed RSS via HTTP
- 💾 **Volumen Persistente**: Almacenamiento persistente en Fly.io para el archivo feed.xml
- 🔔 **Integración IFTTT**: Envío automático de contenido a través de webhooks
- ⏰ **Ejecución Periódica**: Sistema de polling configurable para actualizaciones automáticas
- 📊 **Logging Completo**: Sistema de registro para monitoreo y debugging
- 🐳 **Dockerizado**: Listo para despliegue en contenedores
- ☁️ **Cloud Ready**: Configurado para Fly.io y otros servicios cloud

## 🏗️ Arquitectura

```
┌─────────────┐
│   main.py   │  ← Orquestador principal (loop infinito)
└──────┬──────┘
       │
       ├─────────────────────────────────────┐
       │                                     │
       ▼                                     ▼
┌─────────────┐                    ┌──────────────┐
│  Fetcher    │                    │process_rss.py│
│             │                    │              │
│ • RSS feeds │                    │ • Lee feed.xml
│ • Web scraping                   │ • POST a IFTTT
│ • YouTube   │                    └──────────────┘
└──────┬──────┘
       │
       ▼
┌─────────────┐       ┌──────────────┐       ┌──────────────┐
│  PostgreSQL │       │RSSGenerator  │       │ webserver.py │
│             │       │              │       │              │
│ (History)   │       │ /data/       │◄──────┤ Flask Server │
└─────────────┘       │ feed.xml     │       │ :8080        │
                      └──────────────┘       └──────────────┘
                             │                       │
                             └───── Volumen ─────────┘
                                   Persistente
                                   (Fly.io)
```

## 📁 Estructura del Proyecto

```
my-rss-app/
├── src/                     # Código fuente principal
│   ├── core/                # Módulos core
│   │   ├── fetcher.py       # Lógica de obtención de contenido
│   │   └── rss_generator.py # Generación del feed RSS
│   ├── utils/               # Utilidades
│   │   └── logger.py        # Configuración de logging
│   ├── main.py              # Script principal (loop de ejecución)
│   ├── webserver.py         # Servidor Flask para servir feed.xml
│   ├── process_rss.py       # Procesador y distribuidor IFTTT
│   └── config.yaml          # Configuración de fuentes RSS
├── legacy/                  # Archivos legacy (no en uso)
│   ├── history.json         # Historial JSON (supersedido por PostgreSQL)
│   ├── import_data.py       # Script de migración (ya ejecutado)
│   ├── read_rss.py          # Utilidad de debug
│   ├── Procfile             # Heroku config (proyecto usa Fly.io)
│   ├── requirements.txt     # pip requirements (proyecto usa Poetry)
│   └── README.md            # Documentación de archivos legacy
├── tests/
│   └── test_fetcher.py      # Tests unitarios
├── data/                    # Datos persistentes
│   ├── feed.xml             # Feed RSS generado
│   └── feed_new.xml         # Feed con posts nuevos (para IFTTT)
├── logs/                    # Archivos de logging
├── config.json              # Configuración de webhooks IFTTT
├── pyproject.toml           # Dependencias Poetry
├── poetry.lock              # Lock file Poetry
├── Dockerfile               # Imagen Docker
├── .dockerignore            # Archivos excluidos del build
├── fly.toml                 # Configuración Fly.io
├── start.sh                 # Entrypoint para producción
├── start-local.ps1          # Desarrollo local Windows
├── run-local.ps1            # Ejecutar worker solo
├── DEPLOY.md                # Guía de despliegue Fly.io
├── ARCHITECTURE.md          # Arquitectura detallada
├── QUICKSTART.md            # Guía rápida de inicio
├── STRUCTURE.md             # Documentación de estructura
└── README.md                # Este archivo
```

## 🚀 Instalación y Uso

### Prerequisitos

- Python 3.9+
- PostgreSQL
- Cuenta de IFTTT con webhook configurado

### Instalación Local

1. **Clonar el repositorio**
```bash
git clone <repository-url>
cd my-rss-app
```

2. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

3. **Configurar la base de datos**

Edita `app/config.yaml` con tu URL de conexión PostgreSQL:
```yaml
database:
  connection_url: "postgresql://user:password@host:port/database"
```

4. **Configurar webhooks IFTTT**

Edita `config.json`:
```json
{
  "ifttt_webhook_url": "https://maker.ifttt.com/trigger/EVENT/with/key/YOUR_KEY",
  "initial_prompt": "Please summarize the following article/video for Twitter:",
  "post_delay": 225
}
```

5. **Configurar fuentes de contenido**

Edita `app/config.yaml` para agregar/modificar fuentes:
```yaml
sections:
  NombreSeccion:
    - url: "https://example.com/feed"
      type: "rss"  # rss, web, o youtube
```

6. **Ejecutar la aplicación**
```bash
python main.py
```

### 🪟 Desarrollo en Windows

Para facilitar el desarrollo en Windows, usa el script PowerShell incluido:

```powershell
# Ejecutar con el script automático
.\start-local.ps1

# O manualmente configurar variables de entorno
$env:FEED_DIR="./data"
$env:PORT="8080"

# Crear directorio de datos
New-Item -ItemType Directory -Path "./data" -Force

# Iniciar servidor web (en una terminal)
python webserver.py

# Iniciar worker RSS (en otra terminal)
python main.py
```

### 🐳 Despliegue con Docker

```bash
# Construir imagen
docker build -t my-rss-app .

# Ejecutar contenedor
docker run -d my-rss-app
```

### 🧭 Feeds públicos curados y dominio (Coolify)

Cada feed personalizado se sirve en `https://<dominio>/<slug>.xml` (también en `/feeds/<slug>.xml`). Un feed combina reglas (secciones, palabra clave) con entradas elegidas a mano desde el lector, sin duplicados; con la opción "solo entradas elegidas a mano" ignora las reglas.

- Dominio de producción: `feed-rss.ntv-app.com` (feed de Peruinformado: `https://feed-rss.ntv-app.com/peruinformado.xml`).
- Variable `APP_URL=https://feed-rss.ntv-app.com`: las URLs públicas que muestra el panel usan este valor.
- En Coolify: agrega el dominio `feed-rss.ntv-app.com` a la aplicación y apunta su registro DNS al servidor.
- En el panel, crea el feed con "Crear feed peruinformado" y agrega entradas con el botón Agregar (atajos: `j`/`k` navegar, `a` agregar o quitar, `/` buscar).

### ☁️ Despliegue en Fly.io

#### 1. Crear el volumen persistente

```bash
fly volumes create rss_feed_data --region scl --size 1
```

#### 2. Desplegar

```bash
fly deploy
```

#### 3. Acceder al feed RSS

Una vez desplegado, tu feed estará disponible en:
- `https://my-rss-app.fly.dev/feed`
- `https://my-rss-app.fly.dev/feed.xml`

#### 4. Verificar estado

```bash
# Ver logs
fly logs

# Ver estado
fly status

# Health check
curl https://my-rss-app.fly.dev/health
```

**Ver guía completa de despliegue en [DEPLOY.md](DEPLOY.md)**

## ⚙️ Configuración

### Variables de Entorno

```bash
FEED_DIR=/data          # Directorio para el feed RSS persistente
PORT=8080               # Puerto del servidor web
```

### `app/config.yaml`

```yaml
interval: 600                    # Intervalo de ejecución (segundos)
log_file: "app.log"             # Archivo de logs
ifttt_webhook_url: "..."        # Webhook de notificación de proceso completado
history_file: "history.json"    # Archivo de historial (legacy)

database:
  connection_url: "postgresql://..." # Conexión PostgreSQL

sections:
  SeccionEjemplo:
    - url: "https://example.com/feed"
      type: "rss"               # Tipos: rss, web, youtube
```

### `config.json`

```json
{
  "ifttt_webhook_url": "URL del webhook IFTTT para publicaciones",
  "initial_prompt": "Prompt inicial para el procesamiento",
  "post_delay": 225  // Delay entre publicaciones (segundos)
}
```

## 📊 Fuentes Configuradas

El proyecto viene pre-configurado con las siguientes categorías de contenido:

- **🎥 YouTube**: Canales de tech y educación
- **📰 Noticias**: Medios peruanos e independientes
- **🌎 Internacionales**: Noticias de LATAM y el mundo
- **🔬 Ciencia y Tech**: Tecnología, ciencia e innovación
- **🎬 Cine y TV**: Entretenimiento y cultura pop
- **🐾 Mascotas**: Contenido sobre animales
- **💊 Salud**: Noticias de salud y bienestar
- **🔮 Curiosidades**: Contenido interesante y curioso

## 🔄 Flujo de Trabajo

1. **Fetch** (`fetcher.py`):
   - Obtiene el último post de cada fuente configurada
   - Genera un hash único por URL para evitar duplicados
   - Verifica en PostgreSQL si ya fue procesado
   - Guarda nuevos posts en la base de datos

2. **Generate** (`rss_generator.py`):
   - Crea un feed RSS con todos los posts nuevos
   - Añade el tag de sección a cada item: `#Seccion Título`
   - Guarda el feed en `/data/feed.xml` (volumen persistente)

3. **Serve** (`webserver.py`):
   - Servidor Flask que sirve el feed RSS via HTTP
   - Endpoint `/feed` y `/feed.xml` para acceder al RSS
   - Health check en `/health`
   - Se ejecuta en paralelo con el worker principal

4. **Process** (`process_rss.py`):
   - Lee el feed RSS generado
   - Envía cada entry a IFTTT via webhook
   - Aplica delay configurable entre publicaciones
   - Salta entries con "No Content"

4. **Process** (`process_rss.py`):
   - Lee el feed RSS generado
   - Envía cada entry a IFTTT via webhook
   - Aplica delay configurable entre publicaciones
   - Salta entries con "No Content"

5. **Loop** (`main.py`):
   - Ejecuta el ciclo completo cada X segundos (configurable)
   - Mantiene logs de todas las operaciones
   - Maneja errores y excepciones

## 🌐 Endpoints del Servidor Web

Una vez desplegado, el servidor web expone los siguientes endpoints:

- **`/`** - Información de la API y endpoints disponibles
- **`/feed`** - Feed RSS XML completo
- **`/feed.xml`** - Alias para `/feed`
- **`/health`** - Health check con información del estado del feed

### Ejemplo de uso:

```bash
# Obtener el feed RSS
curl https://my-rss-app.fly.dev/feed

# Verificar el estado
curl https://my-rss-app.fly.dev/health

# Ver información de la API
curl https://my-rss-app.fly.dev/
```

## 🛠️ Dependencias Principales

```
feedparser==6.0.11      # Parser de feeds RSS
beautifulsoup4==4.12.3  # Web scraping
requests==2.32.3        # HTTP requests
psycopg2-binary==2.9.9  # PostgreSQL
PyYAML==6.0.1           # Configuración YAML
aiohttp==3.9.5          # HTTP asíncrono
Flask==3.0.3            # Framework web (opcional)
gunicorn==22.0.0        # WSGI server
```

## 🧪 Testing

Ejecutar tests unitarios:

```bash
python -m unittest tests/test_fetcher.py
```

## 📝 Scripts Auxiliares

### `read_rss.py`
Utilidad para leer y mostrar el contenido del feed RSS generado:
```bash
python read_rss.py
```

### `import_data.py`
Script de migración para actualizar hashes en la base de datos desde `history.json`:
```bash
python import_data.py
```

## 🔐 Seguridad

⚠️ **IMPORTANTE**: Este repositorio contiene credenciales hardcodeadas en los archivos de configuración. Para uso en producción:

1. Usar variables de entorno
2. Implementar gestión de secretos (AWS Secrets Manager, etc.)
3. Nunca commitear credenciales reales al repositorio
4. Rotar credenciales expuestas

## 📈 Monitoreo

La aplicación genera logs detallados de todas las operaciones:

- Fetch de cada fuente
- Posts nuevos detectados
- Generación del RSS
- Publicaciones a IFTTT
- Errores y excepciones

Los logs se envían a stdout y pueden ser capturados por sistemas de logging cloud.

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## 👤 Autor

**Nils Tejedor**
- GitHub: [@nilsertv](https://github.com/nilsertv)

## 🙏 Agradecimientos

- Fuentes de contenido utilizadas
- Comunidad open source de Python
- IFTTT por su API de webhooks

---

**⭐ Si este proyecto te resulta útil, considera darle una estrella en GitHub!**
