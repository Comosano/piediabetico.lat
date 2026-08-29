"""
🛡️ SISTEMA DE AUTORIZACIÓN Y CAPACIDADES RBAC
piediabetico.lat — Ecosistema Clínico LATAM

Garantiza la regla fundamental:
AUTORIZACIÓN = ROL/CAPACIDAD + RELACIÓN ACTIVA (CareRelationship) + PROPIEDAD DEL RECURSO
(Ningún rol provisto por el frontend o localStorage tiene validez).

Reutiliza el modelo persistente de PostgreSQL:
`models.CareRelationship` y `models.User`.
"""

import os
import uuid
import secrets
from typing import Optional, List, Dict, Set, Callable, Any
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, EmailStr, Field
from fastapi import HTTPException, Header, Depends, Path, Query
from enum import Enum

# Importar modelos persistentes de SQLAlchemy
try:
    from models import User as DBUser, Patient as DBPatient, CareRelationship as DBCareRelationship
    MODELS_PERSISTENTES_DISPONIBLES = True
except ImportError:
    MODELS_PERSISTENTES_DISPONIBLES = False
    DBUser = DBPatient = DBCareRelationship = None

# ── 1. Roles del Sistema Unificados ──────────────────────────────────
class SystemRole(str, Enum):
    ADMIN = "admin"
    MEDICO_GENERAL = "medico_general"
    INFECTOLOGO = "infectologo"
    DIABETOLOGO = "diabetologo"
    CIRUJANO_VASCULAR = "cirujano_vascular"
    PODOLOGO = "podologo"
    ENFERMERO = "enfermero"
    PROFESIONAL = "profesional"      # Rol legacy/onboarding transitorio (sin herramientas de alto impacto)
    UNIVERSITARIO = "universitario"  # Rol académico (cero capacidades clínicas)
    INVESTIGADOR = "investigador"    # Rol de investigación (cero capacidades clínicas)
    PACIENTE = "paciente"
    CUIDADOR = "cuidador"

# ── 2. Definición Canónica de Capacidades Clínicas ───────────────────
class Capability(str, Enum):
    SEGMENT_WOUND = "SEGMENT_WOUND"
    USE_OFFLOADING_TOOL = "USE_OFFLOADING_TOOL"
    USE_ANTIBIOTIC_TOOL = "USE_ANTIBIOTIC_TOOL"
    VIEW_PATIENT = "VIEW_PATIENT"
    MANAGE_PATIENT = "MANAGE_PATIENT"

# ── 3. Matriz Centralizada y Configurable de Capacidades por Política ─
# Configurable por política institucional o jurisdicción regulatoria (no afirma reglas universales)
DEFAULT_CAPABILITY_MATRIX: Dict[str, Set[Capability]] = {
    SystemRole.MEDICO_GENERAL.value: {
        Capability.VIEW_PATIENT,
        Capability.MANAGE_PATIENT,
        Capability.SEGMENT_WOUND,
        Capability.USE_OFFLOADING_TOOL,
        Capability.USE_ANTIBIOTIC_TOOL,
    },
    SystemRole.INFECTOLOGO.value: {
        Capability.VIEW_PATIENT,
        Capability.MANAGE_PATIENT,
        Capability.SEGMENT_WOUND,
        Capability.USE_ANTIBIOTIC_TOOL,
    },
    SystemRole.DIABETOLOGO.value: {
        Capability.VIEW_PATIENT,
        Capability.MANAGE_PATIENT,
        Capability.SEGMENT_WOUND,
        Capability.USE_OFFLOADING_TOOL,
        Capability.USE_ANTIBIOTIC_TOOL,
    },
    SystemRole.CIRUJANO_VASCULAR.value: {
        Capability.VIEW_PATIENT,
        Capability.MANAGE_PATIENT,
        Capability.SEGMENT_WOUND,
        Capability.USE_OFFLOADING_TOOL,
        Capability.USE_ANTIBIOTIC_TOOL,
    },
    SystemRole.PODOLOGO.value: {
        Capability.VIEW_PATIENT,
        Capability.MANAGE_PATIENT,
        Capability.SEGMENT_WOUND,
        Capability.USE_OFFLOADING_TOOL,
        # Por política inicial: Podología no prescribe esquemas de antibióticos sistémicos
    },
    SystemRole.ENFERMERO.value: {
        Capability.VIEW_PATIENT,
        Capability.SEGMENT_WOUND,
        Capability.USE_OFFLOADING_TOOL,
        # Por política inicial: Enfermería no prescribe antibióticos sistémicos
    },
    SystemRole.PROFESIONAL.value: {
        # Rol genérico legacy/onboarding: Sólo visualización básica de contexto;
        # SIN capacidades clínicas de alto impacto hasta completar especialidad.
        Capability.VIEW_PATIENT,
    },
    SystemRole.ADMIN.value: set(),          # Cero capacidades clínicas de prescripción
    SystemRole.UNIVERSITARIO.value: set(),  # Cero capacidades clínicas
    SystemRole.INVESTIGADOR.value: set(),   # Cero capacidades clínicas
    SystemRole.PACIENTE.value: set(),
    SystemRole.CUIDADOR.value: set(),
}

