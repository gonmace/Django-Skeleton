#!/bin/bash
# lib.sh — funciones comunes de deploy/backup/rollback (se usa con `source`).
# Requiere ejecutarse desde la raíz del proyecto.

load_env() {
    if [ ! -f .env ]; then
        echo "Error: no se encontró el archivo .env. Ejecuta: bash setup.sh" >&2
        exit 1
    fi
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a

    PROJECT_NAME=${PROJECT_NAME:?La variable PROJECT_NAME no está definida en .env}
    APP_PORT=${APP_PORT:-8000}
    POSTGRES_MODE=${POSTGRES_MODE:-container}
    N8N_DOMAIN=${N8N_DOMAIN:-}
    N8N_MCP_ENABLED=${N8N_MCP_ENABLED:-}
    APP_CONTAINER="${PROJECT_NAME}_app"
}

# Rellena el array PROFILES con los --profile que correspondan según el .env
build_profiles() {
    PROFILES=()
    [ "${POSTGRES_MODE}" = "container" ] && PROFILES+=(--profile postgres)
    if [ -n "${N8N_DOMAIN}" ]; then
        PROFILES+=(--profile n8n)
        [ "${N8N_MCP_ENABLED}" = "true" ] && PROFILES+=(--profile n8n-mcp)
    fi
    return 0
}

# docker compose con los profiles del proyecto
dc() {
    docker compose ${PROFILES[@]+"${PROFILES[@]}"} "$@"
}

# Espera a que el contenedor Django esté healthy. Uso: wait_healthy [segundos]
wait_healthy() {
    local timeout=${1:-180} waited=0 status
    while [ "$waited" -lt "$timeout" ]; do
        status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${APP_CONTAINER}" 2>/dev/null || echo missing)
        case "$status" in
            healthy) return 0 ;;
            unhealthy) return 1 ;;
        esac
        sleep 3
        waited=$((waited + 3))
    done
    return 1
}
