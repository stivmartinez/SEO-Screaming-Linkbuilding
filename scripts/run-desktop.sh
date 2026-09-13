#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON=python3
command -v python3 >/dev/null 2>&1 || PYTHON=python

if [[ ! -d backend/.venv ]]; then
  "$PYTHON" -m venv backend/.venv
fi

if [[ -f backend/.venv/Scripts/activate ]]; then
  # shellcheck disable=SC1091
  source backend/.venv/Scripts/activate
elif [[ -f backend/.venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source backend/.venv/bin/activate
else
  echo "Could not find venv activate script under backend/.venv" >&2
  exit 1
fi

pip install -q -r backend/requirements.txt -r desktop/requirements.txt

if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install)
fi

if [[ ! -f backend/static/index.html ]]; then
  (cd frontend && npm run build)
  rm -rf backend/static
  mkdir -p backend/static
  cp -R frontend/dist/. backend/static/
fi

echo "Launching desktop app…"
python -m desktop "$@"
