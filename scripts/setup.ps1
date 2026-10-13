# Creates the virtual environment and installs dependencies. Run from the project root:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1            (app only)
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -WithAI    (also TensorFlow + Ultralytics, large download)
param([switch]$WithAI)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if ($WithAI) {
  Write-Host "Installing AI packages (TensorFlow + PyTorch/Ultralytics: several GB)..."
  & .\.venv\Scripts\python.exe -m pip install -r backend\requirements-ai.txt
}
if (-not (Test-Path "backend\.env")) {
  $key = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
  (Get-Content backend\.env.example) -replace '^SMART_SECRET_KEY=.*', "SMART_SECRET_KEY=$key" | Set-Content backend\.env
  Write-Host "Created backend\.env with a fresh secret key."
}
Push-Location backend
& ..\.venv\Scripts\python.exe -m app.manage init-db
Pop-Location
Write-Host "`nNext: create an admin user ->  scripts\create_admin.ps1"
