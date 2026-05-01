@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

call :maybe_install_python_windows
if errorlevel 1 exit /b 1

REM Prefer launcher (py -3), then plain python after PATH/bootstrap.
where py >nul 2>&1
if not errorlevel 1 goto run_launcher

where python >nul 2>&1
if not errorlevel 1 goto run_direct

echo ERROR: Python 3 still not available after bootstrap. Install manually from https://www.python.org/ ^(check "Add python.exe to PATH"^).
pause
exit /b 1

:run_launcher
echo [2/3] Installing / updating pip and requirements...
py -3 -m pip install -q --upgrade --no-cache-dir pip
py -3 -m pip install -q --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)
echo [3/3] Starting Polymarket Analyzer GUI...
py -3 -m polymarket_analyzer.qt_main %*
set "ERR=!errorlevel!"
if not "!ERR!"=="0" (
    echo GUI exited with code !ERR!
    pause
)
exit /b !ERR!

:run_direct
echo [2/3] Installing / updating pip and requirements...
python -m pip install -q --upgrade --no-cache-dir pip
python -m pip install -q --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)
echo [3/3] Starting Polymarket Analyzer GUI...
python -m polymarket_analyzer.qt_main %*
set "ERR=!errorlevel!"
if not "!ERR!"=="0" (
    echo GUI exited with code !ERR!
    pause
)
exit /b !ERR!

:maybe_install_python_windows
where py >nul 2>&1
if not errorlevel 1 exit /b 0
where python >nul 2>&1
if not errorlevel 1 exit /b 0

where winget >nul 2>&1
if errorlevel 1 (
    echo Python not found and winget is unavailable.
    echo Install Python 3.10+ from https://www.python.org/ then re-run this script.
    pause
    exit /b 1
)

echo [1/3] Python not found. Installing Python ^(3.11^) via winget...
winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo winget install failed. Install Python manually and retry.
    pause
    exit /b 1
)

REM Merge Machine + User PATH so this cmd.exe session sees freshly installed Python.
for /f "delims=" %%P in ('powershell -NoProfile -Command "$m=[Environment]::GetEnvironmentVariable('Path','Machine'); $u=[Environment]::GetEnvironmentVariable('Path','User'); Write-Output ($m.TrimEnd(';')+';'+$u.TrimEnd(';'))"') do set "PATH=%%P"
exit /b 0
