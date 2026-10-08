#!/usr/bin/env bash
# Démarrage Replit : dépendances si besoin, build du frontend, une seule API.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  rm -rf .venv
  if ! python3 -m venv .venv; then
    rm -rf .venv
    python3 -m pip install --user -r backend/requirements.txt
  fi
fi
if [ -x .venv/bin/python ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -r backend/requirements.txt
fi

cd frontend
if [ ! -d node_modules ]; then
  if [ -f package-lock.json ]; then
    npm ci
  else
    npm install
  fi
fi
npm run build
cd ..

if [ -n "${PORT:-}" ]; then
  exec uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"
else
  exec uvicorn backend.app.main:app --host 127.0.0.1 --port 8741
fi