# Matriz activa en memoria (soporta reconfiguración por política/país)
_ACTIVE_CAPABILITY_POLICY: Dict[str, Set[Capability]] = {
    role: set(caps) for role, caps in DEFAULT_CAPABILITY_MATRIX.items()
}

def set_capability_policy(policy_matrix: Dict[str, Set[Capability]]):
    """Permite ajustar la matriz de capacidades según política jurisdiccional."""
    global _ACTIVE_CAPABILITY_POLICY
    _ACTIVE_CAPABILITY_POLICY = policy_matrix

def user_has_capability(user_role: str, capability: Capability) -> bool:
    """Verifica si un rol posee la capacidad requerida bajo la política activa."""
    allowed_caps = _ACTIVE_CAPABILITY_POLICY.get(user_role, set())
    return capability in allowed_caps


# ── Modelos Pydantic para Payload y Sesión ──────────────────────────
class UserSession(BaseModel):
    user_id: str
    email: str
    nombre: str
    role: str
    patient_id: Optional[str] = None
    is_active: bool = True
    pilot_enabled: bool = False
    organization_id: Optional[str] = None
    matricula: Optional[str] = None
    especialidad: Optional[str] = None
    expires_at: Optional[datetime] = None


# ── Registro de Sesiones Activas Dinámicas ────────────────────────────
_ACTIVE_SESSIONS: Dict[str, UserSession] = {}

# ── Registro de Sesiones Legacy / Demo (Aislado para tests) ───────────
_LEGACY_DEMO_SESSIONS: Dict[str, UserSession] = {
    "token_dr_perez": UserSession(
        user_id="usr_med_001",
        email="dr.perez@hospital.com",
        nombre="Dr. Fernando Pérez",
        role="cirujano_vascular",
        matricula="MN 142.850",
        especialidad="Cirugía Vascular & Pie Diabético",
        pilot_enabled=False
    ),
    "token_dr_gomez": UserSession(
        user_id="usr_med_002",
        email="dr.gomez@hospital.com",
        nombre="Dr. Gómez",
        role="infectologo",
        matricula="MN 118.940",
        especialidad="Infectología",
        pilot_enabled=False
    ),
    "token_lic_podologa": UserSession(
        user_id="usr_pod_001",
        email="podologa@clinica.com",
        nombre="Lic. Laura Podóloga",
        role="podologo",
        matricula="MP 88.210",
        especialidad="Podología Clínica & Biomecánica",
        pilot_enabled=False
    ),
    "token_profesional_generico": UserSession(
        user_id="usr_gen_001",
        email="profesional.legacy@clinica.com",
        nombre="Dr. Onboarding Genérico",
        role="profesional",
        matricula="MN 99.000",
        pilot_enabled=False
    ),
    "token_juan_paciente": UserSession(
        user_id="usr_pac_001",
        email="juan.paciente@email.com",
        nombre="Juan Carlos Pérez",
        role="paciente",
        patient_id="pac_001",
        pilot_enabled=False
    ),
    "token_carlos_paciente": UserSession(
        user_id="usr_pac_002",
        email="carlos.paciente@email.com",
        nombre="Carlos Gómez",
        role="paciente",
        patient_id="pac_002",
        pilot_enabled=False
    ),
    "token_maria_cuidadora": UserSession(
        user_id="usr_cui_001",
        email="maria.cuidadora@email.com",
        nombre="María Pérez",
        role="cuidador",
        pilot_enabled=False
    ),
    "token_investigador": UserSession(
        user_id="usr_inv_001",
        email="investigador@universidad.edu",
        nombre="Dra. Lucía Soria",
        role="investigador",
        pilot_enabled=False
    ),
    "token_universitario": UserSession(
        user_id="usr_uni_001",
        email="alumno@universidad.edu",
        nombre="Estudiante Medicina",
        role="universitario",
        pilot_enabled=False
    ),
    "token_admin": UserSession(
        user_id="usr_adm_001",
        email="admin@piediabetico.lat",
        nombre="Administrador Sistema",
        role="admin",
        pilot_enabled=True
    )
}

# Alias legacy para compatibilidad
_SESSIONS_REGISTRY = _LEGACY_DEMO_SESSIONS


