# Imagen base moderna y ligera
FROM python:3.11-slim

# Evitar generación de .pyc y forzar buffer inmediato de stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace \
    PORT=8080 \
    FEED_DIR=/data

WORKDIR /workspace

# Instalar curl para HEALTHCHECK y dependencias de sistema si fueran necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install --no-cache-dir "poetry>=1.8.0"

# Copiar configuración de dependencias de Poetry
COPY pyproject.toml poetry.lock ./

# Instalar dependencias en el sistema global del contenedor sin virtualenv
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

# Crear directorio de datos persistente para el feed y logs
RUN mkdir -p /data /workspace/logs && chmod 777 /data /workspace/logs

# Copiar el código de la aplicación
COPY . .

# Asegurar permisos de ejecución en el script de arranque
RUN chmod +x start.sh

# Puerto expuesto por defecto
EXPOSE 8080

# Healthcheck nativo para monitorización automática en Coolify / Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Arrancar con bash para soportar job control y señales
CMD ["bash", "start.sh"]
