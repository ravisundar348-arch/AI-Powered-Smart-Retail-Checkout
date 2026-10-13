# Prompts for a password; nothing is hardcoded. Usage: scripts\create_admin.ps1 -Username shopowner [-Seed]
param([Parameter(Mandatory=$true)][string]$Username, [switch]$Seed)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "backend")
$Python = (Resolve-Path ..\.venv\Scripts\python.exe).Path
& $Python -m app.manage provision-admin --username $Username
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($Seed) {
    & $Python -m app.manage seed-catalog
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
