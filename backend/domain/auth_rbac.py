"""
🛡️ SISTEMA DE AUTORIZACIÓN Y RBAC (Role-Based Access Control)
piediabetico.lat — Ecosistema Clínico LATAM

Garantiza la regla fundamental:
AUTORIZACIÓN = ROL + RELACIÓN ACTIVA (CareRelationship) + PROPIEDAD DEL RECURSO
(Ningún rol provisto por el frontend o localStorage tiene validez).
"""

import os
import secrets
from typing import Optional, List, Dict, Set
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from fastapi import HTTPException, Header, Depends, Path, Query
from enum import Enum

# ── Roles del Sistema ────────────────────────────────────────────────
class SystemRole(str, Enum):
    ADMIN = "admin"
    MEDICO_GENERAL = "medico_general"
    INFECTOLOGO = "infectologo"
    DIABETOLOGO = "diabetologo"
    CIRUJANO_VASCULAR = "cirujano_vascular"
    PODOLOGO = "podologo"
    ENFERMERO = "enfermero"
    PROFESIONAL = "profesional"  # Alias genérico para profesionales de salud
    UNIVERSITARIO = "universitario"
    PACIENTE = "paciente"
    CUIDADOR = "cuidador"
    INVESTIGADOR = "investigador"

PROFESSIONAL_ROLES: Set[str] = {
    SystemRole.ADMIN.value,
    SystemRole.MEDICO_GENERAL.value,
    SystemRole.INFECTOLOGO.value,
    SystemRole.DIABETOLOGO.value,
    SystemRole.CIRUJANO_VASCULAR.value,
    SystemRole.PODOLOGO.value,
    SystemRole.ENFERMERO.value,
    SystemRole.PROFESIONAL.value,
}

# ── Modelos de Datos de Sesión y Relación ───────────────────────────
class UserSession(BaseModel):
    user_id: str
    email: EmailStr
    nombre: str
    role: str
    patient_id: Optional[str] = None
    is_active: bool = True
    matricula: Optional[str] = None
    especialidad: Optional[str] = None

class CareRelationship(BaseModel):
    id: str
    professional_id: Optional[str] = None  # user_id del médico
    caregiver_id: Optional[str] = None     # user_id del cuidador
    patient_id: str                        # ID del paciente
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ── Base de Datos de Cuentas y Tokens (Integrada con agente14_auth) ──
_SESSIONS_REGISTRY: Dict[str, UserSession] = {
    "token_dr_perez": UserSession(
        user_id="usr_med_001",
        email="dr.perez@hospital.com",
        nombre="Dr. Fernando Pérez",
        role="profesional",
        matricula="MN 142.850",
        especialidad="Cirugía Vascular & Pie Diabético"
    ),
    "token_dr_gomez": UserSession(
        user_id="usr_med_002",
        email="dr.gomez@hospital.com",
        nombre="Dr. Gómez",
        role="infectologo",
        matricula="MN 118.940",
        especialidad="Infectología"
    ),
    "token_juan_paciente": UserSession(
        user_id="usr_pac_001",
        email="juan.paciente@email.com",
        nombre="Juan Carlos Pérez",
        role="paciente",
        patient_id="pac_001"
    ),
    "token_carlos_paciente": UserSession(
        user_id="usr_pac_002",
        email="carlos.paciente@email.com",
        nombre="Carlos Gómez",
        role="paciente",
        patient_id="pac_002"
    ),
    "token_maria_cuidadora": UserSession(
        user_id="usr_cui_001",
        email="maria.cuidadora@email.com",
        nombre="María Pérez",
        role="cuidador"
    ),
    "token_investigador": UserSession(
        user_id="usr_inv_001",
        email="investigador@universidad.edu",
        nombre="Dra. Lucía Soria",
        role="investigador"
    ),
    "token_admin": UserSession(
        user_id="usr_adm_001",
        email="admin@piediabetico.lat",
        nombre="Administrador Sistema",
        role="admin"
    )
}

# ── Relaciones Activas (CareRelationships) ───────────────────────────
_CARE_RELATIONSHIPS_DB: List[CareRelationship] = [
    # Dr. Pérez atiende a Juan Paciente (pac_001)
    CareRelationship(
        id="rel_001",
        professional_id="usr_med_001",
        patient_id="pac_001",
        is_active=True
    ),
    # María Cuidadora atiende a Juan Paciente (pac_001)
    CareRelationship(
        id="rel_002",
        caregiver_id="usr_cui_001",
        patient_id="pac_001",
        is_active=True
    )
    # Dr. Gómez NO tiene relación con pac_001
]

