# 🚀 Guía Rápida de Inicio

## Desarrollo Local

### Opción 1: Script Automático (Windows)
```powershell
.\start-local.ps1
```

### Opción 2: Manual

#### Windows PowerShell:
```powershell
# Configurar variables
$env:FEED_DIR="./data"
$env:PORT="8080"

# Crear directorio
New-Item -ItemType Directory -Path "./data" -Force

# Terminal 1: Servidor Web
python webserver.py

# Terminal 2: Worker RSS
python main.py
```

#### Linux/Mac:
```bash
# Configurar variables
export FEED_DIR="./data"
export PORT="8080"

# Crear directorio
mkdir -p ./data

# Terminal 1: Servidor Web
python webserver.py

# Terminal 2: Worker RSS
python main.py
```

## Verificar Instalación

### 1. Probar servidor web
```bash
# Windows PowerShell
Invoke-WebRequest http://localhost:8080/health | Select-Object -Expand Content

# Linux/Mac
curl http://localhost:8080/health
```

### 2. Ejecutar tests
```bash
python test_server.py
```

### 3. Ver el feed RSS
Abrir en navegador: http://localhost:8080/feed

## Despliegue en Fly.io

### Primera vez:
```bash
# 1. Crear volumen
fly volumes create rss_feed_data --region scl --size 1

# 2. Desplegar
fly deploy
```

### Actualizaciones:
```bash
fly deploy
```

### Monitoreo:
```bash
# Ver logs en tiempo real
fly logs

# Ver estado
fly status

# Health check
curl https://my-rss-app.fly.dev/health
```

## Endpoints Disponibles

| Endpoint | Descripción |
|----------|-------------|
| `/` | Información de la API |
| `/feed` | Feed RSS XML |
| `/feed.xml` | Alias para `/feed` |
| `/health` | Estado del servidor y feed |

## Troubleshooting Rápido

### ❌ Error: "Feed not found"
**Solución:** El feed aún no se ha generado. Espera a que el worker complete un ciclo.

### ❌ Error: "Module not found"
**Solución:** Instala las dependencias:
```bash
pip install -r requirements.txt
```

### ❌ Error: "Permission denied" (Fly.io)
**Solución:** Ajusta permisos del volumen:
```bash
fly ssh console -C "chmod 777 /data"
```

### ❌ El worker no actualiza el feed
**Solución:** Verifica los logs:
```bash
# Local
# Revisar la terminal donde corre main.py

# Fly.io
fly logs
```

## Archivos Importantes

- `app/config.yaml` - Configuración de fuentes RSS
- `config.json` - Configuración de IFTTT
- `.env.example` - Template de variables de entorno
- `DEPLOY.md` - Guía completa de despliegue
- `CHANGES.md` - Resumen de cambios recientes

## Comandos Útiles

```bash
# Ver estructura del proyecto
tree /F

# Limpiar archivos Python compilados
# Windows
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item
Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse

# Linux/Mac
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -delete

# Ver tamaño del feed
# Windows
Get-Item ./data/feed.xml | Select-Object Name, Length

# Linux/Mac
ls -lh ./data/feed.xml
```

## Recursos

- 📖 [README Completo](README.md)
- 🚀 [Guía de Despliegue](DEPLOY.md)
- 📝 [Changelog](CHANGES.md)
- 🐛 [Reportar Issues](https://github.com/nilsertv/my_rss_app/issues)

---

**¿Necesitas ayuda?** Consulta la documentación completa o revisa los logs para más detalles.
