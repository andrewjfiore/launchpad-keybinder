#!/usr/bin/env bash
# Launchpad Mapper - Start Script (macOS/Linux)

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

echo "[1/4] Checking Python environment..."
PYTHON=""

# Prefer python3 if available, otherwise fall back to python (if it is Python 3)
if command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  if python -c 'import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)' >/dev/null 2>&1; then
    PYTHON="python"
  fi
fi

if [[ -z "${PYTHON}" ]]; then
  echo "ERROR: Python 3 is required but was not found."
  echo "Install Python 3 and try again."
  exit 1
fi

echo "Using: ${PYTHON} ($(${PYTHON} --version 2>&1))"

echo "[2/4] Ensuring virtual environment..."
if [[ ! -x "venv/bin/python" ]]; then
  echo "Creating virtual environment..."
  "${PYTHON}" -m venv "venv"
fi

# shellcheck disable=SC1091
source "venv/bin/activate"

echo "[3/4] Checking dependencies..."
if [[ ! -f "requirements.txt" ]]; then
  echo "ERROR: requirements.txt not found in $(pwd)"
  exit 1
fi

python -m pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
python -m pip install -r "requirements.txt"

echo
echo "==================================================="
echo "  LAUNCHPAD MAPPER STARTED"
echo "  Open: http://localhost:5000"
echo "==================================================="
echo

echo "[4/4] Starting server..."
if [[ ! -f "server.py" ]]; then
  echo "ERROR: server.py not found in $(pwd)"
  exit 1
fi

exec python "server.py"
