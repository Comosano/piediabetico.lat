#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  RESTORE_OBJECTS.SH — piediabetico.lat                               ║
# ║  Restaura objetos y buckets de MinIO desde archivo tar.gz            ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

ARCHIVE_FILE="${1:-}"

if [ -z "${ARCHIVE_FILE}" ] || [ ! -f "${ARCHIVE_FILE}" ]; then
    echo "Uso: $0 <ruta_al_archivo_objetos.tar.gz>"
    exit 1
fi

MINIO_CONTAINER="${MINIO_CONTAINER:-piediadbetico_minio}"
TMP_RESTORE_DIR=$(mktemp -d)

echo "[$(date -u)] Descomprimiendo objetos de respaldo en ${TMP_RESTORE_DIR}..."

tar -xzf "${ARCHIVE_FILE}" -C "${TMP_RESTORE_DIR}"

if [ -d "${TMP_RESTORE_DIR}/raw_data" ]; then
    echo "Copiando datos restaurados hacia el contenedor MinIO ${MINIO_CONTAINER}:/data..."
    docker cp "${TMP_RESTORE_DIR}/raw_data/." "${MINIO_CONTAINER}:/data/"
    echo "✓ Objetos restaurados en MinIO."
else
    echo "✗ Error: Estructura de objetos no encontrada en el archivo de respaldo."
fi

rm -rf "${TMP_RESTORE_DIR}"
echo "[$(date -u)] ✓ Restauración de objetos completada."
