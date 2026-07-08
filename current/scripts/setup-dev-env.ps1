[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Add-PreferredUserPath {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $PreferredPaths
    )

    foreach ($path in $PreferredPaths) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Required path not found: $path"
        }
    }

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($null -eq $userPath) {
        $userPath = ''
    }

    $existing = $userPath.Split(';', [StringSplitOptions]::RemoveEmptyEntries)
    $remaining = @(
        $existing | Where-Object {
            $candidate = $_.Trim().TrimEnd('\')
            -not ($PreferredPaths | Where-Object {
                $_.TrimEnd('\') -ieq $candidate
            })
        }
    )

    $ordered = @($PreferredPaths) + @($remaining)
    $newPath = ($ordered |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ } |
        Select-Object -Unique) -join ';'

    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    return $newPath
}

$pythonHome = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313'
$pythonScripts = Join-Path $pythonHome 'Scripts'
$pythonLauncher = Join-Path $env:LOCALAPPDATA 'Programs\Python\Launcher'
$vscodeBin = Join-Path $env:LOCALAPPDATA 'Programs\Microsoft VS Code\bin'

$preferred = @(
    $pythonHome,
    $pythonScripts,
    $pythonLauncher,
    $vscodeBin
)

$newUserPath = Add-PreferredUserPath -PreferredPaths $preferred

[Environment]::SetEnvironmentVariable('DDMP_HOME', $repoRoot, 'User')
[Environment]::SetEnvironmentVariable('PYTHONUTF8', '1', 'User')
[Environment]::SetEnvironmentVariable('PIP_DISABLE_PIP_VERSION_CHECK', '1', 'User')

# Refresh this PowerShell process as well as the persistent user variables.
$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$env:Path = $machinePath + ';' + $newUserPath
$env:DDMP_HOME = $repoRoot
$env:PYTHONUTF8 = '1'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'

Write-Host 'Development environment variables configured for:' ([Environment]::UserName)
Write-Host 'DDMP_HOME=' $env:DDMP_HOME
Write-Host 'PYTHONUTF8=' $env:PYTHONUTF8
Write-Host 'PIP_DISABLE_PIP_VERSION_CHECK=' $env:PIP_DISABLE_PIP_VERSION_CHECK
Write-Host ''
Write-Host 'User PATH:'
Write-Host $newUserPath
Write-Host ''
Write-Host 'Close and reopen PowerShell, VS Code, and Codex before normal use.'

