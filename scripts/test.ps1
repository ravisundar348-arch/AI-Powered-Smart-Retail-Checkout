Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "backend")
& ..\.venv\Scripts\python.exe -m pytest -v
