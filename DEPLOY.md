# Instrucciones de Despliegue en Fly.io

## Pasos para Desplegar

### 1. Crear el volumen persistente

Antes de desplegar, necesitas crear un volumen para almacenar el archivo `feed.xml`:

```bash
fly volumes create rss_feed_data --region scl --size 1
```

**Nota**: El tamaño es en GB. 1GB es más que suficiente para este caso de uso.

### 2. Desplegar la aplicación

```bash
fly deploy
```

### 3. Verificar el despliegue

Después del despliegue, puedes acceder a:

- **Feed RSS**: `https://my-rss-app.fly.dev/feed` o `https://my-rss-app.fly.dev/feed.xml`
- **Health Check**: `https://my-rss-app.fly.dev/health`
- **Info**: `https://my-rss-app.fly.dev/`

### 4. Monitorear los logs

```bash
fly logs
```

## Comandos Útiles

### Ver el estado de la aplicación
```bash
fly status
```

### Ver información del volumen
```bash
fly volumes list
```

### Conectarse via SSH (para debugging)
```bash
fly ssh console
```

### Ver los archivos en el volumen
```bash
fly ssh console -C "ls -la /data"
```

### Ver el contenido del feed
```bash
fly ssh console -C "cat /data/feed.xml"
```

### Escalar la aplicación
```bash
# Aumentar instancias (no recomendado con volúmenes persistentes)
fly scale count 1

# Cambiar el tamaño de la VM
fly scale vm shared-cpu-2x
```

## Actualizar el Volumen

Si necesitas más espacio en el futuro:

```bash
fly volumes extend rss_feed_data --size 2
```

## Recrear el Volumen (CUIDADO: Borra los datos)

Si necesitas recrear el volumen desde cero:

```bash
# 1. Detener la aplicación
fly scale count 0

# 2. Eliminar el volumen existente
fly volumes delete rss_feed_data

# 3. Crear nuevo volumen
fly volumes create rss_feed_data --region scl --size 1

# 4. Reiniciar la aplicación
fly scale count 1
```

## Notas Importantes

1. **Un volumen por instancia**: Fly.io requiere que cada instancia tenga su propio volumen. Por eso mantenemos `min_machines_running = 1`.

2. **Persistencia**: El archivo `feed.xml` se mantendrá incluso si la aplicación se reinicia o se redespliega.

3. **Backups**: Considera hacer backups periódicos del volumen usando:
   ```bash
   fly ssh console -C "cat /data/feed.xml" > backup_feed.xml
   ```

4. **Región**: El volumen debe estar en la misma región que la aplicación (`scl` - Santiago, Chile).

## Troubleshooting

### El feed no se genera

1. Verifica los logs:
   ```bash
   fly logs
   ```

2. Verifica que el volumen esté montado:
   ```bash
   fly ssh console -C "df -h /data"
   ```

### Error de permisos

Si hay problemas de permisos en el volumen:
```bash
fly ssh console -C "chmod 777 /data"
```

### La aplicación no responde

1. Verifica el health check:
   ```bash
   curl https://my-rss-app.fly.dev/health
   ```

2. Reinicia la aplicación:
   ```bash
   fly apps restart my-rss-app
   ```
