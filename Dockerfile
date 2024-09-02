# Usa una imagen base de Python
FROM python:3.9-slim

# Establecer el directorio de trabajo en /app
WORKDIR /

# Copiar solo los archivos de requirements primero (para mejorar el cacheo de Docker)
COPY requirements.txt ./

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos de la aplicación
COPY . .

# Excluir archivos de logs y otros innecesarios usando .dockerignore (se detalla abajo)
# Crear un volumen para los logs
#VOLUME /app/logs

# Exponer el puerto que la aplicación utilizará (si es necesario)
#EXPOSE 5000

# Comando para ejecutar la aplicación
CMD ["python", "main.py"]
