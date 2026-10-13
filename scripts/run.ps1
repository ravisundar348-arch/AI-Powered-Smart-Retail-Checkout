# Starts the API + web UI on http://localhost:8000
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "backend")
& ..\.venv-ai\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000