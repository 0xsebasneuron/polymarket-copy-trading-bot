#!/usr/bin/env bash
# [1] Ensure Python (+ pip) -> [2] requirements -> [3] polymarket_analyzer.qt_main
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

pick_python_command() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "$(command -v python3)"
    return 0
  fi
  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "$(command -v python)"
    return 0
  fi
  return 1
}

bootstrap_python_unix() {
  if pick_python_command >/dev/null; then
    return 0
  fi

  if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    echo '[1/3] Python not found. Installing Python via Homebrew...' >&2
    brew install python@3.11 || brew install python || true
    hash -r 2>/dev/null || true
  elif command -v apt-get >/dev/null 2>&1; then
    echo '[1/3] Python not found. Installing python3 via apt-get (sudo)...' >&2
    sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-pip python3-venv
    hash -r 2>/dev/null || true
  fi

  if pick_python_command >/dev/null; then
    return 0
  fi
  return 1
}

if ! bootstrap_python_unix; then
  echo 'ERROR: Python 3.10+ not found. Install python3 + pip (e.g. https://python.org/downloads/) and retry.' >&2
  exit 1
fi

PY="$(pick_python_command)"
echo "[1/3] Using ${PY}"

if ! "${PY}" -m pip --version >/dev/null 2>&1; then
  echo '[1/3] pip missing; trying ensurepip...' >&2
  "${PY}" -m ensurepip --upgrade 2>/dev/null || true
fi

echo '[2/3] Installing / updating pip and requirements...'
"${PY}" -m pip install -q --upgrade --no-cache-dir pip
"${PY}" -m pip install -q --no-cache-dir -r requirements.txt
echo '[3/3] Starting Polymarket Analyzer GUI...'
exec "${PY}" -m polymarket_analyzer.qt_main "$@"
