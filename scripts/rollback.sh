#!/bin/bash
# rollback.sh — vuelve a una imagen anterior de Django (sin rebuild)
# Uso: bash scripts/rollback.sh [tag]     (por defecto: el tag previo guardado en .deploy/previous)
# OJO: no revierte migraciones. Si el deploy migró la DB, restaura también el backup (make restore).

set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh
load_env
build_profiles

TAG=${1:-$(cat .deploy/previous 2>/dev/null || true)}
if [ -z "$TAG" ]; then
    echo "Error: no hay tag previo registrado. Tags disponibles:" >&2
    docker images "${PROJECT_NAME}_app" --format '  {{.Tag}}  ({{.CreatedSince}})' >&2
    exit 1
fi
docker image inspect "${PROJECT_NAME}_app:${TAG}" >/dev/null 2>&1 \
    || { echo "Error: no existe la imagen ${PROJECT_NAME}_app:${TAG}" >&2; exit 1; }

echo "▶ Rollback de Django a ${TAG}..."
IMAGE_TAG="$TAG" dc up -d --no-build --no-deps django
if wait_healthy 120; then
    echo "✓ Rollback completado (${TAG})."
else
    echo "✗ Django no quedó healthy tras el rollback." >&2
    docker logs --tail 50 "${APP_CONTAINER}" >&2 || true
    exit 1
fi
