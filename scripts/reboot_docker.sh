#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

echo "[1/4] Stopping current stack (if running)..."
docker compose down --remove-orphans -v || true
docker-compose down --remove-orphans -v || true

echo "[2/4] Removing stale project containers..."
docker ps -a --format '{{.ID}} {{.Names}}' | awk '/docs-analyzer/{print $1}' | xargs -r docker rm -f || true

echo "[3/4] Removing stale project networks/volumes..."
docker network ls --format '{{.ID}} {{.Name}}' | awk '/docs-analyzer/{print $1}' | xargs -r docker network rm || true
docker volume ls --format '{{.Name}}' | awk '/docs-analyzer/{print $1}' | xargs -r docker volume rm || true

echo "[4/4] Rebuilding and starting with docker compose..."
docker compose up --build
