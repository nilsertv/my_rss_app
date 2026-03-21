# Usa una imagen base de Python
FROM python:3.9-slim

# Establecer el directorio de trabajo
WORKDIR /workspace

# Instalar Poetry
RUN pip install --no-cache-dir poetry

# Copiar archivos de Poetry
COPY pyproject.toml poetry.lock ./

# Configurar Poetry para no crear virtualenv y instalar dependencias
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root --only main

# Copiar el resto de los archivos de la aplicación
COPY . .

# Configurar PYTHONPATH para que Python encuentre el paquete src
ENV PYTHONPATH=/workspace

# Hacer el script de inicio ejecutable
RUN chmod +x start.sh

# Crear el directorio de datos con permisos apropiados
RUN mkdir -p /data && chmod 777 /data

# Excluir archivos de logs y otros innecesarios usando .dockerignore (se detalla abajo)
# Crear un volumen para los logs
#VOLUME /app/logs

# Exponer el puerto que la aplicación utilizará
EXPOSE 8080

# Comando para ejecutar la aplicación
CMD ["sh", "start.sh"]
