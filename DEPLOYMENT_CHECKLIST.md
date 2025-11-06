# ✅ Checklist de Despliegue

Usa este checklist para asegurarte de que todo está configurado correctamente antes de desplegar.

## Pre-Despliegue

### 🔧 Configuración Local
- [ ] Todas las dependencias instaladas (`pip install -r requirements.txt`)
- [ ] Archivo `app/config.yaml` configurado con tus fuentes RSS
- [ ] Archivo `config.json` configurado con tu webhook IFTTT
- [ ] Variables de entorno configuradas (`.env` o variables del sistema)
- [ ] Directorio `./data` creado
- [ ] Servidor web funciona localmente (`python webserver.py`)
- [ ] Worker RSS funciona localmente (`python main.py`)

### 🧪 Testing Local
- [ ] Servidor responde en `http://localhost:8080/health`
- [ ] Feed se genera correctamente en `./data/feed.xml`
- [ ] Endpoints `/feed` y `/feed.xml` retornan el RSS
- [ ] Script de prueba pasa (`python test_server.py`)
- [ ] No hay errores en los logs

### 🔐 Seguridad
- [ ] Credenciales de base de datos actualizadas en `app/config.yaml`
- [ ] Webhook IFTTT correcto en `config.json`
- [ ] `.dockerignore` excluye archivos sensibles
- [ ] `.env` no está commiteado en el repositorio
- [ ] Considerar uso de secrets en producción

## Despliegue Fly.io

### 📦 Preparación
- [ ] Cuenta de Fly.io creada
- [ ] CLI de Fly instalado (`flyctl`)
- [ ] Autenticado en Fly.io (`fly auth login`)
- [ ] Nombre de app disponible (verificar con `fly apps list`)

### 🗄️ Volumen
- [ ] Volumen creado: `fly volumes create rss_feed_data --region scl --size 1`
- [ ] Volumen aparece en `fly volumes list`
- [ ] Región del volumen coincide con la región de la app

### 🚀 Despliegue
- [ ] `fly.toml` configurado correctamente
- [ ] Dockerfile actualizado
- [ ] `start.sh` tiene permisos de ejecución
- [ ] Despliegue ejecutado: `fly deploy`
- [ ] Sin errores en el output del deploy

### ✔️ Verificación Post-Despliegue
- [ ] App aparece en `fly status` como "running"
- [ ] Health check responde: `curl https://my-rss-app.fly.dev/health`
- [ ] Feed accesible: `curl https://my-rss-app.fly.dev/feed`
- [ ] Logs muestran actividad: `fly logs`
- [ ] Worker RSS está procesando fuentes
- [ ] Servidor web responde correctamente

### 📊 Monitoreo
- [ ] Health check configurado en `fly.toml`
- [ ] Logs monitoreables (`fly logs -a my-rss-app`)
- [ ] Alertas configuradas (opcional)
- [ ] Dashboard de Fly.io revisado

## Post-Despliegue

### 📝 Documentación
- [ ] URL del feed documentada
- [ ] Instrucciones de acceso compartidas
- [ ] Ejemplos de uso documentados

### 🔄 Mantenimiento
- [ ] Plan de backups del volumen establecido
- [ ] Procedimiento de actualización documentado
- [ ] Contactos de soporte definidos
- [ ] Calendario de revisiones programadas

### 🐛 Troubleshooting
- [ ] Acceso SSH funciona: `fly ssh console`
- [ ] Permisos del volumen correctos: `fly ssh console -C "ls -la /data"`
- [ ] Feed se actualiza según el intervalo configurado
- [ ] Proceso de reinicio documentado

## Comandos de Emergencia

### 🔄 Reiniciar App
```bash
fly apps restart my-rss-app
```

### 📋 Ver Logs en Tiempo Real
```bash
fly logs -a my-rss-app
```

### 🔍 Inspeccionar Volumen
```bash
fly ssh console -C "ls -la /data"
fly ssh console -C "cat /data/feed.xml | head -50"
```

### 🛑 Detener App (emergencia)
```bash
fly scale count 0
```

### ▶️ Reiniciar App
```bash
fly scale count 1
```

### 🔧 Acceso SSH para Debug
```bash
fly ssh console
# Dentro del contenedor:
cd /data
ls -la
cat feed.xml
ps aux
```

## Métricas de Éxito

- ✅ Uptime > 99%
- ✅ Feed se actualiza cada 600 segundos (10 minutos)
- ✅ Health check siempre responde 200 OK
- ✅ Feed contiene artículos recientes
- ✅ Tamaño del feed < 5MB
- ✅ Tiempo de respuesta < 2 segundos

## Notas Importantes

1. **Un volumen por instancia**: No escalar a más de 1 instancia sin crear volúmenes adicionales
2. **Región consistente**: Volumen y app deben estar en la misma región
3. **Backups**: El volumen no tiene backups automáticos, hacer backups manuales
4. **Costos**: Monitorear uso de recursos en el dashboard de Fly.io
5. **Updates**: Usar `fly deploy` para actualizaciones, el volumen se mantiene

## Contactos y Recursos

- 📚 [Documentación Fly.io](https://fly.io/docs/)
- 💬 [Comunidad Fly.io](https://community.fly.io/)
- 🐛 [Issues del Proyecto](https://github.com/nilsertv/my_rss_app/issues)
- 📧 Soporte: support@fly.io

---

**Fecha del último despliegue:** _________________

**Versión desplegada:** _________________

**Responsable:** _________________