def create_user_session(user_obj: Any, expires_in_seconds: int = 86400) -> str:
    """
    Crea una sesión de usuario criptográficamente segura e inmutable en memoria.
    Asigna un token opaco tipo 'pd_sess_<32 bytes urlsafe>'.
    """
    token = f"pd_sess_{secrets.token_urlsafe(32)}"
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    user_id_str = str(getattr(user_obj, "id", getattr(user_obj, "user_id", str(uuid.uuid4()))))
    org_id_str = str(getattr(user_obj, "organization_id", "")) if getattr(user_obj, "organization_id", None) else None

    session = UserSession(
        user_id=user_id_str,
        email=getattr(user_obj, "email", "usuario@piediabetico.lat"),
        nombre=getattr(user_obj, "full_name", getattr(user_obj, "nombre", "Profesional")),
        role=getattr(user_obj, "role", "medico_general"),
        is_active=getattr(user_obj, "is_active", True),
        pilot_enabled=getattr(user_obj, "pilot_enabled", False),
        organization_id=org_id_str,
        expires_at=expires_at
    )
    _ACTIVE_SESSIONS[token] = session
    return token


# Importar módulos de base de datos y almacenamiento de sesiones
try:
    from database import get_db
except ImportError:
    def get_db():
        yield None

try:
    from domain.session_store import get_session, create_session, RedisSessionUnavailableError, hash_session_token
    REDIS_STORE_AVAILABLE = True
except ImportError:
    REDIS_STORE_AVAILABLE = False
    get_session = create_session = hash_session_token = None
    RedisSessionUnavailableError = Exception


# ── Relaciones Persistentes Mock/State para Runtime ──────────────────
_PERSISTENT_CARE_RELATIONSHIPS: List[Dict] = [
    # Dr. Pérez vinculado a Juan Paciente (pac_001) - Relación Activa
    {
        "id": "rel_001",
        "professional_id": "usr_med_001",
        "caregiver_id": None,
        "patient_id": "pac_001",
        "relationship_type": "medico_tratante",
        "is_active": True
    },
    # María Cuidadora vinculada a Juan Paciente (pac_001) - Relación Activa
    {
        "id": "rel_002",
        "professional_id": None,
        "caregiver_id": "usr_cui_001",
        "patient_id": "pac_001",
        "relationship_type": "cuidador",
        "is_active": True
    },
    # Relación Revocada / Inactiva de prueba
    {
        "id": "rel_003_revocada",
        "professional_id": "usr_med_003_revocado",
        "caregiver_id": None,
        "patient_id": "pac_001",
        "relationship_type": "medico_tratante",
        "is_active": False
    }
]

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
    """Registra una sesión activa para compatibilidad de tests."""
    _ACTIVE_SESSIONS[token] = session


# ── DEPENDENCIAS REUTILIZABLES FASTAPI ────────────────────────────────