# ── Mapeo de Lesiones a Pacientes ───────────────────────────────────
_WOUNDS_PATIENTS_MAP: Dict[str, str] = {
    "DFU-2026-0042": "pac_001",
    "DFU-2026-0043": "pac_001",
    "DFU-2026-0099": "pac_002",
}

# ── Funciones de Utilidad y Extracción de Token ──────────────────────
def extract_auth_token(
    authorization: Optional[str] = Header(None),
    x_session_token: Optional[str] = Header(None, alias="X-Session-Token")
) -> Optional[str]:
    """Extrae el token de Authorization: Bearer <token> o X-Session-Token."""
    if x_session_token:
        return x_session_token.strip()
    if authorization and authorization.startswith("Bearer "):
        return authorization.split("Bearer ")[1].strip()
    if authorization and not authorization.startswith("Bearer "):
        return authorization.strip()
    return None

def register_active_session(token: str, session: UserSession):
    """Registra una sesión activa tras el 2FA exitoso."""
    _SESSIONS_REGISTRY[token] = session


# ── DEPENDENCIAS REUTILIZABLES FASTAPI ────────────────────────────────

def get_current_user(
    token: Optional[str] = Depends(extract_auth_token)
) -> Optional[UserSession]:
    """Obtiene el usuario actual autenticado o None si es anónimo."""
    if not token:
        return None
    return _SESSIONS_REGISTRY.get(token)

def require_authenticated(
    current_user: Optional[UserSession] = Depends(get_current_user)
) -> UserSession:
    """Exige que el usuario esté debidamente autenticado (401 si no)."""
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Autenticación requerida. Inicie sesión o proporcione credenciales válidas."
        )
    return current_user

def require_professional(
    current_user: UserSession = Depends(require_authenticated)
) -> UserSession:
    """Exige que el usuario posea un rol profesional de salud o admin (403 si no)."""
    if current_user.role not in PROFESSIONAL_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Acceso restringido: Se requiere rol profesional de salud habilitado."
        )
    return current_user

def require_admin(
    current_user: UserSession = Depends(require_authenticated)
) -> UserSession:
    """Exige que el usuario posea el rol de administrador (403 si no)."""
    if current_user.role != SystemRole.ADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado: Se requieren privilegios de Administrador del Sistema."
        )
    return current_user

def verify_patient_access_logic(current_user: UserSession, patient_id: str) -> bool:
    """
    Evalúa la matriz estricta de autorización para un paciente específico:
    - Paciente propio: su patient_id coincide.
    - Cuidador autorizado: existe CareRelationship activa.
    - Profesional tratante: existe CareRelationship activa.
    - Admin: permitido bajo auditoría.
    - Otros: DENEGADO (403).
    """
    if not current_user:
        return False
    
    # 1. Admin del sistema
    if current_user.role == SystemRole.ADMIN.value:
        return True
    
    # 2. El propio paciente
    if current_user.role == SystemRole.PACIENTE.value:
        return current_user.patient_id == patient_id
    
    # 3. Cuidador vinculado
    if current_user.role == SystemRole.CUIDADOR.value:
        return any(
            rel.caregiver_id == current_user.user_id and rel.patient_id == patient_id and rel.is_active
            for rel in _CARE_RELATIONSHIPS_DB
        )
    
    # 4. Profesional de salud vinculado
    if current_user.role in PROFESSIONAL_ROLES:
        return any(
            rel.professional_id == current_user.user_id and rel.patient_id == patient_id and rel.is_active
            for rel in _CARE_RELATIONSHIPS_DB
        )
    
    return False

def check_patient_authorization(patient_id: str, current_user: UserSession):
    """Lanza 403 si el usuario actual no tiene permiso sobre patient_id."""
    if not verify_patient_access_logic(current_user, patient_id):
        raise HTTPException(
            status_code=403,
            detail=f"Acceso denegado: No posee relación clínica activa ni titularidad sobre el paciente '{patient_id}'."
        )

def check_wound_authorization(wound_id: str, current_user: UserSession):
    """Valida permiso sobre una úlcera verificando su paciente propietario."""
    patient_id = _WOUNDS_PATIENTS_MAP.get(wound_id)
    if not patient_id:
        raise HTTPException(status_code=404, detail=f"Lesión '{wound_id}' no encontrada.")
    check_patient_authorization(patient_id, current_user)
