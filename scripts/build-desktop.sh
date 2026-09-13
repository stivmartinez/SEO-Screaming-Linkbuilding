#!/usr/bin/env bash
# Build a distributable desktop app (macOS .app / Windows folder via PyInstaller).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d backend/.venv ]]; then
  python3 -m venv backend/.venv
fi
# shellcheck disable=SC1091
source backend/.venv/bin/activate

pip install -q -r backend/requirements.txt -r desktop/requirements.txt

echo "Building UI…"
(cd frontend && npm install && npm run build)
rm -rf backend/static
mkdir -p backend/static
cp -R frontend/dist/. backend/static/

echo "Packaging with PyInstaller…"
rm -rf build dist
pyinstaller --noconfirm desktop/seo-crawler.spec

echo
echo "Done."
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "macOS app: dist/SEO Screaming Link Building.app"
else
  echo "App folder: dist/SEOScreamingLinkBuilding/"
fi
echo "Double-click to open. Crawl data is stored in the OS app-data directory."