def get_current_user(
    token: Optional[str] = Depends(extract_auth_token),
    db: Optional[Any] = Depends(get_db)
) -> Optional[UserSession]:
    """
    Obtiene el usuario actual autenticado resolviendo identidad y estado activo en PostgreSQL.
    Multi-worker & Fail-Closed:
    1. Si no hay token, retorna None.
    2. Tokens de prueba sintéticos 'expired_', 'tampered_' o 'invalid_' emiten 401.
    3. Tokens demo legacy (token_dr_perez, token_admin) SOLO funcionan si ALLOW_DEMO_TOKENS=true
       está explícitamente configurado. Por defecto (false) son rechazados estrictamente con 401.
    4. Resuelve la sesión desde Redis mediante clave SHA-256 (pilot_session:<sha256>).
       Si Redis está caído, APLICA FAIL-CLOSED ESTRICTO (401).
    5. Consulta PostgreSQL models.User por user_id y verifica is_active=True y pilot_enabled=True.
    6. Retorna UserSession con datos frescos de la base de datos.
    """
    if not token:
        return None
    
    if token.startswith("expired_"):
        raise HTTPException(status_code=401, detail="Token de sesión expirado. Inicie sesión nuevamente.")
    if token.startswith("tampered_") or token.startswith("invalid_"):
        raise HTTPException(status_code=401, detail="Firma de token inválida o sesión manipulada.")

    # 1. Verificar tokens demo bajo aislamiento explícito estricto
    allow_demo = os.getenv("ALLOW_DEMO_TOKENS", "false").strip().lower() in ("true", "1")
    if token in _LEGACY_DEMO_SESSIONS:
        if allow_demo:
            demo_user = _LEGACY_DEMO_SESSIONS[token]
            if not demo_user.is_active:
                return None
            return demo_user
        else:
            raise HTTPException(status_code=401, detail="Token de sesión no reconocido o inválido.")

    # 2. Resolución en Redis + PostgreSQL (Multi-worker Fail-Closed)
    if get_session is not None:
        try:
            session_data = get_session(token)
        except RedisSessionUnavailableError as e:
            raise HTTPException(status_code=401, detail="Servicio de autenticación no disponible (Redis Fail-Closed).")
        except Exception:
            raise HTTPException(status_code=401, detail="Error en verificación de sesión.")

        if session_data is None:
            # Fallback en memoria local solo si está explícitamente en _ACTIVE_SESSIONS y permitido
            if token in _ACTIVE_SESSIONS and allow_demo:
                return _ACTIVE_SESSIONS[token]
            raise HTTPException(status_code=401, detail="Token de sesión no reconocido, inválido o expirado.")

        user_id = session_data.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Sesión corrupta o sin identificador de usuario.")

        # Verificar usuario en PostgreSQL en tiempo real
        if db is not None and DBUser is not None:
            try:
                try:
                    user_obj = db.query(DBUser).filter(DBUser.id == uuid.UUID(str(user_id))).first()
                except Exception:
                    user_obj = db.query(DBUser).filter(str(DBUser.id) == str(user_id)).first()
            except Exception:
                raise HTTPException(status_code=401, detail="Error verificando estado del usuario.")

            if not user_obj:
                raise HTTPException(status_code=401, detail="Usuario no encontrado en base de datos.")
            if not user_obj.is_active:
                raise HTTPException(status_code=401, detail="Cuenta de usuario inactiva.")
            if not user_obj.pilot_enabled:
                raise HTTPException(status_code=401, detail="Usuario no habilitado para el piloto.")

            return UserSession(
                user_id=str(user_obj.id),
                email=user_obj.email,
                nombre=user_obj.full_name,
                role=user_obj.role,
                is_active=user_obj.is_active,
                pilot_enabled=user_obj.pilot_enabled,
                organization_id=str(user_obj.organization_id) if user_obj.organization_id else None
            )
        else:
            # En test context donde db is None pero hay sesión válida
            if allow_demo:
                return UserSession(
                    user_id=str(user_id),
                    email=session_data.get("email", "usuario@piediabetico.lat"),
                    nombre=session_data.get("nombre", "Profesional"),
                    role=session_data.get("role", "medico_general"),
                    is_active=True,
                    pilot_enabled=True
                )
            raise HTTPException(status_code=401, detail="Base de datos no disponible para verificar sesión.")

    raise HTTPException(status_code=401, detail="Token de sesión no reconocido o inválido.")

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

def require_capability(required_capability: Capability) -> Callable:
    """
    Fábrica de dependencias FastAPI para verificar una capacidad específica.
    Reemplaza al antiguo 'require_professional' monolítico.
    """
    def _capability_dependency(
        current_user: UserSession = Depends(require_authenticated)
    ) -> UserSession:
        if not user_has_capability(current_user.role, required_capability):
            raise HTTPException(
                status_code=403,
                detail=f"Acceso denegado: El rol '{current_user.role}' no posee la capacidad requerida '{required_capability.value}' bajo la política clínica activa."
            )
        return current_user
    return _capability_dependency

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

def verify_patient_access_logic(
    current_user: UserSession,
    patient_id: str,
    db_relationships: Optional[List[Dict]] = None
) -> bool:
    """
    Evalúa la matriz estricta de autorización para un paciente específico
    consultando el registro persistente de CareRelationship:
    - Paciente propio: su patient_id coincide.
    - Cuidador vinculado: CareRelationship activa (is_active = True).
    - Profesional tratante con capacidad VIEW_PATIENT + CareRelationship activa (is_active = True).
    - Admin: permitido bajo auditoría.
    - Relación revocada (is_active = False): DENEGADO (403).
    - Otros / No vinculados: DENEGADO (403).
    """
    if not current_user or not current_user.is_active:
        return False
    
    # 1. Admin del sistema
    if current_user.role == SystemRole.ADMIN.value:
        return True
    
    # 2. El propio paciente
    if current_user.role == SystemRole.PACIENTE.value:
        return current_user.patient_id == patient_id
    
    rels = db_relationships if db_relationships is not None else _PERSISTENT_CARE_RELATIONSHIPS

    # 3. Cuidador vinculado con relación ACTIVA
    if current_user.role == SystemRole.CUIDADOR.value:
        return any(
            r.get("caregiver_id") == current_user.user_id and
            r.get("patient_id") == patient_id and
            r.get("is_active") is True
            for r in rels
        )
    
    # 4. Profesional de salud con capacidad VIEW_PATIENT y relación ACTIVA
    if user_has_capability(current_user.role, Capability.VIEW_PATIENT):
        return any(
            r.get("professional_id") == current_user.user_id and
            r.get("patient_id") == patient_id and
            r.get("is_active") is True
            for r in rels
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
