[CmdletBinding()]
param(
    [string] $Address = "0.0.0.0:8000"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found. Run $root\scripts\bootstrap-dev-machine.ps1 first."
}

Set-Location $root
& $python manage.py migrate
if ($LASTEXITCODE -ne 0) {
    throw "Database migration failed."
}

Write-Host "Starting DDMP at http://$Address/"
Write-Host "Local access: http://127.0.0.1:8000/"
Write-Host "Wi-Fi access: use this computer's WLAN IPv4 address with port 8000."
& $python manage.py runserver $Address
