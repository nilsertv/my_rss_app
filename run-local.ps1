# Script para ejecutar main.py localmente con encoding UTF-8

# Configurar UTF-8 en PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# Ejecutar main.py
poetry run python main.py
