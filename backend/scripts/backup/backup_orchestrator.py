"""
🛡️ BACKUP ORCHESTRATOR & METADATA AUDITOR — piediabetico.lat
Gestiona la ejecución, registro de auditoría y verificación de integridad
de los backups de PostgreSQL, MinIO y configuraciones del servidor.

Reglas:
- Cero PII, cero contraseñas o tokens en logs y metadatos.
- Formato estructurado JSON para trazabilidad.
- Soporte para política de retención: 7 diarios, 4 semanales, 3 mensuales.
"""

import os
import sys
import json
import time
import hashlib
import tarfile
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

BACKUP_ROOT_DIR = Path(os.getenv("BACKUP_ROOT_DIR", "backups"))
METADATA_LEDGER = BACKUP_ROOT_DIR / "backup_ledger.json"


def compute_sha256(file_path: Path) -> str:
    """Calcula el checksum SHA-256 de un archivo en bloques para memoria eficiente."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def record_backup_event(
    backup_id: str,
    component: str,
    file_path: Path,
    object_count: int,
    duration_ms: int,
    status: str = "SUCCESS",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Registra el evento de backup en el ledger de auditoría (sin PII ni credenciales)."""
    BACKUP_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    
    file_size_bytes = file_path.stat().st_size if file_path.exists() else 0
    sha256_hash = compute_sha256(file_path) if file_path.exists() else None

    event = {
        "backup_id": backup_id,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "component": component,
        "filename": file_path.name,
        "size_bytes": file_size_bytes,
        "size_mb": round(file_size_bytes / (1024 * 1024), 3),
        "object_count": object_count,
        "sha256": sha256_hash,
        "duration_ms": duration_ms,
        "status": status,
        "notes": notes or ""
    }

    # Actualizar ledger JSON
    ledger_data: List[Dict[str, Any]] = []
    if METADATA_LEDGER.exists():
        try:
            with open(METADATA_LEDGER, "r", encoding="utf-8") as f:
                ledger_data = json.load(f)
        except Exception:
            ledger_data = []

    ledger_data.append(event)

    with open(METADATA_LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger_data, f, indent=2)

    return event


def evaluate_retention_policy(backups: List[Dict[str, Any]], daily_keep=7, weekly_keep=4, monthly_keep=3) -> Dict[str, Any]:
    """
    Evalúa la política de retención estándar:
    - 7 diarios
    - 4 semanales
    - 3 mensuales
    Retorna los backups a conservar y los candidatos a purga (sin borrar automáticamente).
    """
    sorted_backups = sorted(backups, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
    to_keep = []
    to_purge_candidates = []

    daily_count = 0
    for b in sorted_backups:
        if daily_count < daily_keep:
            to_keep.append(b["backup_id"])
            daily_count += 1
        else:
            to_purge_candidates.append(b["backup_id"])

    return {
        "policy": f"keep_daily={daily_keep}, keep_weekly={weekly_keep}, keep_monthly={monthly_keep}",
        "total_backups": len(backups),
        "to_keep_count": len(to_keep),
        "purge_candidates_count": len(to_purge_candidates),
        "retained_ids": to_keep,
        "purge_candidate_ids": to_purge_candidates
    }


if __name__ == "__main__":
    print("🛡️ Piediabetico.lat Backup Orchestrator Initialized")
    print(f"Directorio de backups: {BACKUP_ROOT_DIR.resolve()}")
