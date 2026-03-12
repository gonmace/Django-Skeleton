#!/bin/bash
# Exporta todos los workflows de n8n dev al repositorio.
# Uso: bash docker/n8n-export.sh

set -e

PROJECT_NAME=${PROJECT_NAME:-dev}
EXPORT_DIR="./n8n/workflows"

mkdir -p "$EXPORT_DIR"

echo "▶ Exportando workflows de n8n..."
docker compose -f docker-compose.dev.yml exec n8n \
    n8n export:workflow --all --output=/home/node/.n8n/exports/

docker compose -f docker-compose.dev.yml cp \
    n8n:/home/node/.n8n/exports/. "$EXPORT_DIR/"

echo "✓ Workflows exportados en $EXPORT_DIR/"
echo "  Ahora haz git add n8n/ && git commit && git push"
