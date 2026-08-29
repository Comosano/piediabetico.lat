#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  BACKUP_OBJECTS.SH — piediabetico.lat                                ║
# ║  Respalda objetos y buckets de MinIO mediante mc / S3 sync seguro    ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/piediabetico/objects}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_ID="objects_${TIMESTAMP}"
OUTPUT_DIR="${BACKUP_DIR}/${BACKUP_ID}"
ARCHIVE_FILE="${BACKUP_DIR}/${BACKUP_ID}.tar.gz"

mkdir -p "${OUTPUT_DIR}"

MINIO_CONTAINER="${MINIO_CONTAINER:-piediadbetico_minio}"
BUCKET_NAME="${BUCKET_NAME:-piediabetico-media}"

echo "[$(date -u)] Iniciando backup de objetos MinIO (${BUCKET_NAME})..."

START_TIME=$(date +%s)

# Opción 1: Exportar datos desde el volumen de MinIO /data de forma consistente
docker cp "${MINIO_CONTAINER}:/data" "${OUTPUT_DIR}/raw_data"

# Empaquetar y comprimir objetos con tar
tar -czf "${ARCHIVE_FILE}" -C "${OUTPUT_DIR}" raw_data
rm -rf "${OUTPUT_DIR}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

SHA256_HASH=$(sha256sum "${ARCHIVE_FILE}" | awk '{print $1}')
SIZE_BYTES=$(stat -c%s "${ARCHIVE_FILE}" 2>/dev/null || stat -f%z "${ARCHIVE_FILE}")

echo "[$(date -u)] ✓ Backup de objetos MinIO completado: ${ARCHIVE_FILE} (${SIZE_BYTES} bytes, SHA256: ${SHA256_HASH}, Duración: ${DURATION}s)"
