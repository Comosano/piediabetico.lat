#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════════╗
# ║  VERIFY_RESTIC.SH — piediabetico.lat                                 ║
# ║  Verificación de Integridad y Política de Retención Restic / R2      ║
# ╚══════════════════════════════════════════════════════════════════════╝
set -euo pipefail

echo "[$(date -u)] [1/3] Listando snapshots disponibles en Cloudflare R2..."
restic snapshots

echo "[$(date -u)] [2/3] Verificando integridad de datos (check 100% de índices y árboles)..."
restic check

echo "[$(date -u)] [3/3] Simulando política de retención (7 daily, 4 weekly, 3 monthly)..."
# Ejecutar dry-run de forget para previsualizar retención sin borrar sin confirmación
restic forget \
    --keep-daily 7 \
    --keep-weekly 4 \
    --keep-monthly 3 \
    --dry-run

echo "✓ Repositorio Restic verificado y saludable."
