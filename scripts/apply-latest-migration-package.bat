@echo off
setlocal EnableExtensions

rem Apply the newest DDMP code-only zip from the server incoming directory.
rem Functional scope: deployment support for FR-OPS-01 / FR-OPS-02.

set "RUNTIME_ROOT=D:\DDMP-RUNTIME"
set "INCOMING_DIR=%RUNTIME_ROOT%\incoming"
set "APPLY_SCRIPT=%INCOMING_DIR%\apply-migration-package.ps1"
set "PUBLIC_HOST=bzb889.originseed.com.cn"
set "SERVICE_NAME=DDMP-App"

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo [DDMP] Need Administrator permission. Requesting elevation...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

if not exist "%INCOMING_DIR%\" (
    echo [DDMP] Incoming directory not found: %INCOMING_DIR%
    echo [DDMP] Please create it and copy ddmp-code-*.zip there.
    pause
    exit /b 1
)

if not exist "%APPLY_SCRIPT%" (
    echo [DDMP] Apply script not found: %APPLY_SCRIPT%
    echo [DDMP] Please copy apply-migration-package.ps1 to %INCOMING_DIR%
    pause
    exit /b 1
)

set "LATEST_ZIP="
for /f "usebackq delims=" %%F in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%INCOMING_DIR%' -Filter 'ddmp-code-*.zip' -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName"`) do (
    set "LATEST_ZIP=%%F"
)

if not defined LATEST_ZIP (
    echo [DDMP] No code-only zip found in %INCOMING_DIR%
    echo [DDMP] Expected file name like: ddmp-code-YYYYMMDD-HHMMSS.zip
    pause
    exit /b 1
)

echo [DDMP] Runtime root : %RUNTIME_ROOT%
echo [DDMP] Public host  : %PUBLIC_HOST%
echo [DDMP] Service name : %SERVICE_NAME%
echo [DDMP] Latest zip   : %LATEST_ZIP%
echo.
echo [DDMP] This will deploy source code, preserve production data/media, collect static files, and restart %SERVICE_NAME%.
echo [DDMP] Press Ctrl+C now if this is not expected.
pause

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%APPLY_SCRIPT%" ^
  -PackagePath "%LATEST_ZIP%" ^
  -RuntimeRoot "%RUNTIME_ROOT%" ^
  -PublicHost "%PUBLIC_HOST%" ^
  -ServiceName "%SERVICE_NAME%"

set "EXIT_CODE=%errorlevel%"
echo.
if "%EXIT_CODE%"=="0" (
    echo [DDMP] Deployment finished successfully.
) else (
    echo [DDMP] Deployment failed. Exit code: %EXIT_CODE%
)
pause
exit /b %EXIT_CODE%
