#!/bin/bash
set -e

echo "Starting My RSS App services..."

# Asegurar existencia de directorio de datos y logs
DATA_DIRECTORY="${FEED_DIR:-/data}"
mkdir -p "$DATA_DIRECTORY"
mkdir -p "./logs"

# Iniciar Gunicorn para el servidor web en background
echo "Starting Gunicorn Web Server on 0.0.0.0:${PORT:-8080}..."
gunicorn \
    --workers 2 \
    --bind "0.0.0.0:${PORT:-8080}" \
    --access-logfile - \
    --error-logfile - \
    src.webserver:app &
WEBSERVER_PID=$!

# Esperar para verificación inicial
sleep 2

# Iniciar el worker RSS en background
echo "Starting RSS Worker Daemon..."
python -m src.main &
WORKER_PID=$!

# Manejador de señales de terminación limpia (Coolify envía SIGTERM al detener/replegar)
cleanup() {
    echo "Termination signal received. Stopping services gracefully..."
    kill -TERM "$WEBSERVER_PID" "$WORKER_PID" 2>/dev/null || true
    wait "$WEBSERVER_PID" "$WORKER_PID" 2>/dev/null || true
    echo "All services stopped."
    exit 0
}

trap cleanup SIGTERM SIGINT

# Monitorear procesos en bucle
while true; do
    if ! kill -0 "$WEBSERVER_PID" 2>/dev/null; then
        echo "Web server exited. Restarting Gunicorn..."
        gunicorn \
            --workers 2 \
            --bind "0.0.0.0:${PORT:-8080}" \
            --access-logfile - \
            --error-logfile - \
            src.webserver:app &
        WEBSERVER_PID=$!
    fi
    
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
        echo "RSS Worker exited. Restarting Worker..."
        python -m src.main &
        WORKER_PID=$!
    fi
    
    sleep 5
done
