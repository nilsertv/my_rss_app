#!/bin/bash

# Script de inicio para ejecutar ambos procesos

# Crear directorio de datos si no existe
mkdir -p /data

# Asegurar permisos de escritura en /data
chmod 777 /data

# Iniciar el servidor web en background
echo "Starting web server..."
python webserver.py &
WEBSERVER_PID=$!

# Esperar un momento para que el servidor inicie
sleep 3

# Iniciar el worker principal
echo "Starting RSS worker..."
python main.py &
WORKER_PID=$!

# Función para manejar señales de terminación
cleanup() {
    echo "Shutting down..."
    kill $WEBSERVER_PID $WORKER_PID 2>/dev/null
    wait $WEBSERVER_PID $WORKER_PID
    exit 0
}

# Registrar manejador de señales
trap cleanup SIGTERM SIGINT

# Mantener el script corriendo y monitorear los procesos
while true; do
    # Verificar si los procesos están corriendo
    if ! kill -0 $WEBSERVER_PID 2>/dev/null; then
        echo "Web server died, restarting..."
        python webserver.py &
        WEBSERVER_PID=$!
    fi
    
    if ! kill -0 $WORKER_PID 2>/dev/null; then
        echo "Worker died, restarting..."
        python main.py &
        WORKER_PID=$!
    fi
    
    sleep 10
done
