#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d backend/.venv ]]; then
  python3 -m venv backend/.venv
fi
# shellcheck disable=SC1091
source backend/.venv/bin/activate

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
