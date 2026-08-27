#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  ENTRYPOINT.SH — piediabetico.lat                                  ║
# ╠══════════════════════════════════════════════════════════════════════╣
# ║  Ejecuta automáticamente cuando el contenedor de la API arranca.   ║
# ║  Orden:                                                            ║
# ║    1. Esperar a que PostgreSQL esté listo                          ║
# ║    2. Ejecutar migraciones de Alembic                              ║
# ║    3. Crear buckets de MinIO si no existen                         ║
# ║    4. Iniciar la API FastAPI                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝

set -e  # Detener si cualquier comando falla

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  piediabetico.lat — Iniciando API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Esperar a PostgreSQL ───────────────────────────────────────────
echo "[1/4] Esperando a PostgreSQL..."

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-adminpd}"
MAX_RETRIES=30
RETRY=0

until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge $MAX_RETRIES ]; then
        echo "✗ PostgreSQL no respondió después de $MAX_RETRIES intentos. Abortando."
        exit 1
    fi
    echo "  PostgreSQL no disponible aún — reintentando ($RETRY/$MAX_RETRIES)..."
    sleep 2
done

echo "✓ PostgreSQL listo"

# ── 2. Ejecutar migraciones de Alembic ───────────────────────────────
echo "[2/4] Ejecutando migraciones de Alembic..."

cd /app

# Verificar que alembic.ini existe
if [ ! -f "alembic.ini" ]; then
    echo "✗ alembic.ini no encontrado en /app/"
    exit 1
fi

# Ejecutar la migración
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "✓ Migraciones aplicadas correctamente"
else
    echo "✗ Error en las migraciones de Alembic"
    exit 1
fi

# ── 3. Crear buckets de MinIO ─────────────────────────────────────────
echo "[3/4] Configurando MinIO..."

MINIO_ENDPOINT="${MINIO_ENDPOINT:-minio:9000}"
MINIO_USER="${MINIO_ROOT_USER:-adminminio}"
MINIO_PASS="${MINIO_ROOT_PASSWORD:-}"

# Esperar a MinIO
RETRY=0
until curl -sf "http://$MINIO_ENDPOINT/minio/health/live" > /dev/null 2>&1; do
    RETRY=$((RETRY + 1))
    if [ $RETRY -ge 15 ]; then
        echo "  MinIO no disponible — continuando sin crear buckets"
        break
    fi
    sleep 2
done

if [ $RETRY -lt 15 ]; then
    # Crear buckets usando la API de MinIO (mc no está instalado, usamos Python)
    python3 -c "
import os
from minio import Minio
from minio.error import S3Error

endpoint = os.getenv('MINIO_ENDPOINT', 'minio:9000')
user     = os.getenv('MINIO_ROOT_USER', 'adminminio')
password = os.getenv('MINIO_ROOT_PASSWORD', '')

buckets = [
    os.getenv('MINIO_BUCKET_IMAGENES', 'imagenes-medicas'),
    os.getenv('MINIO_BUCKET_REPORTES', 'reportes-pdf'),
]

try:
    client = Minio(endpoint, access_key=user, secret_key=password, secure=False)
    for bucket in buckets:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            print(f'  Bucket creado: {bucket}')
        else:
            print(f'  Bucket ya existe: {bucket}')
except Exception as e:
    print(f'  Advertencia MinIO: {e}')
" 2>/dev/null || echo "  MinIO: configuración manual necesaria"

    echo "✓ MinIO configurado"
fi

# ── 4. Iniciar la API FastAPI ─────────────────────────────────────────
echo "[4/4] Iniciando API FastAPI..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Docs: http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Ejecutar el comando pasado al contenedor (definido en docker-compose.yml)
exec "$@"
