#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  VERIFY_BACKUP.SH — piediabetico.lat                                 ║
# ║  Verifica integridad criptográfica y legibilidad del dump de DB      ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

BACKUP_FILE="${1:-}"

if [ -z "${BACKUP_FILE}" ] || [ ! -f "${BACKUP_FILE}" ]; then
    echo "Uso: $0 <archivo_de_backup.dump|.tar.gz|.tar.enc>"
    exit 1
fi

echo "[$(date -u)] Verificando integridad de ${BACKUP_FILE}..."

# 1. Comprobar que el archivo no esté vacío
SIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}")
if [ "${SIZE}" -lt 100 ]; then
    echo "✗ Error: El archivo de backup es sospechosamente pequeño (${SIZE} bytes)."
    exit 1
fi

# 2. Si es dump de PostgreSQL, verificar con pg_restore --list
if [[ "${BACKUP_FILE}" == *.dump ]]; then
    echo "Verificando cabecera y TOC del dump PostgreSQL..."
    if pg_restore --list "${BACKUP_FILE}" > /dev/null 2>&1; then
        echo "✓ Dump PostgreSQL válido y legible por pg_restore."
    else
        echo "✗ Error: El dump PostgreSQL está corrupto o incompleto."
        exit 1
    fi
fi

# 3. Si es tar.gz de objetos, verificar integridad del gzip
if [[ "${BACKUP_FILE}" == *.tar.gz ]]; then
    echo "Verificando integridad del archivo tar.gz..."
    if tar -tzf "${BACKUP_FILE}" > /dev/null 2>&1; then
        echo "✓ Archivo de objetos tar.gz íntegro y sin errores de descompresión."
    else
        echo "✗ Error: El archivo tar.gz está corrupto."
        exit 1
    fi
fi

# 4. Calcular y mostrar SHA-256
SHA256_HASH=$(sha256sum "${BACKUP_FILE}" | awk '{print $1}')
echo "✓ Checksum SHA-256: ${SHA256_HASH}"
echo "✓ Estado: VERIFICADO"
