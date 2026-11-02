#!/bin/bash
# deploy.sh — despliega el proyecto en el VPS con downtime mínimo
#
# Uso:   bash deploy.sh
# Opciones por entorno:
#   BACKUP=auto|always|never   auto (defecto): backup solo si hay migraciones pendientes
#   SKIP_PULL=1                no hace git pull (útil para probar en local)
#
# Flujo: pull → build (con la app aún en marcha) → backup condicional →
#        up -d (recrea solo lo que cambió) → espera healthy → rollback automático si falla.

set -euo pipefail
cd "$(dirname "$0")"
source scripts/lib.sh

BACKUP=${BACKUP:-auto}

load_env
DOMAIN=${DOMAIN:?La variable DOMAIN no está definida en .env}
: "${SECRET_KEY:?SECRET_KEY no está definida en .env}"
: "${POSTGRES_DB:?POSTGRES_DB no está definida en .env}"
: "${POSTGRES_USER:?POSTGRES_USER no está definida en .env}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD no está definida en .env}"
if [ -n "${N8N_DOMAIN}" ]; then
    : "${N8N_ENCRYPTION_KEY:?N8N_ENCRYPTION_KEY es obligatoria si N8N_DOMAIN está definido}"
fi

# ── 1. Actualizar código ───────────────────────────────────────────────────────
# Tras el pull se re-ejecuta el script para no seguir con una versión vieja de sí mismo.
if [ "${SKIP_PULL:-}" != "1" ] && [ "${1:-}" != "--pulled" ]; then
    echo "▶ Actualizando código..."
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    git pull --ff-only origin "${BRANCH}"
    exec bash "$0" --pulled
fi

echo "━━━ Desplegando: ${PROJECT_NAME} (${DOMAIN}) ━━━"
GIT_SHA=$(git rev-parse --short HEAD)
echo "  Versión: ${GIT_SHA}"

build_profiles
if [ "${POSTGRES_MODE}" = "container" ]; then
    echo "  PostgreSQL: contenedor Docker"
else
    echo "  PostgreSQL: servidor host (${POSTGRES_HOST:-host.docker.internal})"
    echo "  Asegúrate de que pg_hba.conf permita conexiones desde Docker (172.16.0.0/12)"
fi
if [ -n "${N8N_DOMAIN}" ]; then
    echo "  n8n: habilitado (${N8N_DOMAIN})"
    [ "${N8N_MCP_ENABLED}" = "true" ] && echo "  n8n-MCP: habilitado (puerto ${N8N_MCP_PORT:-8002})"
else
    echo "  n8n: deshabilitado (N8N_DOMAIN no definido)"
fi
echo ""

# ── 2. Directorios y permisos ──────────────────────────────────────────────────
# Django corre como UID 1000 dentro del contenedor; n8n también (usuario node).
ensure_owner() {
    mkdir -p "$1"
    if [ "$(stat -c %u "$1")" != "1000" ]; then
        sudo chown -R 1000:1000 "$1"
    fi
}
ensure_owner staticfiles
ensure_owner media
[ -n "${N8N_DOMAIN}" ] && ensure_owner volumes/n8n

# ── 3. Puertos (solo en el primer deploy; luego son del propio proyecto) ───────
if [ -z "$(docker compose ps -q django 2>/dev/null)" ]; then
    echo "▶ Verificando puertos..."
    bash check-ports.sh || { echo "Error: hay puertos ocupados."; exit 1; }
    echo ""
fi

# ── 4. Construir (la versión actual sigue sirviendo mientras tanto) ────────────
PREVIOUS_TAG=$(docker inspect -f '{{.Config.Image}}' "${APP_CONTAINER}" 2>/dev/null | sed -n 's/.*://p' || true)
[ "${PREVIOUS_TAG}" = "latest" ] && PREVIOUS_TAG=""

echo "▶ Construyendo imágenes..."
export IMAGE_TAG="${GIT_SHA}"
dc build
docker tag "${PROJECT_NAME}_app:${GIT_SHA}" "${PROJECT_NAME}_app:latest"
echo ""

