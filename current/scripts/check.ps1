[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found."
}

function Invoke-Check {
    param(
        [string] $Name,
        [string[]] $Arguments
    )

    Write-Host "`n== $Name ==" -ForegroundColor Cyan
    & $python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Set-Location $root
Invoke-Check "Ruff lint" @("-m", "ruff", "check", ".")
Invoke-Check "Ruff format" @("-m", "ruff", "format", "--check", ".")
Invoke-Check "Tests" @("-m", "pytest")
Invoke-Check "Django system check" @("manage.py", "check")
Invoke-Check "Migration check" @("manage.py", "makemigrations", "--check", "--dry-run")

Write-Host "`nAll checks passed." -ForegroundColor Green

