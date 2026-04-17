#!/usr/bin/env bash
# Install requirements with the default interpreter, then launch the GUI (macOS / Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

choose_python() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' python3
  elif command -v python >/dev/null 2>&1; then
    printf '%s\n' python
  else
    echo "ERROR: Python 3.10+ not found. Install python3/python and retry." >&2
    exit 1
  fi
}

PY="$(choose_python)"

echo '[1/2] Installing / updating dependencies...'
# --no-cache-dir avoids pip "Cache entry deserialization failed" with a stale user cache
"${PY}" -m pip install -q --upgrade --no-cache-dir pip
"${PY}" -m pip install -q --no-cache-dir -r requirements.txt
echo '[2/2] Starting Polymarket Analyzer GUI...'
exec "${PY}" -m polymarket_analyzer.qt_main "$@"