# ── 5. Servicios de datos + decisión de backup ─────────────────────────────────
echo "▶ Iniciando base de datos y Redis..."
DATA_SERVICES=(redis)
[ "${POSTGRES_MODE}" = "container" ] && DATA_SERVICES+=(postgres)
dc up -d --wait "${DATA_SERVICES[@]}"

run_django() { dc run --rm --no-deps -T django "$@"; }

PENDING=0
run_django python manage.py migrate --check >/dev/null 2>&1 || PENDING=1
HAS_DATA=0
run_django python manage.py shell -c \
    "import sys; from django.db import connection; sys.exit(0 if 'django_migrations' in connection.introspection.table_names() else 1)" \
    >/dev/null 2>&1 && HAS_DATA=1

BACKUP_FILE=""
case "${BACKUP}" in
    never)  echo "  Backup: omitido (BACKUP=never)" ;;
    always) DO_BACKUP=1 ;;
    *)      DO_BACKUP=$PENDING ;;
esac
if [ "${BACKUP}" != "never" ]; then
    if [ "${HAS_DATA}" = "0" ]; then
        echo "  Backup: no necesario (base de datos vacía, primer deploy)"
    elif [ "${DO_BACKUP}" = "1" ]; then
        [ "${PENDING}" = "1" ] && echo "▶ Hay migraciones pendientes → backup previo..." || echo "▶ Backup previo (BACKUP=always)..."
        BACKUP_FILE=$(bash scripts/backup.sh "pre-${GIT_SHA}") || { echo "Error: el backup falló. Deploy abortado (la versión actual sigue en marcha)."; exit 1; }
        echo "  Backup: ${BACKUP_FILE}"
    else
        echo "  Backup: omitido (sin migraciones pendientes)"
    fi
fi
echo ""

# ── 6. Reiniciar solo lo que cambió ────────────────────────────────────────────
echo "▶ Aplicando cambios..."
dc up -d --remove-orphans

# ── 7. Verificar salud ─────────────────────────────────────────────────────────
echo "▶ Esperando a que Django esté healthy..."
if wait_healthy 240; then
    echo "  Django healthy."
else
    echo ""
    echo "✗ Django no pasó el healthcheck. Últimos logs:" >&2
    docker logs --tail 50 "${APP_CONTAINER}" >&2 || true
    echo "" >&2
    if [ "${PENDING}" = "0" ] && [ -n "${PREVIOUS_TAG}" ]; then
        echo "▶ Sin migraciones aplicadas: rollback automático a ${PREVIOUS_TAG}..." >&2
        IMAGE_TAG="${PREVIOUS_TAG}" dc up -d --no-build --no-deps django
        wait_healthy 120 && echo "✓ Rollback completado (${PREVIOUS_TAG})." >&2 || echo "✗ El rollback tampoco quedó healthy." >&2
    else
        echo "Este deploy aplicó migraciones: el rollback de imagen no las revierte." >&2
        [ -n "${BACKUP_FILE}" ] && echo "  Restaurar datos:  make restore FILE=${BACKUP_FILE}" >&2
        [ -n "${PREVIOUS_TAG}" ] && echo "  Volver al código: make rollback TAG=${PREVIOUS_TAG}" >&2
    fi
    exit 1
fi

# ── 8. Registro y limpieza ─────────────────────────────────────────────────────
mkdir -p .deploy
if [ -n "${PREVIOUS_TAG}" ] && [ "${PREVIOUS_TAG}" != "${GIT_SHA}" ]; then
    echo "${PREVIOUS_TAG}" > .deploy/previous
fi
echo "${GIT_SHA}" > .deploy/current

# Conservar las 3 últimas imágenes de la app; el resto (y capas huérfanas) se eliminan
docker images "${PROJECT_NAME}_app" --format '{{.Tag}}' | grep -v '^latest$' | tail -n +4 \
    | xargs -r -I{} docker rmi "${PROJECT_NAME}_app:{}" >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true

echo ""
echo "✓ Despliegue completado (${GIT_SHA}) → https://${DOMAIN}"
[ -n "${N8N_DOMAIN}" ] && echo "✓ n8n disponible → https://${N8N_DOMAIN}"
exit 0
