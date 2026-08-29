#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  DEPLOY.SH — Script de Despliegue Idempotente para Producción       ║
# ║  Plataforma: piediabetico.lat                                        ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/piediabetico}"
cd "${APP_DIR}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🦶 piediabetico.lat — Despliegue de Stack de Producción"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. Validar existencia de .env seguro ───────────────────────────────
echo "[1/5] Verificando archivo de configuración .env..."
if [ ! -f "${APP_DIR}/backend/.env" ] && [ ! -f "${APP_DIR}/.env" ]; then
    echo "✗ Error: No se encontró el archivo .env en ${APP_DIR}."
    echo "  Copie .env.example como .env y complete las variables antes de continuar."
    exit 1
fi
echo "✓ Archivo .env presente."

# ── 2. Construir e Iniciar Contenedores Docker ─────────────────────────
echo "[2/5] Construyendo e iniciando contenedores Docker..."
docker compose -f backend/docker-compose.prod.yml up -d --build

# ── 3. Esperar que PostgreSQL esté listo ───────────────────────────────
echo "[3/5] Verificando estado saludable de PostgreSQL..."
RETRIES=30
until docker compose -f backend/docker-compose.prod.yml exec -T postgres pg_isready -U adminpd > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
    echo "  Esperando a PostgreSQL... ($RETRIES intentos restantes)"
    sleep 2
    RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
    echo "✗ Error: PostgreSQL no respondió a tiempo."
    exit 1
fi
echo "✓ PostgreSQL activo y saludable."

# ── 4. Ejecutar Migraciones Alembic ────────────────────────────────────
echo "[4/5] Ejecutando migraciones de base de datos Alembic..."
docker compose -f backend/docker-compose.prod.yml exec -T api alembic upgrade head
echo "✓ Migraciones Alembic aplicadas exitosamente (HEAD = 003_care_relationships)."

# ── 5. Healthcheck en Runtime ──────────────────────────────────────────
echo "[5/5] Ejecutando healthcheck en runtime..."
sleep 3
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health || echo "000")

if [ "$HEALTH_STATUS" -eq 200 ]; then
    echo "✓ Healthcheck exitoso (HTTP 200: {\"status\":\"ok\"})"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🎉 DESPLIEGUE FINALIZADO EXITOSAMENTE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "✗ Error: Healthcheck falló con código HTTP ${HEALTH_STATUS}."
    exit 1
fi
