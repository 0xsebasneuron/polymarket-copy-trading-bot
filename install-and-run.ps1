# Install requirements with the default interpreter, then launch the GUI (Windows PowerShell).
# If execution policy blocks scripts: powershell -ExecutionPolicy Bypass -File .\install-and-run.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Host '[1/2] Installing / updating dependencies (py -3)...'
    & py -3 -m pip install -q --upgrade --no-cache-dir pip
    & py -3 -m pip install -q --no-cache-dir -r requirements.txt
    Write-Host '[2/2] Starting Polymarket Analyzer GUI...'
    & py -3 -m polymarket_analyzer.qt_main @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host '[1/2] Installing / updating dependencies (python)...'
    python -m pip install -q --upgrade --no-cache-dir pip
    python -m pip install -q --no-cache-dir -r requirements.txt
    Write-Host '[2/2] Starting Polymarket Analyzer GUI...'
    python -m polymarket_analyzer.qt_main @args
} else {
    Write-Error 'Python 3.10+ not found. Install from https://www.python.org/ and retry.'
    exit 1
}

exit $LASTEXITCODE
