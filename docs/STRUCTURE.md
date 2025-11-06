# Estructura del Proyecto

```
my-rss-app/
├── src/                      # Código fuente principal
│   ├── core/                 # Módulos core del negocio
│   │   ├── fetcher.py        # Fetching de RSS/Web/YouTube
│   │   └── rss_generator.py  # Generación de feed RSS
│   ├── utils/                # Utilidades
│   │   └── logger.py         # Configuración de logging
│   ├── main.py               # Worker principal (loop fetch → DB → RSS)
│   ├── process_rss.py        # Procesador IFTTT
│   ├── webserver.py          # Servidor Flask
│   └── config.yaml           # Configuración de fuentes RSS
├── data/                     # Datos persistentes (feed.xml, feed_new.xml)
├── logs/                     # Archivos de log
├── tests/                    # Tests unitarios
├── config.json               # Configuración IFTTT
├── pyproject.toml            # Dependencias Poetry
├── Dockerfile                # Container build
├── fly.toml                  # Configuración Fly.io
├── start.sh                  # Entrypoint para producción
├── start-local.ps1           # Desarrollo local Windows
└── run-local.ps1             # Ejecutar worker localmente
```

## Ejecución Local

```powershell
# Opción 1: Solo worker
.\run-local.ps1

# Opción 2: Web server + worker
.\start-local.ps1
```

## Ejecución en Producción (Fly.io)

```powershell
fly deploy --no-cache
```
