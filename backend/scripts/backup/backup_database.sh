#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  BACKUP_DATABASE.SH — piediabetico.lat                               ║
# ║  Genera dump consistente y comprimido de PostgreSQL sin locks       ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/piediabetico/db}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_ID="db_${TIMESTAMP}"
OUTPUT_FILE="${BACKUP_DIR}/${BACKUP_ID}.dump"
LOG_FILE="${BACKUP_DIR}/${BACKUP_ID}.log"

mkdir -p "${BACKUP_DIR}"

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-piediadbetico_postgres}"
POSTGRES_USER="${POSTGRES_USER:-adminpd}"
POSTGRES_DB="${POSTGRES_DB:-piediadbetico}"

echo "[$(date -u)] Iniciando backup consistente de PostgreSQL (${POSTGRES_DB})..."

START_TIME=$(date +%s)

# Ejecutar pg_dump consistente en formato custom (comprimido, apto para pg_restore)
docker exec "${POSTGRES_CONTAINER}" pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --format=custom \
    --compress=9 \
    --no-owner \
    --clean \
    --if-exists \
    > "${OUTPUT_FILE}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Calcular checksum SHA-256
SHA256_HASH=$(sha256sum "${OUTPUT_FILE}" | awk '{print $1}')
SIZE_BYTES=$(stat -c%s "${OUTPUT_FILE}" 2>/dev/null || stat -f%z "${OUTPUT_FILE}")

echo "[$(date -u)] ✓ Backup de DB completado: ${OUTPUT_FILE} (${SIZE_BYTES} bytes, SHA256: ${SHA256_HASH}, Duración: ${DURATION}s)"
