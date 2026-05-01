# [1] Ensure Python -> [2] pip + requirements -> [3] polymarket_analyzer.qt_main
# If execution policy blocks: powershell -ExecutionPolicy Bypass -File .\install-and-run.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Refresh-PathEnv {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

function Test-PythonAvailable {
    return [bool](Get-Command py -ErrorAction SilentlyContinue) -or
        [bool](Get-Command python -ErrorAction SilentlyContinue)
}

if (-not (Test-PythonAvailable)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host '[1/3] Python not found. Installing Python (3.11) via winget...'
        winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
        Refresh-PathEnv
    }
    if (-not (Test-PythonAvailable)) {
        Write-Error 'Python 3.10+ not found. Install from https://www.python.org/ (check Add to PATH) or install winget, then retry.'
        exit 1
    }
} else {
    Write-Host '[1/3] Python already available.'
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Host '[2/3] Installing / updating pip and requirements (py -3)...'
    & py -3 -m pip install -q --upgrade --no-cache-dir pip
    & py -3 -m pip install -q --no-cache-dir -r requirements.txt
    Write-Host '[3/3] Starting Polymarket Analyzer GUI...'
    & py -3 -m polymarket_analyzer.qt_main @args
} else {
    Write-Host '[2/3] Installing / updating pip and requirements (python)...'
    python -m pip install -q --upgrade --no-cache-dir pip
    python -m pip install -q --no-cache-dir -r requirements.txt
    Write-Host '[3/3] Starting Polymarket Analyzer GUI...'
    python -m polymarket_analyzer.qt_main @args
}

exit $LASTEXITCODE
