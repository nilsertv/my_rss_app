# Script de inicio para desarrollo local en Windows

Write-Host "=== My RSS App - Desarrollo Local ===" -ForegroundColor Cyan

# Configurar variables de entorno
$env:FEED_DIR = "./data"
$env:PORT = "8080"

# Crear directorio de datos si no existe
if (-not (Test-Path "./data")) {
    Write-Host "Creando directorio ./data..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path "./data" | Out-Null
}

Write-Host "Variables de entorno configuradas:" -ForegroundColor Green
Write-Host "  FEED_DIR: $env:FEED_DIR" -ForegroundColor White
Write-Host "  PORT: $env:PORT" -ForegroundColor White
Write-Host ""

# Función para limpiar procesos al salir
$cleanup = {
    Write-Host "`nDeteniendo procesos..." -ForegroundColor Yellow
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    Write-Host "Procesos detenidos." -ForegroundColor Green
}

# Registrar manejador de Ctrl+C
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanup | Out-Null

try {
    # Iniciar el servidor web en background
    Write-Host "Iniciando servidor web..." -ForegroundColor Cyan
    $webserver = Start-Job -ScriptBlock {
        $env:FEED_DIR = "./data"
        $env:PORT = "8080"
        python src/webserver.py
    }

    # Esperar un momento para que el servidor inicie
    Start-Sleep -Seconds 3

    Write-Host "Servidor web iniciado (Job ID: $($webserver.Id))" -ForegroundColor Green
    Write-Host "  - Feed RSS: http://localhost:8080/feed" -ForegroundColor White
    Write-Host "  - Health: http://localhost:8080/health" -ForegroundColor White
    Write-Host ""

    # Preguntar si quiere iniciar el worker RSS
    $startWorker = Read-Host "¿Iniciar el worker RSS? (S/N)"
    
    if ($startWorker -eq "S" -or $startWorker -eq "s") {
        Write-Host "Iniciando worker RSS..." -ForegroundColor Cyan
        $worker = Start-Job -ScriptBlock {
            $env:FEED_DIR = "./data"
            python src/main.py
        }
        Write-Host "Worker RSS iniciado (Job ID: $($worker.Id))" -ForegroundColor Green
        Write-Host ""
    }

    Write-Host "=== Aplicación corriendo ===" -ForegroundColor Green
    Write-Host "Presiona Ctrl+C para detener todos los procesos." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Ver logs de los procesos:" -ForegroundColor Cyan
    Write-Host "  Get-Job | Receive-Job" -ForegroundColor White
    Write-Host ""

    # Mantener el script corriendo
    while ($true) {
        # Mostrar estado de los jobs cada 30 segundos
        Start-Sleep -Seconds 30
        
        $jobs = Get-Job
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Estado de procesos:" -ForegroundColor DarkGray
        foreach ($job in $jobs) {
            Write-Host "  - Job $($job.Id): $($job.State)" -ForegroundColor DarkGray
        }
        
        # Verificar si algún job falló
        $failedJobs = Get-Job | Where-Object { $_.State -eq "Failed" }
        if ($failedJobs) {
            Write-Host "¡ADVERTENCIA! Algunos procesos fallaron:" -ForegroundColor Red
            foreach ($job in $failedJobs) {
                Write-Host "  - Job $($job.Id) falló" -ForegroundColor Red
                Receive-Job -Job $job
            }
        }
    }
}
catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
finally {
    # Limpiar al salir
    & $cleanup
}
