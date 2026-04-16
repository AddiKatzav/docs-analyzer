#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"

cd "$BACKEND_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv .venv
fi

source "$VENV_DIR/bin/activate"
pip install -r requirements.txt

echo "Starting full localhost MVP on http://localhost:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
