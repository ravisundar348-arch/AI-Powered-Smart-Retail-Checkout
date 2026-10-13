# Prompts for a password; nothing is hardcoded.  Usage: scripts\create_admin.ps1 -Username shopowner [-Seed]
param([Parameter(Mandatory=$true)][string]$Username, [string]$Role = "admin", [switch]$Seed)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path (Split-Path $PSScriptRoot -Parent) "backend")
& ..\.venv\Scripts\python.exe -m app.manage create-user --username $Username --role $Role
if ($Seed) { & ..\.venv\Scripts\python.exe -m app.manage seed-catalog }
