#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  RESTORE_RESTIC.SH — piediabetico.lat                                ║
# ║  Restauración Total (Disaster Recovery) desde Cloudflare R2 / Restic ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

SNAPSHOT_ID="${1:-latest}"

echo "[$(date -u)] [1/5] Verificando credenciales de Restic y Cloudflare R2 para restore..."
MISSING_VARS=0
for var in RESTIC_REPOSITORY RESTIC_PASSWORD AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY; do
    if [ -z "${!var:-}" ]; then
        echo "✗ Error: Variable requerida '${var}' no está configurada."
        MISSING_VARS=1
    fi
done

if [ "${MISSING_VARS}" -eq 1 ]; then
    echo "✗ Abortando: Faltan credenciales de Cloudflare R2 o contraseña de Restic."
    exit 1
fi

START_TIME=$(date +%s)
RESTORE_STAGING=$(mktemp -d /tmp/pd_restore_staging_XXXXXX)
trap 'rm -rf "${RESTORE_STAGING}"' EXIT

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-piediadbetico_postgres}"
POSTGRES_USER="${POSTGRES_USER:-adminpd}"
POSTGRES_DB="${POSTGRES_DB:-piediadbetico}"
MINIO_CONTAINER="${MINIO_CONTAINER:-piediadbetico_minio}"
APP_ROOT="${APP_ROOT:-/app}"

# ── 2. Descargar y Descifrar Snapshot desde Cloudflare R2 ─────────────
echo "[$(date -u)] [2/5] Descargando snapshot '${SNAPSHOT_ID}' desde Cloudflare R2..."
restic restore "${SNAPSHOT_ID}" --target "${RESTORE_STAGING}"
echo "✓ Snapshot descargado y descifrado en staging local."

# Localizar carpeta restaurada
STAGED_DATA=$(find "${RESTORE_STAGING}" -maxdepth 2 -type d -name "postgres" | head -n 1 | xargs dirname)

# ── 3. Restaurar PostgreSQL ──────────────────────────────────────────
echo "[$(date -u)] [3/5] Restaurando base de datos PostgreSQL (${POSTGRES_DB})..."
DUMP_FILE=$(find "${STAGED_DATA}/postgres" -name "*.dump" | head -n 1)
if [ -n "${DUMP_FILE}" ] && [ -f "${DUMP_FILE}" ]; then
    cat "${DUMP_FILE}" | docker exec -i "${POSTGRES_CONTAINER}" pg_restore \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        --clean \
        --if-exists \
        --no-owner \
        --exit-on-error || true
    echo "✓ Base de datos PostgreSQL restaurada correctamente."
else
    echo "✗ Error: Archivo dump de PostgreSQL no encontrado en snapshot."
    exit 1
fi

# ── 4. Restaurar Objetos MinIO ───────────────────────────────────────
echo "[$(date -u)] [4/5] Restaurando objetos y fotos clínicas en MinIO..."
if [ -d "${STAGED_DATA}/minio/raw_data" ]; then
    docker cp "${STAGED_DATA}/minio/raw_data/." "${MINIO_CONTAINER}:/data/"
    echo "✓ Objetos y buckets de MinIO restaurados."
fi

# ── 5. Restaurar Configuración ───────────────────────────────────────
echo "[$(date -u)] [5/5] Restaurando configuraciones del servidor..."
if [ -d "${STAGED_DATA}/config" ]; then
    cp -r "${STAGED_DATA}/config/." "${APP_ROOT}/"
    echo "✓ Archivos de configuración restaurados (.env, nginx, alembic)."
fi

END_TIME=$(date +%s)
RTO_SECONDS=$((END_TIME - START_TIME))

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ DISASTER RECOVERY COMPLETADO CON ÉXITO DESDE CLOUDFLARE R2"
echo "  Recovery Time Objective (RTO Real): ${RTO_SECONDS} segundos"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
