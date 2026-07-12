<#
.SYNOPSIS
Build a code-only DDMP deployment package from the development workstation.

.DESCRIPTION
Creates a deployment package containing application source code only.
It never exports the development database and never copies uploaded media.

The package is written under .local\release so it is not committed by git.
Use the companion scripts\apply-migration-package.ps1 on the Windows server.

Functional scope: deployment support for FR-OPS-01 / FR-OPS-02.
#>

[CmdletBinding()]
param(
    [string]$OutputRoot = ".local\release",

    [switch]$SkipZip
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$ExtraArguments = @()
    )

    $arguments = @($Source, $Destination, "/MIR", "/R:2", "/W:2", "/NFL", "/NDL", "/NP") + $ExtraArguments
    & robocopy.exe @arguments | Out-Host
    $code = $LASTEXITCODE
    if ($code -gt 7) {
        throw "robocopy failed with exit code ${code}: $Source -> $Destination"
    }
}

$repoRoot = Resolve-RepoRoot
$managePy = Join-Path $repoRoot "manage.py"
if (-not (Test-Path -LiteralPath $managePy)) {
    throw "manage.py not found: $managePy"
}

$requirementsFile = Join-Path $repoRoot "requirements\prod.txt"
if (-not (Test-Path -LiteralPath $requirementsFile)) {
    throw "Production requirements file not found: $requirementsFile"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputRootPath = Join-Path $repoRoot $OutputRoot
$packageName = "ddmp-code-$timestamp"
$packageDir = Join-Path $outputRootPath $packageName
$codeDir = Join-Path $packageDir "code"

New-Item -ItemType Directory -Path $codeDir -Force | Out-Null

Write-Host "Copying application source code only..."
$excludeDirs = @(
    "/XD",
    ".git",
    ".agents",
    ".codex",
    ".venv",
    ".local",
    ".tmp",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "pytest-of-*",
    "htmlcov"
)
$excludeFiles = @(
    "/XF",
    ".env",
    ".env.*",
    "*.sqlite3",
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.rar",
    "*.zip"
)
Invoke-RobocopyMirror -Source $repoRoot -Destination $codeDir -ExtraArguments ($excludeDirs + $excludeFiles)

$manifest = [ordered]@{
    package_name = $packageName
    package_type = "code_only"
    generated_at = (Get-Date).ToString("s")
    includes_database = $false
    includes_media = $false
    deployment_actions = @(
        "replace_application_code",
        "install_dependencies",
        "apply_schema_migrations",
        "collect_static",
        "restart_service",
        "health_check"
    )
    safety = "This package contains no database fixture and no uploaded media. Production business data and media must be preserved."
}
$manifestPath = Join-Path $packageDir "manifest.json"
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$applyScriptSource = Join-Path $repoRoot "scripts\apply-migration-package.ps1"
$applyScriptCopy = Join-Path $outputRootPath "apply-migration-package.ps1"
Copy-Item -LiteralPath $applyScriptSource -Destination $applyScriptCopy -Force
$applyLatestBatSource = Join-Path $repoRoot "scripts\apply-latest-migration-package.bat"
$applyLatestBatCopy = Join-Path $outputRootPath "apply-latest-migration-package.bat"
Copy-Item -LiteralPath $applyLatestBatSource -Destination $applyLatestBatCopy -Force

if (-not $SkipZip) {
    $zipPath = Join-Path $outputRootPath "$packageName.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Write-Host "Creating code-only zip package: $zipPath"
    Compress-Archive -Path (Join-Path $packageDir "*") -DestinationPath $zipPath -Force
}

Write-Host ""
Write-Host "Code-only deployment package ready:"
Write-Host "  Folder: $packageDir"
Write-Host "  Server apply script: $applyScriptCopy"
Write-Host "  Server latest-package bat: $applyLatestBatCopy"
if (-not $SkipZip) {
    Write-Host "  Zip:    $zipPath"
}
Write-Host ""
Write-Host "No development database data or uploaded media was included."
Write-Host "Copy the zip and both server helper scripts to D:\DDMP-RUNTIME\incoming."
