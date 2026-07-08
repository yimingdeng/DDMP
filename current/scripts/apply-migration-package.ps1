<#
.SYNOPSIS
Apply a code-only DDMP deployment package on the Windows runtime server.

.DESCRIPTION
Deploys application source code while preserving the production database and
uploaded media. The script installs dependencies, applies checked-in schema
migrations, collects static files, restarts the service and checks health.

Packages containing development fixtures or media are rejected.
Run from an elevated PowerShell session on the server.
Functional scope: deployment support for FR-OPS-01 / FR-OPS-02.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath,

    [string]$RuntimeRoot = "D:\DDMP-RUNTIME",

    [string]$Python = "",

    [string]$EnvFile = "",

    [string]$ServiceName = "DDMP-App",

    [string]$PublicHost = "bzb889.originseed.com.cn",

    [switch]$SkipPipInstall,

    [switch]$SkipMigrations,

    [switch]$SkipServiceRestart,

    [switch]$SkipHealthCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory
    )

    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [string[]]$ExtraArguments = @()
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $arguments = @($Source, $Destination, "/MIR", "/R:2", "/W:2", "/NFL", "/NDL", "/NP") + $ExtraArguments
    & robocopy.exe @arguments | Out-Host
    $code = $LASTEXITCODE
    if ($code -gt 7) {
        throw "robocopy failed with exit code ${code}: $Source -> $Destination"
    }
}

function Resolve-PackageRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = Resolve-Path -LiteralPath $Path
    $item = Get-Item -LiteralPath $resolved.Path
    if ($item.PSIsContainer) {
        $candidate = $item.FullName
    }
    else {
        $incomingRoot = Join-Path $RuntimeRoot "incoming"
        $extractDir = Join-Path $incomingRoot ("ddmp-code-package-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
        New-Item -ItemType Directory -Path $extractDir -Force | Out-Null
        Expand-Archive -LiteralPath $item.FullName -DestinationPath $extractDir -Force
        $candidate = $extractDir
    }

    if (
        (Test-Path -LiteralPath (Join-Path $candidate "code")) -and
        (Test-Path -LiteralPath (Join-Path $candidate "manifest.json"))
    ) {
        return $candidate
    }

    $children = Get-ChildItem -LiteralPath $candidate -Directory
    foreach ($child in $children) {
        if (
            (Test-Path -LiteralPath (Join-Path $child.FullName "code")) -and
            (Test-Path -LiteralPath (Join-Path $child.FullName "manifest.json"))
        ) {
            return $child.FullName
        }
    }

    throw "Package root not found. Expected code and manifest.json: ${Path}"
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = Join-Path $RuntimeRoot "venv\Scripts\python.exe"
}
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $RuntimeRoot "config\.env"
}

$runtimeRootPath = (Resolve-Path -LiteralPath $RuntimeRoot).Path
$pythonPath = (Resolve-Path -LiteralPath $Python).Path
$envFilePath = (Resolve-Path -LiteralPath $EnvFile).Path
$packageRoot = Resolve-PackageRoot -Path $PackagePath
$codeSource = Join-Path $packageRoot "code"
$manifestPath = Join-Path $packageRoot "manifest.json"
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

if (
    $manifest.PSObject.Properties.Name -notcontains "package_type" -or
    $manifest.package_type -ne "code_only"
) {
    throw "Unsafe or obsolete package rejected. Expected package_type=code_only: $manifestPath"
}
if (
    ($manifest.PSObject.Properties.Name -contains "includes_database" -and $manifest.includes_database) -or
    ($manifest.PSObject.Properties.Name -contains "includes_media" -and $manifest.includes_media) -or
    (Test-Path -LiteralPath (Join-Path $packageRoot "data")) -or
    (Test-Path -LiteralPath (Join-Path $packageRoot "media"))
) {
    throw "Package contains database data or media and will not be deployed: $packageRoot"
}

if (-not $SkipServiceRestart -and -not (Test-IsAdministrator)) {
    throw "This script needs Administrator PowerShell to stop/start Windows service '$ServiceName'. Please reopen PowerShell as Administrator, then rerun the command. If you have already stopped the service manually, rerun with -SkipServiceRestart."
}

$appCurrent = Join-Path $runtimeRootPath "app\current"
$staticTarget = Join-Path $runtimeRootPath "data\static"
$backupRoot = Join-Path $runtimeRootPath "backups"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

New-Item -ItemType Directory -Path $appCurrent, $staticTarget, $backupRoot -Force | Out-Null

if (-not $SkipServiceRestart) {
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $service -and $service.Status -ne "Stopped") {
        Write-Host "Stopping service: $ServiceName"
        Stop-Service -Name $ServiceName -Force
        $service.WaitForStatus("Stopped", "00:00:30")
    }
}

$env:DJANGO_ENV_FILE = $envFilePath

if (Test-Path -LiteralPath (Join-Path $appCurrent "manage.py")) {
    $codeBackup = Join-Path $backupRoot "app\before-$timestamp"
    Write-Host "Backing up current code to $codeBackup"
    Invoke-RobocopyMirror -Source $appCurrent -Destination $codeBackup
}

Write-Host "Deploying code to $appCurrent"
Invoke-RobocopyMirror -Source $codeSource -Destination $appCurrent `
    -ExtraArguments @("/XD", ".local", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache")

if (-not $SkipPipInstall) {
    $requirementsFile = Join-Path $appCurrent "requirements\prod.txt"
    if (-not (Test-Path -LiteralPath $requirementsFile)) {
        throw "Production requirements file not found after code deployment: $requirementsFile"
    }
    Write-Host "Installing or updating Python dependencies..."
    Invoke-Checked -FilePath $pythonPath `
        -Arguments @("-m", "pip", "install", "-r", $requirementsFile) `
        -WorkingDirectory $appCurrent
}

if (-not $SkipMigrations) {
    Write-Host "Applying checked-in schema migrations without replacing production records..."
    Invoke-Checked -FilePath $pythonPath `
        -Arguments @("manage.py", "migrate", "--noinput") `
        -WorkingDirectory $appCurrent
}
else {
    Write-Host "Skipped database schema migrations."
}

Write-Host "Collecting static files..."
Invoke-Checked -FilePath $pythonPath `
    -Arguments @("manage.py", "collectstatic", "--clear", "--noinput") `
    -WorkingDirectory $appCurrent

Write-Host "Running production checks..."
Invoke-Checked -FilePath $pythonPath `
    -Arguments @("manage.py", "check", "--deploy") `
    -WorkingDirectory $appCurrent

if (-not $SkipServiceRestart) {
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -ne $service) {
        Write-Host "Starting service: $ServiceName"
        Start-Service -Name $ServiceName
        $service.WaitForStatus("Running", "00:00:30")
    }
    else {
        Write-Host "Service not found, please start the Django app manually: $ServiceName"
    }
}

if (-not $SkipHealthCheck) {
    Write-Host "Health check through local Waitress with production Host header..."
    # Windows Server may bundle an older curl without --fail-with-body.
    & curl.exe -f -i `
        -H "Host: $PublicHost" `
        -H "X-Forwarded-Proto: https" `
        "http://127.0.0.1:8000/health/" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Health check failed with curl exit code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "Code-only deployment finished."
Write-Host "Package: $packageRoot"
Write-Host "Code backup: $backupRoot\app\before-$timestamp"
Write-Host "Production database records and uploaded media were preserved."
