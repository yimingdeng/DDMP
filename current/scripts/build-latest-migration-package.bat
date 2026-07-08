@echo off
setlocal EnableExtensions

rem Build a fresh DDMP code-only deployment package on the development workstation.
rem Functional scope: deployment support for FR-OPS-01 / FR-OPS-02.

set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

set "BUILD_SCRIPT=%REPO_ROOT%\scripts\build-migration-package.ps1"
set "RELEASE_DIR=%REPO_ROOT%\.local\release"

if not exist "%BUILD_SCRIPT%" (
    echo [DDMP] Build script not found: %BUILD_SCRIPT%
    pause
    exit /b 1
)

echo [DDMP] Repository : %REPO_ROOT%
echo [DDMP] Output dir : %RELEASE_DIR%
echo.
echo [DDMP] This creates a source-code-only zip package.
echo [DDMP] Development database data and uploaded media are NOT included.
echo [DDMP] Press Ctrl+C now if this is not expected.
pause

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BUILD_SCRIPT%"

set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [DDMP] Package build failed. Exit code: %EXIT_CODE%
    pause
    exit /b %EXIT_CODE%
)

echo.
echo [DDMP] Copying server helper scripts to release directory...
if not exist "%RELEASE_DIR%\" mkdir "%RELEASE_DIR%"
copy /Y "%REPO_ROOT%\scripts\apply-migration-package.ps1" "%RELEASE_DIR%\apply-migration-package.ps1" >nul
copy /Y "%REPO_ROOT%\scripts\apply-latest-migration-package.bat" "%RELEASE_DIR%\apply-latest-migration-package.bat" >nul

echo.
echo [DDMP] Latest generated code packages:
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%RELEASE_DIR%' -Filter 'ddmp-code-*.zip' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 3 FullName,Length,LastWriteTime | Format-Table -AutoSize"

echo.
echo [DDMP] Copy these files to D:\DDMP-RUNTIME\incoming on the server:
echo [DDMP]   1. the newest ddmp-code-*.zip above
echo [DDMP]   2. %RELEASE_DIR%\apply-migration-package.ps1
echo [DDMP]   3. %RELEASE_DIR%\apply-latest-migration-package.bat
pause
exit /b 0
