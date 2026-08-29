#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  BACKUP_CONFIGURATION.SH — piediabetico.lat                         ║
# ║  Cifra y respalda configuraciones críticas del servidor              ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/piediabetico/config}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_ID="config_${TIMESTAMP}"
OUTPUT_ARCHIVE="${BACKUP_DIR}/${BACKUP_ID}.tar"
OUTPUT_ENCRYPTED="${BACKUP_DIR}/${BACKUP_ID}.tar.enc"

mkdir -p "${BACKUP_DIR}"

APP_ROOT="${APP_ROOT:-/app}"
BACKUP_PASSPHRASE="${BACKUP_PASSPHRASE:-}"

if [ -z "${BACKUP_PASSPHRASE}" ]; then
    echo "✗ Error: BACKUP_PASSPHRASE no está configurada. Imposible cifrar configuración."
    exit 1
fi

echo "[$(date -u)] Iniciando empaquetado y cifrado de configuraciones críticas..."

START_TIME=$(date +%s)

# Empaquetar solo archivos de configuración necesarios para reconstrucción
tar -cf "${OUTPUT_ARCHIVE}" \
    -C "${APP_ROOT}" \
    .env \
    docker-compose.prod.yml \
    nginx_piediabetico.conf \
    alembic.ini \
    2>/dev/null || true

# Cifrado AES-256-CBC con PBKDF2
openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
    -in "${OUTPUT_ARCHIVE}" \
    -out "${OUTPUT_ENCRYPTED}" \
    -pass pass:"${BACKUP_PASSPHRASE}"

# Eliminar archivo no cifrado
rm -f "${OUTPUT_ARCHIVE}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

SHA256_HASH=$(sha256sum "${OUTPUT_ENCRYPTED}" | awk '{print $1}')
SIZE_BYTES=$(stat -c%s "${OUTPUT_ENCRYPTED}" 2>/dev/null || stat -f%z "${OUTPUT_ENCRYPTED}")

echo "[$(date -u)] ✓ Configuración cifrada con éxito: ${OUTPUT_ENCRYPTED} (${SIZE_BYTES} bytes, SHA256: ${SHA256_HASH}, Duración: ${DURATION}s)"
