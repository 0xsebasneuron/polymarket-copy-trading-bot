@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM Prefer Windows Python Launcher when present; otherwise use python on PATH.

where py >nul 2>&1
if not errorlevel 1 goto run_py

where python >nul 2>&1
if not errorlevel 1 goto run_python

echo ERROR: Python 3.10+ not found. Install from https://www.python.org/ ^(enable "Add python.exe to PATH"^).
pause
exit /b 1

:run_py
echo [1/2] Installing / updating dependencies...
py -3 -m pip install -q --upgrade --no-cache-dir pip
py -3 -m pip install -q --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)
echo [2/2] Starting Polymarket Analyzer GUI...
py -3 -m polymarket_analyzer.qt_main %*
set "ERR=!errorlevel!"
if not "!ERR!"=="0" (
    echo GUI exited with code !ERR!
    pause
)
exit /b !ERR!

:run_python
echo [1/2] Installing / updating dependencies...
python -m pip install -q --upgrade --no-cache-dir pip
python -m pip install -q --no-cache-dir -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)
echo [2/2] Starting Polymarket Analyzer GUI...
python -m polymarket_analyzer.qt_main %*
set "ERR=!errorlevel!"
if not "!ERR!"=="0" (
    echo GUI exited with code !ERR!
    pause
)
exit /b !ERR!
