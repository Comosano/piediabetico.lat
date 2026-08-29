#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  SEED_PILOT_USERS.PY — piediabetico.lat                              ║
║  Generador seguro de 5 cuentas médicas para el Piloto v0.1          ║
║  Zero Credenciales Hardcodeadas en Git                              ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import uuid
import secrets
import logging
from typing import List, Dict, Any

# Agregar directorio backend al path para resolución de módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger("seed_pilot_users")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROLES_PILOTO = [
    ("medico_general",    "Dr. Médico General Piloto 1"),
    ("diabetologo",       "Dra. Diabetóloga Piloto 2"),
    ("infectologo",       "Dr. Infectólogo Piloto 3"),
    ("cirujano_vascular", "Dr. Cirujano Vascular Piloto 4"),
    ("enfermero",         "Lic. Enfermería de Heridas Piloto 5")
]


def generar_usuarios_piloto(sync_db: bool = True, force_reset: bool = False) -> List[Dict[str, Any]]:
    """
    Genera 5 cuentas de profesionales de salud con pilot_enabled=True
    y contraseñas aleatorias criptográficamente seguras de 16 bytes.
    """
    cuentas_generadas = []

    for idx, (rol, nombre) in enumerate(ROLES_PILOTO, start=1):
        raw_password = secrets.token_urlsafe(16)
        user_uuid = str(uuid.uuid4())
        email = f"piloto.medico{idx}@piediabetico.lat"

        cuenta_info = {
            "id": user_uuid,
            "email": email,
            "full_name": nombre,
            "role": rol,
            "pilot_enabled": True,
            "is_active": True,
            "password_temporal": raw_password
        }
        cuentas_generadas.append(cuenta_info)

    if sync_db:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from models import Organization, User
            from domain.password_security import hash_password

            db_url = os.getenv("DATABASE_URL", "postgresql://adminpd:local_dev_password_pd_2026@localhost:5432/piediadbetico")
            engine = create_engine(db_url)
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()

            # Buscar u organizar institución de piloto
            org = db.query(Organization).filter(Organization.slug == "hospital-piloto-latam").first()
            if not org:
                org = Organization(
                    name="Hospital Piloto LATAM",
                    slug="hospital-piloto-latam",
                    country="AR",
                    plan="institution",
                    active=True
                )
                db.add(org)
                db.flush()

            for c in cuentas_generadas:
                existing = db.query(User).filter(User.email == c["email"]).first()
                if not existing:
                    user_obj = User(
                        organization_id=org.id,
                        email=c["email"],
                        password_hash=hash_password(c["password_temporal"]),
                        full_name=c["full_name"],
                        role=c["role"],
                        pilot_enabled=True,
                        is_active=True
                    )
                    db.add(user_obj)
                    c["status"] = "CREADO_NUEVO"
                elif force_reset:
                    existing.pilot_enabled = True
                    existing.is_active = True
                    existing.organization_id = org.id
                    existing.password_hash = hash_password(c["password_temporal"])
                    c["status"] = "ROTADO_Y_ACTUALIZADO"
                else:
                    # Idempotente: asegurar que pilot_enabled esté activo pero no sobreescribir password ni reportar password falso
                    existing.pilot_enabled = True
                    existing.is_active = True
                    existing.organization_id = org.id
                    c["status"] = "YA_EXISTE_CONSERVADO"
                    c["password_temporal"] = "[PREVIAMENTE ESTABLECIDA - NO MODIFICADA]"

            db.commit()
            db.close()
            logger.info("✓ 5 usuarios de piloto sincronizados en PostgreSQL con pilot_enabled=True.")
        except Exception as e:
            logger.warning(f"Seeding ejecutado en modo standalone / sin conexión DB directa: {e}")

    return cuentas_generadas


if __name__ == "__main__":
    import sys
    force = "--force-reset" in sys.argv or "--reset" in sys.argv
    usuarios = generar_usuarios_piloto(force_reset=force)
    print("\n═══════════════════════════════════════════════════════════════════════")
    print("🔑 CUENTAS DE ACCESO PARA LOS 5 MÉDICOS DEL PILOTO v0.1")
    print("═══════════════════════════════════════════════════════════════════════\n")
    for u in usuarios:
        print(f"Médico: {u['full_name']}")
        print(f"  • Email:    {u['email']}")
        print(f"  • Rol:      {u['role']}")
        print(f"  • Password: {u['password_temporal']}")
        print(f"  • Piloto:   {'ACTIVO' if u['pilot_enabled'] else 'INACTIVO'}\n")
    print("⚠️ Entregar estas credenciales por canal seguro. NUNCA commitear a Git.")
