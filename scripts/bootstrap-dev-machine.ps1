<#
.SYNOPSIS
Prepare a fresh Windows checkout for DDMP development.

.DESCRIPTION
Creates a repository-local Python virtual environment, installs development
dependencies, creates a machine-local .env when needed, applies checked-in
migrations, and runs Django's system check. It never copies development or
production data from another machine.

Functional scope: SYS-CONFIG-001.
#>

[CmdletBinding()]
param(
    [string] $PythonCommand = "py",
    [string] $PythonVersion = "3.13",
    [switch] $SkipDependencyInstall,
    [switch] $SkipMigrations
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env"
$envExample = Join-Path $root ".env.example"
$requirements = Join-Path $root "requirements\dev.txt"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string] $FilePath,
        [Parameter(Mandatory = $true)][string[]] $Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

Set-Location $root

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating Python $PythonVersion virtual environment..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $PythonCommand -Arguments @("-$PythonVersion", "-m", "venv", ".venv")
}

if (-not $SkipDependencyInstall) {
    Write-Host "Installing development dependencies..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $venvPython -Arguments @("-m", "pip", "install", "-r", $requirements)
}

if (-not (Test-Path -LiteralPath $envFile)) {
    if (-not (Test-Path -LiteralPath $envExample)) {
        throw "Environment template not found: $envExample"
    }

    Copy-Item -LiteralPath $envExample -Destination $envFile

    $randomBytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($randomBytes)
    }
    finally {
        $random.Dispose()
    }
    $secret = ([BitConverter]::ToString($randomBytes)).Replace("-", "").ToLowerInvariant()
    $content = Get-Content -LiteralPath $envFile -Raw -Encoding UTF8
    $content = $content.Replace(
        "replace-with-a-random-development-secret",
        "dev-$secret"
    )
    Set-Content -LiteralPath $envFile -Value $content -Encoding UTF8
    Write-Host "Created a machine-local .env with a random development secret." -ForegroundColor Green
    Write-Warning "Review .env for this computer's LAN IP and PostgreSQL connection before shared-device testing."
}
else {
    Write-Host "Keeping the existing machine-local .env." -ForegroundColor Yellow
}

if (-not $SkipMigrations) {
    Write-Host "Applying checked-in migrations..." -ForegroundColor Cyan
    Invoke-Checked -FilePath $venvPython -Arguments @("manage.py", "migrate", "--noinput")
}

Write-Host "Running Django system check..." -ForegroundColor Cyan
Invoke-Checked -FilePath $venvPython -Arguments @("manage.py", "check")

Write-Host "`nDDMP development checkout is ready: $root" -ForegroundColor Green
Write-Host "Run .\scripts\check.ps1 before committing changes."
Write-Host "Run .\scripts\run-dev.ps1 to start the local server."
