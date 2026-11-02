#!/bin/bash
# restore.sh — restaura un backup .sql.gz (DESTRUCTIVO: reemplaza el contenido de la DB)
# Uso: bash scripts/restore.sh backups/archivo.sql.gz

set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/lib.sh
load_env
build_profiles

FILE=${1:?Uso: bash scripts/restore.sh backups/archivo.sql.gz}
[ -f "$FILE" ] || { echo "Error: no existe $FILE" >&2; exit 1; }

echo "Se reemplazará la base '${POSTGRES_DB}' con $FILE."
read -r -p "Escribe el nombre de la base para confirmar: " CONFIRM
[ "$CONFIRM" = "${POSTGRES_DB}" ] || { echo "Cancelado."; exit 1; }

echo "▶ Deteniendo Django..."
dc stop django

SQL_RESET="DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
echo "▶ Restaurando..."
if [ "${POSTGRES_MODE}" = "container" ]; then
    dc exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "$SQL_RESET"
    gunzip -c "$FILE" | dc exec -T postgres psql -v ON_ERROR_STOP=1 -q -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
else
    PSQL=(docker run --rm -i --add-host host.docker.internal:host-gateway -e PGPASSWORD="${POSTGRES_PASSWORD}" postgres:17-alpine
          psql -v ON_ERROR_STOP=1 -h "${POSTGRES_HOST:-host.docker.internal}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}")
    "${PSQL[@]}" -c "$SQL_RESET"
    gunzip -c "$FILE" | "${PSQL[@]}" -q
fi

echo "▶ Iniciando Django..."
dc up -d --no-build django
echo "✓ Restauración completada."
