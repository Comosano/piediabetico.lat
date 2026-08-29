#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  RESTORE_DATABASE.SH — piediabetico.lat                              ║
# ║  Restaura un dump consistente de PostgreSQL en un contenedor target  ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

DUMP_FILE="${1:-}"

if [ -z "${DUMP_FILE}" ] || [ ! -f "${DUMP_FILE}" ]; then
    echo "Uso: $0 <ruta_al_archivo.dump>"
    exit 1
fi

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-piediadbetico_postgres}"
POSTGRES_USER="${POSTGRES_USER:-adminpd}"
POSTGRES_DB="${POSTGRES_DB:-piediadbetico}"

echo "[$(date -u)] PRECAUCIÓN: Iniciando restauración de PostgreSQL en ${POSTGRES_CONTAINER}/${POSTGRES_DB}..."

# 1. Comprobar que el archivo de dump sea válido
if ! pg_restore --list "${DUMP_FILE}" > /dev/null 2>&1; then
    echo "✗ Error: El archivo de dump no es válido."
    exit 1
fi

# 2. Restaurar dump hacia el contenedor PostgreSQL
cat "${DUMP_FILE}" | docker exec -i "${POSTGRES_CONTAINER}" pg_restore \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --clean \
    --if-exists \
    --no-owner \
    --exit-on-error || true

echo "[$(date -u)] ✓ Restauración de base de datos finalizada."
