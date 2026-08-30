"""
╔══════════════════════════════════════════════════════════════════════╗
║  PILOT ROUTER — piediabetico.lat v0.1                                ║
║  Piloto Cerrado: 5 Médicos · Casos Pseudonimizados · Timeline        ║
║  Retención Dual (72h Aislado / 21d Longitudinal) · Diseñado sin PII  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import uuid
import time
import secrets
import hashlib
import base64
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Header, status, Response
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from PIL import Image

from models import PilotCase, PilotWound, PilotAnalysis, PilotFeedback, PilotEvolutionFeedback, PilotUploadToken, User
from domain.auth_rbac import (
    require_capability,
    require_authenticated,
    Capability,
    UserSession,
    create_user_session
)
from domain.password_security import verify_password
from domain.session_store import create_session, RedisSessionUnavailableError
from database import get_db
from domain.storage_service import save_image_bytes, get_image_bytes, delete_image_bytes
from agente4_clasificador_ulcera import (
    _inferir as inferir_clasificador,
    ClasificadorInput,
    check_classifier_readiness
)
from agente4_segmentacion_unet import (
    predecir_segmentacion,
    SegmentacionInput,
    check_segmentation_readiness
)

logger = logging.getLogger(__name__)

router_pilot = APIRouter(prefix="/api/pilot", tags=["Piloto Cerrado v0.1"])


# ── SANITIZACIÓN & RE-ENCODING SERVER-SIDE (ZERO CLIENT TRUST) ────────

def sanitizar_y_reencodear_imagen_servidor(
    imagen_base64: str,
    max_bytes: int = 10 * 1024 * 1024, # 10 MB
    max_dimension: int = 4096
) -> bytes:
    """
    Decodifica y re-encodea la imagen del lado del servidor (Zero Client Trust).
    - Valida tamaño máximo de payload (10MB).
    - Valida que sea decodificable como imagen real (JPEG/PNG/WEBP).
    - Valida dimensiones máximas (<= 4096px).
    - Remueve metadatos EXIF / GPS reconstruyendo los píxeles puros en RGB.
    - Re-encodea a JPEG limpio.
    """
    if not imagen_base64:
        raise HTTPException(status_code=400, detail="La carga de imagen está vacía.")

    if "," in imagen_base64:
        _, data_part = imagen_base64.split(",", 1)
    else:
        data_part = imagen_base64

    try:
        raw_bytes = base64.b64decode(data_part)
    except Exception:
        raise HTTPException(status_code=400, detail="Formato Base64 inválido.")

    if len(raw_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="La imagen excede el tamaño máximo permitido (10MB).")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # Validar formato permitido
            if img.format not in ("JPEG", "PNG", "WEBP", "MPO"):
                raise HTTPException(status_code=415, detail=f"Formato de imagen no permitido: {img.format}")

            # Validar dimensiones
            width, height = img.size
            if width > max_dimension or height > max_dimension:
                raise HTTPException(status_code=400, detail=f"Dimensiones de imagen ({width}x{height}) exceden el límite de {max_dimension}px.")

            # Convertir a RGB puro eliminando EXIF/GPS
            rgb_img = img.convert("RGB")
            output_buffer = io.BytesIO()
            rgb_img.save(output_buffer, format="JPEG", quality=85, optimize=True)
            return output_buffer.getvalue()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error decodificando imagen en servidor: {e}")
        raise HTTPException(status_code=400, detail="El archivo no es una imagen decodificable válida.")


# ── SCHEMAS ───────────────────────────────────────────────────────────

class PilotLoginInput(BaseModel):
    email: str = Field(..., description="Correo electrónico institucional del profesional.")
    password: str = Field(..., min_length=6, description="Contraseña del profesional.")


class PilotUserOutput(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: Optional[str] = None
    pilot_enabled: bool


class PilotLoginOutput(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400 # 24 horas en segundos
    user: PilotUserOutput


class PilotAIReadinessOutput(BaseModel):
    classifier_artifact_path: str
    classifier_artifact_exists: bool
    classifier_loadable: bool
    classifier_status: str # "READY", "MISSING_ARTIFACT", "LOAD_ERROR"
    segmentation_artifact_path: str
    segmentation_artifact_exists: bool
    segmentation_loadable: bool
    segmentation_status: str # "READY", "MISSING_ARTIFACT", "LOAD_ERROR"
    overall_status: str # "ALL_MODELS_READY", "SEGMENTATION_ONLY", "CLASSIFIER_ONLY", "MODELS_UNAVAILABLE"
    message: str


class PilotTokenCreateInput(BaseModel):
    due_days: int = Field(4, description="Días sugeridos para la toma de control (por defecto 4).")
    expire_days: int = Field(7, description="Días hasta la caducidad del enlace (por defecto 7).")


class PilotTokenOutput(BaseModel):
    token: str
    url: str
    due_at: str
    expires_at: str


class PilotPatientUploadInput(BaseModel):
    imagen_base64: str = Field(..., description="Foto capturada por el paciente en Base64.")
    privacy_gate_confirmed: bool = Field(..., description="Certificación de privacidad 4 checks.")
    quality_score: int = Field(..., ge=0, le=100, description="Puntaje de calidad óptica.")


class PilotPatientUploadOutput(BaseModel):
    exito: bool
    retry_allowed: bool = False
    analysis_uuid: Optional[str] = None
    mensaje: str

class PilotCaseCreateInput(BaseModel):
    case_alias: Optional[str] = Field(None, description="Alias pseudonimizado (ej. PILOT-0001). Cero PII.")


class PilotCaseOutput(BaseModel):
    id: str
    pilot_case_uuid: str
    case_alias: str
    is_active: bool
    created_at: str


class PilotWoundSummary(BaseModel):
    id: str
    wound_uuid: str
    wound_label: str
    wound_location: str
    created_at: str


class PilotCaseWithWoundsOutput(BaseModel):
    id: str
    pilot_case_uuid: str
    case_alias: str
    is_active: bool
    created_at: str
    wounds: List[PilotWoundSummary] = []


class PilotWoundCreateInput(BaseModel):
    wound_label: str = Field("Herida 1", description="Etiqueta ordinal (ej. 'Herida 1', 'Herida 2').")
    wound_location: str = Field("Plantar", description="Ubicación anatómica general (ej. 'Talón', 'Hallux', 'Dorsal').")


class PilotWoundOutput(BaseModel):
    id: str
    wound_uuid: str
    pilot_case_uuid: str
    wound_label: str
    wound_location: str
    created_at: str


class PilotShadowModeInput(BaseModel):
    pre_classification: str = Field(..., description="'Normal(Healthy skin)', 'Abnormal(Ulcer)' o 'Indeterminada'")
    pre_infection: Optional[str] = Field("Ausente", description="'Presente', 'Ausente' o 'Dudoso'")


class PilotAnalisisInput(BaseModel):
    imagen_base64: str = Field(..., description="Foto de la lesión sanitizada en Base64.")
    privacy_gate_confirmed: bool = Field(..., description="Confirmación explícita del profesional de que la toma no contiene rostro, pulsera, documentos ni PII visible.")
    quality_score: int = Field(..., ge=0, le=100, description="Puntuación óptica del Quality Gate (0-100, umbral técnico heurístico del piloto = 48).")
    quality_status: str = Field("optimo", description="'optimo', 'advertencia' o 'insuficiente'")
    pilot_case_uuid: Optional[str] = Field(None, description="UUID del caso pseudonimizado si es seguimiento longitudinal.")
    pilot_wound_uuid: Optional[str] = Field(None, description="UUID de la herida específica si es seguimiento longitudinal.")
    taken_at_custom: Optional[str] = Field(None, description="Fecha real histórica de la toma si el profesional la conoce (ISO).")
    sequence_index: Optional[int] = Field(None, description="Índice ordinal secuencial de la foto (1, 2, 3...) cuando la fecha es desconocida.")
    shadow_mode: Optional[PilotShadowModeInput] = Field(None, description="Evaluación clínica previa cegada al resultado de la IA.")
    scale_detected: bool = Field(False, description="Indica si existe marcador métrico físico calibrado.")
    px_per_cm: Optional[float] = Field(None, description="Píxeles/cm si scale_detected es True.")


class PilotAnalisisOutput(BaseModel):
    exito: bool
    analysis_uuid: str
    pilot_case_uuid: str
    pilot_wound_uuid: Optional[str] = None
    photo_uuid: str
    ai_status: str # "COMPLETED", "PARTIAL", "NO_EVALUABLE", "AI_UNAVAILABLE", "AI_FAILED"
    classification_status: str = "SKIPPED" # "COMPLETED", "AI_UNAVAILABLE", "AI_FAILED", "SKIPPED"
    segmentation_status: str = "SKIPPED" # "COMPLETED", "AI_UNAVAILABLE", "AI_FAILED", "SKIPPED"
    quality_gate_score: int
    quality_gate_status: str
    classification_label: Optional[str] = None
    classification_confidence: Optional[float] = None
    scale_detected: bool
    pixel_area: Optional[int] = None
    relative_area_percent: Optional[float] = None
    absolute_area_cm2: Optional[float] = None # estrictamente None sin calibrador
    segmentation_mask_base64: Optional[str] = None
    shadow_mode_recorded: bool
    concordance_pre_ai: Optional[bool] = None
    processing_duration_ms: int
    taken_at_display: str
    sequence_index: Optional[int] = None
    is_longitudinal: bool
    created_at: str
    expires_at: str
    mensaje: str


class PilotFeedbackInput(BaseModel):
    analysis_uuid: str = Field(..., description="UUID del análisis a evaluar.")
    is_clinically_evaluable: bool = Field(..., description="¿La imagen era clínicamente evaluable? (True/False)")
    segmentation_rating: str = Field(..., description="'Correcta', 'Parcial' o 'Incorrecta'")
    concordance_rating: str = Field(..., description="'Sí', 'Parcial' o 'No'")
    would_modify_classification: bool = Field(..., description="¿Modificarías la clasificación? (True/False)")
    utility_score: int = Field(..., ge=1, le=5, description="Utilidad percibida (1 a 5).")
    comment: Optional[str] = Field(None, max_length=250, description="Comentario libre opcional (máx. 250 caracteres). AVISO: No incluya nombres ni otros datos identificatorios del paciente.")


class PilotFeedbackOutput(BaseModel):
    exito: bool
    feedback_id: str
    analysis_uuid: str
    mensaje: str


class PilotEvolutionFeedbackInput(BaseModel):
    baseline_analysis_uuid: str = Field(..., description="UUID del análisis inicial / anterior.")
    followup_analysis_uuid: str = Field(..., description="UUID del análisis actual / posterior.")
    clinical_evolution: str = Field(..., description="'MEJOR', 'SIMILAR' o 'PEOR'")
    system_representation_agreement: str = Field(..., description="'SI', 'PARCIAL' o 'NO'")
    comment: Optional[str] = Field(None, max_length=250, description="Comentario libre opcional (máx. 250 caracteres). AVISO: No incluya nombres ni datos identificatorios.")


class PilotEvolutionFeedbackOutput(BaseModel):
    exito: bool
    feedback_id: str
    mensaje: str


class TimelineEventItem(BaseModel):
    analysis_uuid: str
    photo_uuid: str
    sequence_index: Optional[int] = None
    taken_at: Optional[str] = None
    display_date: str
    quality_gate_score: int
    quality_gate_status: str
    ai_status: str
    classification_status: Optional[str] = None
    segmentation_status: Optional[str] = None
    classification_label: Optional[str] = None
    classification_confidence: Optional[float] = None
    pixel_area: Optional[int] = None
    relative_area_percent: Optional[float] = None
    segmentation_mask_base64: Optional[str] = None
    has_feedback: bool
    feedback_rating: Optional[str] = None


class PilotWoundTimelineGroup(BaseModel):
    wound_uuid: str
    wound_label: str
    wound_location: str
    events: List[TimelineEventItem]


class PilotCaseTimelineOutput(BaseModel):
    pilot_case_uuid: str
    case_alias: str
    created_at: str
    wounds: List[PilotWoundTimelineGroup]


# ── ENDPOINT DE LOGIN AUTENTICADO DEL PILOTO (POSTGRESQL + ARGON2ID) ──

@router_pilot.post("/auth/login", response_model=PilotLoginOutput)
def login_piloto_profesional(
    payload: PilotLoginInput,
    db: Optional[Session] = Depends(get_db)
):
    """
    Inicio de sesión seguro para profesionales médicos del Piloto Cerrado:
    - Valida existencia del usuario en la base de datos PostgreSQL.
    - Valida que la cuenta esté activa (is_active=True).
    - Valida que esté expresamente habilitado para el piloto (pilot_enabled=True).
    - Verifica el hash criptográfico de la contraseña (Argon2id / PBKDF2-SHA256).
    - Retorna un error 401 genérico e idéntico ante cualquier discrepancia (Zero User Enumeration).
    - Emite un token de sesión opaco seguro (pd_sess_<32_bytes_urlsafe>) con TTL de 24h.
    """
    email_clean = payload.email.lower().strip()
    user = None

    if db is not None:
        try:
            user = db.query(User).filter(User.email == email_clean).first()
        except Exception as e:
            logger.error(f"Error consultando usuario en PostgreSQL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de comunicación con el servicio de autenticación."
            )

    # Si no se encuentra el usuario en DB
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o acceso no autorizado.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validar cuenta activa y habilitada para piloto
    if not user.is_active or not user.pilot_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o acceso no autorizado.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validar contraseña contra hash criptográfico
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o acceso no autorizado.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Actualizar fecha de último login si hay DB
    if db is not None:
        try:
            user.last_login_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as e:
            logger.warning(f"No se pudo registrar last_login_at: {e}")

    # Emitir sesión opaca segura en Redis (con clave pilot_session:<sha256> y TTL 24h)
    try:
        token = create_session(user_id=str(user.id), ttl_seconds=86400)
    except RedisSessionUnavailableError as e:
        logger.error(f"Fallo crítico registrando sesión en Redis: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Servicio de autenticación no disponible (Redis Fail-Closed)."
        )
    except Exception as e:
        logger.error(f"Error inesperado al emitir sesión: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Error al emitir sesión de usuario."
        )

    return PilotLoginOutput(
        access_token=token,
        token_type="Bearer",
        expires_in=86400,
        user=PilotUserOutput(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            organization_id=str(user.organization_id) if user.organization_id else None,
            pilot_enabled=user.pilot_enabled
        )
    )


# ── ENDPOINT DE READINESS CHECK REAL (DIAGNÓSTICO PRE-PILOTO PROTEGIDO) ─

@router_pilot.get(
    "/ai-readiness",
    response_model=PilotAIReadinessOutput,
    dependencies=[Depends(require_authenticated)]
)
def verificar_readiness_ia_piloto():
    """
    Chequeo de diagnóstico real del estado de los artefactos y librerías de IA:
    - Protegido: Requiere sesión profesional o administrativa válida.
    - Comprueba existencia física de los archivos de modelo.
    - Intenta carga perezosa real en memoria.
    - No ejecuta resultados clínicos simulados.
    """
    clf = check_classifier_readiness()
    seg = check_segmentation_readiness()

    clf_status = "READY" if (clf["exists"] and clf["loadable"]) else ("MISSING_ARTIFACT" if not clf["exists"] else "LOAD_ERROR")
    seg_status = "READY" if (seg["exists"] and seg["loadable"]) else ("MISSING_ARTIFACT" if not seg["exists"] else "LOAD_ERROR")

    if clf_status == "READY" and seg_status == "READY":
        overall = "ALL_MODELS_READY"
        msg = "Todos los modelos de IA están instalados y listos para inferencia real."
    elif seg_status == "READY":
        overall = "SEGMENTATION_ONLY"
        msg = "Modelo U-Net de segmentación listo. Clasificador ONNX ausente (el piloto operará con clasificación honestamente no disponible)."
    elif clf_status == "READY":
        overall = "CLASSIFIER_ONLY"
        msg = "Clasificador ONNX listo. Modelo U-Net de segmentación ausente."
    else:
        overall = "MODELS_UNAVAILABLE"
        msg = "Modelos de IA locales no disponibles en el servidor. El sistema opera en modo fail-closed sin inventar diagnósticos."

    return PilotAIReadinessOutput(
        classifier_artifact_path=clf["path"],
        classifier_artifact_exists=clf["exists"],
        classifier_loadable=clf["loadable"],
        classifier_status=clf_status,
        segmentation_artifact_path=seg["path"],
        segmentation_artifact_exists=seg["exists"],
        segmentation_loadable=seg["loadable"],
        segmentation_status=seg_status,
        overall_status=overall,
        message=msg
    )


# ── ENDPOINTS DE CASOS Y HERIDAS ──────────────────────────────────────

@router_pilot.get("/cases", response_model=List[PilotCaseWithWoundsOutput])
def listar_casos_piloto(
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Retorna la lista de casos pseudonimizados pertenecientes exclusivamente al médico autenticado.
    Anti-IDOR: No permite listar casos de otros profesionales.
    """
    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            cases = db.query(PilotCase).filter(
                PilotCase.physician_id == physician_id,
                PilotCase.is_active == True
            ).order_by(PilotCase.created_at.desc()).all()

            results = []
            for c in cases:
                wounds = db.query(PilotWound).filter(
                    PilotWound.pilot_case_id == c.id
                ).order_by(PilotWound.created_at.asc()).all()

                results.append(PilotCaseWithWoundsOutput(
                    id=str(c.id),
                    pilot_case_uuid=str(c.pilot_case_uuid),
                    case_alias=c.case_alias,
                    is_active=c.is_active,
                    created_at=c.created_at.isoformat() if c.created_at else datetime.now(timezone.utc).isoformat(),
                    wounds=[
                        PilotWoundSummary(
                            id=str(w.id),
                            wound_uuid=str(w.wound_uuid),
                            wound_label=w.wound_label,
                            wound_location=w.wound_location or "No especificada",
                            created_at=w.created_at.isoformat() if w.created_at else datetime.now(timezone.utc).isoformat()
                        ) for w in wounds
                    ]
                ))
            return results
        except Exception as e:
            logger.error(f"Error listando casos del médico: {e}")
            raise HTTPException(status_code=500, detail="Error recuperando los casos.")

    return []


@router_pilot.post("/cases", response_model=PilotCaseOutput)
def crear_caso_piloto(
    payload: PilotCaseCreateInput,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Crea un caso pseudonimizado en PostgreSQL para seguimiento longitudinal (ej. PILOT-0001).
    Anti-IDOR: Asocia el caso estrictamente al physician_id del usuario autenticado en sesión.
    """
    case_uuid = uuid.uuid4()
    alias = payload.case_alias or f"PILOT-{case_uuid.hex[:6].upper()}"
    now_dt = datetime.now(timezone.utc)

    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            case_obj = PilotCase(
                pilot_case_uuid=case_uuid,
                physician_id=physician_id,
                case_alias=alias,
                is_active=True
            )
            db.add(case_obj)
            db.commit()
            db.refresh(case_obj)

            return PilotCaseOutput(
                id=str(case_obj.id),
                pilot_case_uuid=str(case_obj.pilot_case_uuid),
                case_alias=case_obj.case_alias,
                is_active=case_obj.is_active,
                created_at=case_obj.created_at.isoformat()
            )
        except Exception as e:
            logger.error(f"Error creando caso en PostgreSQL: {e}")
            if "UUID" in str(e):
                pass
            else:
                db.rollback()
                raise HTTPException(status_code=500, detail="Error al crear el caso en la base de datos.")

    return PilotCaseOutput(
        id=str(case_uuid),
        pilot_case_uuid=str(case_uuid),
        case_alias=alias,
        is_active=True,
        created_at=now_dt.isoformat()
    )


@router_pilot.post("/cases/{case_uuid}/wounds", response_model=PilotWoundOutput)
def crear_herida_caso_piloto(
    case_uuid: str,
    payload: PilotWoundCreateInput,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Crea una herida clínica dentro de un caso pseudonimizado.
    Anti-IDOR: Valida que el caso pertenezca al médico autenticado.
    """
    wound_uuid = uuid.uuid4()
    now_dt = datetime.now(timezone.utc)

    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            try:
                c_uuid = uuid.UUID(case_uuid)
            except ValueError:
                raise HTTPException(status_code=404, detail="Identificador de caso inválido.")

            case = db.query(PilotCase).filter(
                PilotCase.pilot_case_uuid == c_uuid,
                PilotCase.physician_id == physician_id
            ).first()

            if not case:
                raise HTTPException(status_code=404, detail="Caso no encontrado o no pertenece al profesional.")

            wound_obj = PilotWound(
                wound_uuid=wound_uuid,
                pilot_case_id=case.id,
                wound_label=payload.wound_label,
                wound_location=payload.wound_location
            )
            db.add(wound_obj)
            db.commit()
            db.refresh(wound_obj)

            return PilotWoundOutput(
                id=str(wound_obj.id),
                wound_uuid=str(wound_obj.wound_uuid),
                pilot_case_uuid=str(case.pilot_case_uuid),
                wound_label=wound_obj.wound_label,
                wound_location=wound_obj.wound_location,
                created_at=wound_obj.created_at.isoformat()
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creando herida en PostgreSQL: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Error al registrar la herida.")

    return PilotWoundOutput(
        id=str(wound_uuid),
        wound_uuid=str(wound_uuid),
        pilot_case_uuid=case_uuid,
        wound_label=payload.wound_label,
        wound_location=payload.wound_location,
        created_at=now_dt.isoformat()
    )


# ── ENDPOINT DE ANÁLISIS E INFERENCIA TÉCNICA ─────────────────────────

@router_pilot.post("/analisis", response_model=PilotAnalisisOutput)
def procesar_analisis_piloto(
    payload: PilotAnalisisInput,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Procesa un análisis fotográfico del piloto cerrado con persistencia real:
    1. Anti-IDOR: Valida que el caso y la herida pertenezcan al médico autenticado.
    2. Valida confirmación explícita de Privacy Gate.
    3. Evalúa Quality Gate (NO_EVALUABLE si score < 48).
    4. Sanitiza y re-encodea imagen server-side, subiendo bytes a MinIO con clave opaca UUID.
    5. Ejecuta inferencia técnica FAIL-CLOSED (Clasificador ONNX + Segmentador U-Net).
    6. Persiste la entidad PilotAnalysis en PostgreSQL.
    7. Garantiza honestidad física (cero cm² arbitrarios sin calibrador).
    8. Aplica política de retención dual (72h aislado / 21d longitudinal).
    """
    t_inicio = time.time()

    # 1. Privacy Gate Check
    if not payload.privacy_gate_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Privacy Gate no confirmado: El profesional debe certificar expresamente que la toma no contiene rostro, pulsera, documentos ni PII visible."
        )

    now_dt = datetime.now(timezone.utc)
    is_longitudinal = bool(payload.pilot_wound_uuid)
    ttl_delta = timedelta(days=21) if is_longitudinal else timedelta(hours=72)
    expires_dt = now_dt + ttl_delta

    # Parseo de fecha personalizada
    taken_at_dt = None
    taken_at_display = "Foto"
    if payload.taken_at_custom:
        try:
            custom_dt = datetime.fromisoformat(payload.taken_at_custom.replace("Z", "+00:00"))
            taken_at_dt = custom_dt
            taken_at_display = custom_dt.strftime("%d %b %Y")
        except Exception:
            taken_at_display = payload.taken_at_custom[:10]
    elif payload.sequence_index is not None:
        taken_at_display = f"Foto {payload.sequence_index}"
    else:
        taken_at_display = now_dt.strftime("%d %b %Y")

    # Anti-IDOR y resolución de entidades en PostgreSQL
    pilot_case_id = None
    pilot_wound_id = None
    case_uuid_out = payload.pilot_case_uuid or str(uuid.uuid4())
    wound_uuid_out = payload.pilot_wound_uuid
    physician_id = None
    storage_key = None
    mask_storage_key = None

    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            if payload.pilot_case_uuid:
                try:
                    c_uuid = uuid.UUID(payload.pilot_case_uuid)
                except ValueError:
                    raise HTTPException(status_code=404, detail="Identificador de caso inválido.")

                case = db.query(PilotCase).filter(
                    PilotCase.pilot_case_uuid == c_uuid,
                    PilotCase.physician_id == physician_id
                ).first()

                if not case:
                    raise HTTPException(status_code=404, detail="Caso no encontrado o no pertenece al profesional.")

                pilot_case_id = case.id
                case_uuid_out = str(case.pilot_case_uuid)

                if payload.pilot_wound_uuid:
                    try:
                        w_uuid = uuid.UUID(payload.pilot_wound_uuid)
                    except ValueError:
                        raise HTTPException(status_code=404, detail="Identificador de herida inválido.")

                    wound = db.query(PilotWound).filter(
                        PilotWound.wound_uuid == w_uuid,
                        PilotWound.pilot_case_id == case.id
                    ).first()

                    if not wound:
                        raise HTTPException(status_code=404, detail="Herida no encontrada o no pertenece a este caso.")

                    pilot_wound_id = wound.id
                    wound_uuid_out = str(wound.wound_uuid)
            else:
                # Foto aislada: persistir caso contenedor privado
                iso_case = PilotCase(
                    pilot_case_uuid=uuid.uuid4(),
                    physician_id=physician_id,
                    case_alias=f"AISLADO-{uuid.uuid4().hex[:6].upper()}",
                    is_active=True
                )
                db.add(iso_case)
                db.flush()
                pilot_case_id = iso_case.id
                case_uuid_out = str(iso_case.pilot_case_uuid)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error resolviendo entidades en PostgreSQL: {e}")
            raise HTTPException(status_code=500, detail="Error de validación de base de datos.")

    # 2. Sanitización y subida a MinIO
    sanitized_bytes = sanitizar_y_reencodear_imagen_servidor(payload.imagen_base64)
    storage_key = save_image_bytes(sanitized_bytes, prefix="photos")

    analysis_uuid = uuid.uuid4()
    photo_uuid = uuid.uuid4()

    # 3. Quality Gate & Abstención (NO_EVALUABLE)
    if payload.quality_score < 48 or payload.quality_status == "insuficiente":
        duration_ms = int((time.time() - t_inicio) * 1000)

        if db is not None and pilot_case_id is not None:
            try:
                analysis_obj = PilotAnalysis(
                    pilot_case_id=pilot_case_id,
                    pilot_wound_id=pilot_wound_id,
                    physician_id=physician_id,
                    analysis_uuid=analysis_uuid,
                    photo_uuid=photo_uuid,
                    photo_storage_key=storage_key,
                    photo_mime_type="image/jpeg",
                    privacy_gate_confirmed=True,
                    quality_gate_score=payload.quality_score,
                    ai_status="NO_EVALUABLE",
                    classification_status="SKIPPED",
                    segmentation_status="SKIPPED",
                    scale_detected=payload.scale_detected,
                    processing_duration_ms=duration_ms,
                    taken_at_custom=taken_at_dt,
                    sequence_index=payload.sequence_index,
                    expires_at=expires_dt
                )
                db.add(analysis_obj)
                db.commit()
            except Exception as e:
                logger.error(f"Error persistiendo análisis no evaluable: {e}")
                db.rollback()

        return PilotAnalisisOutput(
            exito=True,
            analysis_uuid=str(analysis_uuid),
            pilot_case_uuid=case_uuid_out,
            pilot_wound_uuid=wound_uuid_out,
            photo_uuid=str(photo_uuid),
            ai_status="NO_EVALUABLE",
            classification_status="SKIPPED",
            segmentation_status="SKIPPED",
            quality_gate_score=payload.quality_score,
            quality_gate_status="insuficiente",
            classification_label=None,
            classification_confidence=None,
            scale_detected=payload.scale_detected,
            pixel_area=None,
            relative_area_percent=None,
            absolute_area_cm2=None,
            segmentation_mask_base64=None,
            shadow_mode_recorded=payload.shadow_mode is not None,
            concordance_pre_ai=None,
            processing_duration_ms=duration_ms,
            taken_at_display=taken_at_display,
            sequence_index=payload.sequence_index,
            is_longitudinal=is_longitudinal,
            created_at=now_dt.isoformat(),
            expires_at=expires_dt.isoformat(),
            mensaje="NO EVALUABLE: Calidad óptica insuficiente. Sugerimos mejorar la iluminación y reenfocar."
        )

    # 4. Inferencia de Clasificación (EfficientNet ONNX) — FAIL CLOSED
    clasif_label = None
    clasif_conf = None
    clasif_status = "AI_UNAVAILABLE"
    try:
        clasif_res = inferir_clasificador(payload.imagen_base64)
        if clasif_res and "es_ulcera" in clasif_res:
            clasif_label = "Abnormal(Ulcer)" if clasif_res["es_ulcera"] else "Normal(Healthy skin)"
            clasif_conf = round(float(clasif_res.get("confianza", 0.0)), 4)
            clasif_status = "COMPLETED"
    except FileNotFoundError:
        clasif_status = "AI_UNAVAILABLE"
    except Exception as e:
        logger.warning(f"Error en inferencia del clasificador ONNX: {e}")
        clasif_status = "AI_FAILED"

    # 5. Inferencia de Segmentación Técnica (U-Net Keras) — FAIL CLOSED
    seg_status = "AI_UNAVAILABLE"
    seg_px_area = None
    seg_rel_pct = None
    seg_abs_cm2 = None
    seg_mask_b64 = None
    mask_storage_key = None
    try:
        seg_payload = SegmentacionInput(
            imagen_base64=payload.imagen_base64,
            scale_detected=payload.scale_detected,
            px_per_cm=payload.px_per_cm
        )
        seg_res = predecir_segmentacion(seg_payload)
        seg_status = seg_res.ai_status
        seg_px_area = seg_res.pixel_area
        seg_rel_pct = seg_res.relative_area_percent
        seg_abs_cm2 = seg_res.absolute_area_cm2 if payload.scale_detected else None
        seg_mask_b64 = seg_res.mascara_base64
        if seg_mask_b64:
            try:
                mask_bytes = base64.b64decode(seg_mask_b64.split(",")[-1])
                mask_storage_key = save_image_bytes(mask_bytes, prefix="masks", content_type="image/png")
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error en inferencia de segmentación U-Net: {e}")
        seg_status = "AI_FAILED"

    # 6. Derivación de estado global honesto
    if clasif_status == "COMPLETED" and seg_status == "COMPLETED":
        overall_ai_status = "COMPLETED"
    elif clasif_status == "COMPLETED" or seg_status == "COMPLETED":
        overall_ai_status = "PARTIAL"
    elif clasif_status == "AI_FAILED" or seg_status == "AI_FAILED":
        overall_ai_status = "AI_FAILED"
    else:
        overall_ai_status = "AI_UNAVAILABLE"

    concordance = None
    if payload.shadow_mode and clasif_label is not None:
        pre_c = payload.shadow_mode.pre_classification
        concordance = (pre_c == clasif_label)

    duration_ms = int((time.time() - t_inicio) * 1000)

    # 7. Persistencia en PostgreSQL
    if db is not None and pilot_case_id is not None:
        try:
            analysis_obj = PilotAnalysis(
                pilot_case_id=pilot_case_id,
                pilot_wound_id=pilot_wound_id,
                physician_id=physician_id,
                analysis_uuid=analysis_uuid,
                photo_uuid=photo_uuid,
                photo_storage_key=storage_key,
                photo_mime_type="image/jpeg",
                privacy_gate_confirmed=True,
                quality_gate_score=payload.quality_score,
                ai_status=overall_ai_status,
                classification_status=clasif_status,
                segmentation_status=seg_status,
                model_name="EfficientNet-B0 + U-Net",
                model_version="1.0.0",
                classification_label=clasif_label,
                classification_confidence=clasif_conf,
                scale_detected=payload.scale_detected,
                pixel_area=seg_px_area,
                relative_area_percent=seg_rel_pct,
                absolute_area_cm2=seg_abs_cm2 if payload.scale_detected else None,
                segmentation_mask_key=mask_storage_key,
                shadow_mode_assessment=payload.shadow_mode.model_dump() if payload.shadow_mode else None,
                processing_duration_ms=duration_ms,
                taken_at_custom=taken_at_dt,
                sequence_index=payload.sequence_index,
                expires_at=expires_dt
            )
            db.add(analysis_obj)
            db.commit()
            db.refresh(analysis_obj)
        except Exception as e:
            logger.error(f"Error persistiendo análisis en PostgreSQL (compensación MinIO iniciada): {e}")
            db.rollback()
            if storage_key:
                delete_image_bytes(storage_key)
            if mask_storage_key:
                delete_image_bytes(mask_storage_key)
            raise HTTPException(status_code=500, detail="Error al almacenar el análisis en la base de datos.")

    return PilotAnalisisOutput(
        exito=True,
        analysis_uuid=str(analysis_uuid),
        pilot_case_uuid=case_uuid_out,
        pilot_wound_uuid=wound_uuid_out,
        photo_uuid=str(photo_uuid),
        ai_status=overall_ai_status,
        classification_status=clasif_status,
        segmentation_status=seg_status,
        quality_gate_score=payload.quality_score,
        quality_gate_status=payload.quality_status,
        classification_label=clasif_label,
        classification_confidence=clasif_conf,
        scale_detected=payload.scale_detected,
        pixel_area=seg_px_area,
        relative_area_percent=seg_rel_pct,
        absolute_area_cm2=seg_abs_cm2 if payload.scale_detected else None,
        segmentation_mask_base64=seg_mask_b64,
        shadow_mode_recorded=payload.shadow_mode is not None,
        concordance_pre_ai=concordance,
        processing_duration_ms=duration_ms,
        taken_at_display=taken_at_display,
        sequence_index=payload.sequence_index,
        is_longitudinal=is_longitudinal,
        created_at=now_dt.isoformat(),
        expires_at=expires_dt.isoformat(),
        mensaje="Análisis del piloto completado exitosamente."
    )


# ── ENDPOINTS DE TIMELINE Y FEEDBACK ──────────────────────────────────

@router_pilot.get("/cases/{pilot_case_uuid}/timeline", response_model=PilotCaseTimelineOutput)
def obtener_timeline_caso_piloto(
    pilot_case_uuid: str,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Retorna la línea de tiempo vertical de análisis para un caso del piloto.
    Anti-IDOR: Carga exclusivamente los datos de casos pertenecientes al médico autenticado.
    Orden de eventos:
    1. taken_at_custom si existe
    2. sequence_index si existe
    3. created_at
    """
    now_dt = datetime.now(timezone.utc)

    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            try:
                c_uuid = uuid.UUID(pilot_case_uuid)
            except ValueError:
                raise HTTPException(status_code=404, detail="Identificador de caso inválido.")

            case = db.query(PilotCase).filter(
                PilotCase.pilot_case_uuid == c_uuid,
                PilotCase.physician_id == physician_id
            ).first()

            if not case:
                raise HTTPException(status_code=404, detail="Caso no encontrado o no pertenece al profesional.")

            wounds = db.query(PilotWound).filter(
                PilotWound.pilot_case_id == case.id
            ).order_by(PilotWound.created_at).all()

            wound_groups = []
            for w in wounds:
                analyses = db.query(PilotAnalysis).filter(
                    PilotAnalysis.pilot_wound_id == w.id
                ).all()

                # Ordenamiento estricto: taken_at_custom > sequence_index > created_at
                def sort_key(a: PilotAnalysis):
                    t = a.taken_at_custom or datetime.min.replace(tzinfo=timezone.utc)
                    s = a.sequence_index or 0
                    c = a.created_at or datetime.min.replace(tzinfo=timezone.utc)
                    return (t, s, c)

                analyses_sorted = sorted(analyses, key=sort_key)
                events = []

                for idx, a in enumerate(analyses_sorted, start=1):
                    # Formateo honesto de fecha (nunca inventar fechas ausentes)
                    if a.taken_at_custom:
                        display_date = a.taken_at_custom.strftime("%d %b %Y")
                    elif a.sequence_index is not None:
                        display_date = f"Foto {a.sequence_index}"
                    elif len(analyses_sorted) > 1:
                        display_date = f"Foto {idx}"
                    else:
                        display_date = "Foto 1 (Inicial)"

                    fb = db.query(PilotFeedback).filter(PilotFeedback.analysis_id == a.id).first()

                    events.append(TimelineEventItem(
                        analysis_uuid=str(a.analysis_uuid),
                        photo_uuid=str(a.photo_uuid),
                        sequence_index=a.sequence_index or idx,
                        taken_at=a.taken_at_custom.isoformat() if a.taken_at_custom else None,
                        display_date=display_date,
                        quality_gate_score=a.quality_gate_score or 0,
                        quality_gate_status="optimo" if (a.quality_gate_score or 0) >= 48 else "insuficiente",
                        ai_status=a.ai_status,
                        classification_status=a.classification_status,
                        segmentation_status=a.segmentation_status,
                        classification_label=a.classification_label,
                        classification_confidence=float(a.classification_confidence) if a.classification_confidence is not None else None,
                        pixel_area=a.pixel_area,
                        relative_area_percent=float(a.relative_area_percent) if a.relative_area_percent is not None else None,
                        segmentation_mask_base64=None,
                        has_feedback=fb is not None,
                        feedback_rating=fb.segmentation_rating if fb else None
                    ))

                wound_groups.append(PilotWoundTimelineGroup(
                    wound_uuid=str(w.wound_uuid),
                    wound_label=w.wound_label,
                    wound_location=w.wound_location,
                    events=events
                ))

            return PilotCaseTimelineOutput(
                pilot_case_uuid=str(case.pilot_case_uuid),
                case_alias=case.case_alias or f"PILOT-{str(case.pilot_case_uuid)[:6].upper()}",
                created_at=case.created_at.isoformat(),
                wounds=wound_groups
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error consultando timeline en PostgreSQL: {e}")
            raise HTTPException(status_code=500, detail="Error consultando timeline.")

    # Fallback para pruebas aisladas
    return PilotCaseTimelineOutput(
        pilot_case_uuid=pilot_case_uuid,
        case_alias=f"PILOT-{pilot_case_uuid[:6].upper()}",
        created_at=now_dt.isoformat(),
        wounds=[]
    )


@router_pilot.get("/photos/{photo_uuid}")
def obtener_foto_clinica_piloto(
    photo_uuid: str,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Recupera los bytes de una fotografía clínica desde MinIO previa validación de propiedad (Anti-IDOR).
    Solo accesible para el profesional autenticado dueño del caso.
    """
    now_dt = datetime.now(timezone.utc)
    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            try:
                p_uuid = uuid.UUID(photo_uuid)
            except ValueError:
                raise HTTPException(status_code=404, detail="Identificador de fotografía inválido.")

            analysis = db.query(PilotAnalysis).filter(
                PilotAnalysis.photo_uuid == p_uuid,
                PilotAnalysis.physician_id == physician_id
            ).first()

            if not analysis:
                raise HTTPException(status_code=404, detail="Fotografía no encontrada o no autorizada.")

            if analysis.deleted_at is not None or (analysis.expires_at and analysis.expires_at < now_dt):
                raise HTTPException(status_code=410, detail="La fotografía ha expirado o ha sido purgada según la política de retención.")

            if not analysis.photo_storage_key:
                raise HTTPException(status_code=404, detail="Clave de almacenamiento no disponible.")

            image_bytes = get_image_bytes(analysis.photo_storage_key)
            if not image_bytes:
                raise HTTPException(status_code=404, detail="Objeto no encontrado en almacenamiento.")

            return Response(content=image_bytes, media_type=analysis.photo_mime_type or "image/jpeg")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error obteniendo fotografía clínica: {e}")
            raise HTTPException(status_code=500, detail="Error recuperando la imagen.")

    raise HTTPException(status_code=404, detail="Fotografía no disponible.")


@router_pilot.post("/feedback", response_model=PilotFeedbackOutput)
def registrar_feedback_piloto(
    payload: PilotFeedbackInput,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Registra el feedback del médico post-análisis:
    - Anti-IDOR: Vinculado a un análisis perteneciente al médico autenticado.
    - Sanitizado: Cero PII en comentarios.
    """
    if payload.comment:
        comentario_lower = payload.comment.lower()
        palabras_bloqueadas = ["dni", "paciente:", "nombre:", "tel:", "dr.", "dra."]
        for p in palabras_bloqueadas:
            if p in comentario_lower:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El comentario contiene posibles datos identificatorios. Por favor use solo apreciaciones técnicas de la IA."
                )

    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            a_uuid = uuid.UUID(payload.analysis_uuid)

            analysis = db.query(PilotAnalysis).filter(
                PilotAnalysis.analysis_uuid == a_uuid,
                PilotAnalysis.physician_id == physician_id
            ).first()

            if not analysis:
                raise HTTPException(status_code=404, detail="Análisis no encontrado o no pertenece al profesional.")

            fb = db.query(PilotFeedback).filter(PilotFeedback.analysis_id == analysis.id).first()
            if not fb:
                fb = PilotFeedback(
                    analysis_id=analysis.id,
                    physician_id=physician_id,
                    is_clinically_evaluable=payload.is_clinically_evaluable,
                    segmentation_rating=payload.segmentation_rating,
                    concordance_rating=payload.concordance_rating,
                    would_modify_classification=payload.would_modify_classification,
                    utility_score=payload.utility_score,
                    comment=payload.comment
                )
                db.add(fb)
            else:
                fb.is_clinically_evaluable = payload.is_clinically_evaluable
                fb.segmentation_rating = payload.segmentation_rating
                fb.concordance_rating = payload.concordance_rating
                fb.would_modify_classification = payload.would_modify_classification
                fb.utility_score = payload.utility_score
                fb.comment = payload.comment

            db.commit()
            db.refresh(fb)

            return PilotFeedbackOutput(
                exito=True,
                feedback_id=str(fb.id),
                analysis_uuid=payload.analysis_uuid,
                mensaje="Feedback registrado exitosamente. ¡Muchas gracias por participar del piloto!"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error registrando feedback: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Error registrando feedback.")

    return PilotFeedbackOutput(
        exito=True,
        feedback_id=str(uuid.uuid4()),
        analysis_uuid=payload.analysis_uuid,
        mensaje="Feedback registrado exitosamente."
    )


@router_pilot.post("/evolution-feedback", response_model=PilotEvolutionFeedbackOutput)
def registrar_feedback_evolucion(
    payload: PilotEvolutionFeedbackInput,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Registra la evaluación médica longitudinal comparativa entre dos análisis:
    - Anti-IDOR: Ambos análisis deben pertenecer al médico autenticado y a la MISMA herida.
    - Evolución: MEJOR | SIMILAR | PEOR (Juicio clínico médico, no derivado automáticamente de cm²).
    """
    if payload.clinical_evolution not in ("MEJOR", "SIMILAR", "PEOR"):
        raise HTTPException(status_code=400, detail="Evolución clínica debe ser MEJOR, SIMILAR o PEOR.")

    if payload.system_representation_agreement not in ("SI", "PARCIAL", "NO"):
        raise HTTPException(status_code=400, detail="Acuerdo de representación debe ser SI, PARCIAL o NO.")

    if payload.comment:
        comentario_lower = payload.comment.lower()
        palabras_bloqueadas = ["dni", "paciente:", "nombre:", "tel:", "dr.", "dra."]
        for p in palabras_bloqueadas:
            if p in comentario_lower:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El comentario contiene posibles datos identificatorios. Por favor use solo apreciaciones clínicas/técnicas."
                )

    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            base_uuid = uuid.UUID(payload.baseline_analysis_uuid)
            fol_uuid = uuid.UUID(payload.followup_analysis_uuid)

            base = db.query(PilotAnalysis).filter(
                PilotAnalysis.analysis_uuid == base_uuid,
                PilotAnalysis.physician_id == physician_id
            ).first()
            if not base:
                raise HTTPException(status_code=404, detail="Análisis baseline no encontrado o no pertenece al profesional.")

            fol = db.query(PilotAnalysis).filter(
                PilotAnalysis.analysis_uuid == fol_uuid,
                PilotAnalysis.physician_id == physician_id
            ).first()
            if not fol:
                raise HTTPException(status_code=404, detail="Análisis follow-up no encontrado o no pertenece al profesional.")

            if base.pilot_wound_id is None or base.pilot_wound_id != fol.pilot_wound_id:
                raise HTTPException(
                    status_code=400,
                    detail="Ambos análisis deben pertenecer a la misma herida clínica para registrar evaluación longitudinal."
                )

            evol = PilotEvolutionFeedback(
                baseline_analysis_id=base.id,
                followup_analysis_id=fol.id,
                physician_id=physician_id,
                clinical_evolution=payload.clinical_evolution,
                system_representation_agreement=payload.system_representation_agreement,
                comment=payload.comment
            )
            db.add(evol)
            db.commit()
            db.refresh(evol)

            return PilotEvolutionFeedbackOutput(
                exito=True,
                feedback_id=str(evol.id),
                mensaje="Evaluación longitudinal registrada exitosamente."
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error registrando feedback evolutivo: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Error registrando feedback de evolución.")

    return PilotEvolutionFeedbackOutput(
        exito=True,
        feedback_id=str(uuid.uuid4()),
        mensaje="Evaluación longitudinal registrada exitosamente."
    )


# ── ENDPOINTS DE REMOTE FOLLOW-UP (+4 DÍAS) ───────────────────────────

@router_pilot.post("/cases/{pilot_case_uuid}/wounds/{wound_uuid}/tokens", response_model=PilotTokenOutput)
def generar_token_seguimiento_remoto(
    pilot_case_uuid: str,
    wound_uuid: str,
    payload: Optional[PilotTokenCreateInput] = None,
    current_user: UserSession = Depends(require_authenticated),
    db: Optional[Session] = Depends(get_db)
):
    """
    Genera un token criptográfico Single-Use (de uso único) para solicitar fotografía remota de control al paciente (+4 días).
    Anti-IDOR: Valida que el caso y la herida pertenezcan al médico autenticado.
    Persiste ÚNICAMENTE el hash SHA-256 (nunca el token en claro).
    """
    due_days = payload.due_days if payload else 4
    expire_days = payload.expire_days if payload else 7

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    now_dt = datetime.now(timezone.utc)
    due_dt = now_dt + timedelta(days=due_days)
    expires_dt = now_dt + timedelta(days=expire_days)

    if db is not None:
        try:
            physician_id = uuid.UUID(str(current_user.user_id))
            c_uuid = uuid.UUID(pilot_case_uuid)
            w_uuid = uuid.UUID(wound_uuid)

            case = db.query(PilotCase).filter(
                PilotCase.pilot_case_uuid == c_uuid,
                PilotCase.physician_id == physician_id
            ).first()
            if not case:
                raise HTTPException(status_code=404, detail="Caso no encontrado o no pertenece al profesional.")

            wound = db.query(PilotWound).filter(
                PilotWound.wound_uuid == w_uuid,
                PilotWound.pilot_case_id == case.id
            ).first()
            if not wound:
                raise HTTPException(status_code=404, detail="Herida no encontrada o no pertenece a este caso.")

            token_obj = PilotUploadToken(
                token_hash=token_hash,
                pilot_case_id=case.id,
                pilot_wound_id=wound.id,
                physician_id=physician_id,
                due_at=due_dt,
                expires_at=expires_dt
            )
            db.add(token_obj)
            db.commit()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generando token de seguimiento en PostgreSQL: {e}")
            db.rollback()
            raise HTTPException(status_code=500, detail="Error al generar token de seguimiento.")

    return PilotTokenOutput(
        token=raw_token,
        url=f"/r/{raw_token}",
        due_at=due_dt.isoformat(),
        expires_at=expires_dt.isoformat()
    )


@router_pilot.get("/r/{raw_token}")
def validar_token_remoto_paciente(
    raw_token: str,
    db: Optional[Session] = Depends(get_db)
):
    """
    Valida un token remoto sin exponer identificadores de caso, herida ni médico.
    Verifica:
    - Existencia del hash SHA-256 en PostgreSQL.
    - used_at IS NULL (Single-use).
    - revoked_at IS NULL.
    - expires_at > now.
    """
    if len(raw_token) < 16:
        raise HTTPException(status_code=404, detail="Enlace no válido, expirado o ya utilizado.")

    token_hash = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
    now_dt = datetime.now(timezone.utc)

    if db is not None:
        try:
            token_obj = db.query(PilotUploadToken).filter(
                PilotUploadToken.token_hash == token_hash
            ).first()

            if (
                not token_obj
                or token_obj.used_at is not None
                or token_obj.revoked_at is not None
                or token_obj.expires_at < now_dt
            ):
                raise HTTPException(status_code=404, detail="Enlace no válido, expirado o ya utilizado.")

            return {
                "valid": True,
                "due_date": token_obj.due_at.strftime("%d %b %Y"),
                "mensaje": "Su profesional solicitó una nueva fotografía de seguimiento de su herida."
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validando token remoto: {e}")
            raise HTTPException(status_code=404, detail="Enlace no válido, expirado o ya utilizado.")

    return {
        "valid": True,
        "due_date": (now_dt + timedelta(days=4)).strftime("%d %b %Y"),
        "mensaje": "Su profesional solicitó una nueva fotografía de seguimiento de su herida."
    }


@router_pilot.post("/r/{raw_token}/upload", response_model=PilotPatientUploadOutput)
def subir_foto_remota_paciente(
    raw_token: str,
    payload: PilotPatientUploadInput,
    db: Optional[Session] = Depends(get_db)
):
    """
    Carga de fotografía de seguimiento desde el celular del paciente con consumo atómico:
    1. SHA-256 del token provisto.
    2. Transacción en base de datos con SELECT ... FOR UPDATE.
    3. Valida: exists, used_at IS NULL, revoked_at IS NULL, expires_at > now.
    4. Valida Privacy Gate confirmado.
    5. Sanitiza y re-encodea imagen server-side.
    6. Evalúa Quality Gate (<48: retorna retry_allowed=True sin consumir el token).
    7. Asocia en servidor exclusivamente a PilotUploadToken (case, wound, physician).
    8. Sube imagen a MinIO bajo clave opaca UUID.
    9. Ejecuta inferencia U-Net fail-closed.
    10. Persiste PilotAnalysis (retención 21 días) y marca token.used_at = now de forma atómica.
    11. Replay bloqueado: segundo intento con el mismo token es rechazado con 404.
    """
    if len(raw_token) < 16:
        raise HTTPException(status_code=404, detail="Enlace no válido, expirado o ya utilizado.")

    if not payload.privacy_gate_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Debe confirmar la certificación de privacidad antes de enviar."
        )

    token_hash = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
    now_dt = datetime.now(timezone.utc)

    # 1. Sanitización de imagen
    sanitized_bytes = sanitizar_y_reencodear_imagen_servidor(payload.imagen_base64)

    # 2. Quality Gate: Si no supera el umbral, permitir reintento SIN consumir el token
    if payload.quality_score < 48:
        return PilotPatientUploadOutput(
            exito=False,
            retry_allowed=True,
            analysis_uuid=None,
            mensaje="La fotografía no tiene suficiente calidad. Por favor vuelva a tomarla con mejor iluminación y enfoque."
        )

    # 3. Transacción atómica con SELECT FOR UPDATE
    storage_key = None
    mask_storage_key = None

    if db is not None:
        try:
            token_obj = db.query(PilotUploadToken).filter(
                PilotUploadToken.token_hash == token_hash
            ).with_for_update().first()

            if (
                not token_obj
                or token_obj.used_at is not None
                or token_obj.revoked_at is not None
                or token_obj.expires_at < now_dt
            ):
                raise HTTPException(status_code=404, detail="Enlace no válido, expirado o ya utilizado.")

            # Subir a MinIO
            storage_key = save_image_bytes(sanitized_bytes, prefix="patient_photos")

            # Inferencia de segmentación U-Net
            seg_status = "AI_UNAVAILABLE"
            seg_px_area = None
            seg_rel_pct = None
            mask_storage_key = None
            try:
                seg_res = predecir_segmentacion(SegmentacionInput(
                    imagen_base64=payload.imagen_base64,
                    scale_detected=False
                ))
                seg_status = seg_res.ai_status
                seg_px_area = seg_res.pixel_area
                seg_rel_pct = seg_res.relative_area_percent
                if seg_res.mascara_base64:
                    try:
                        m_bytes = base64.b64decode(seg_res.mascara_base64.split(",")[-1])
                        mask_storage_key = save_image_bytes(m_bytes, prefix="patient_masks", content_type="image/png")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Error en inferencia remota U-Net: {e}")
                seg_status = "AI_FAILED"

            overall_ai = "PARTIAL" if seg_status == "COMPLETED" else "AI_UNAVAILABLE"

            analysis_uuid = uuid.uuid4()
            photo_uuid = uuid.uuid4()

            analysis_obj = PilotAnalysis(
                pilot_case_id=token_obj.pilot_case_id,
                pilot_wound_id=token_obj.pilot_wound_id,
                physician_id=token_obj.physician_id,
                analysis_uuid=analysis_uuid,
                photo_uuid=photo_uuid,
                photo_storage_key=storage_key,
                photo_mime_type="image/jpeg",
                privacy_gate_confirmed=True,
                quality_gate_score=payload.quality_score,
                ai_status=overall_ai,
                classification_status="SKIPPED",
                segmentation_status=seg_status,
                model_name="EfficientNet-B0 + U-Net",
                model_version="1.0.0",
                classification_label=None,
                classification_confidence=None,
                scale_detected=False,
                pixel_area=seg_px_area,
                relative_area_percent=seg_rel_pct,
                absolute_area_cm2=None, # Estrictamente None
                segmentation_mask_key=mask_storage_key,
                taken_at_custom=now_dt,
                expires_at=now_dt + timedelta(days=21) # 21 días de retención desde la ingesta
            )

            # Consumir el token atómicamente
            token_obj.used_at = now_dt

            db.add(analysis_obj)
            db.commit()

            return PilotPatientUploadOutput(
                exito=True,
                retry_allowed=False,
                analysis_uuid=str(analysis_uuid),
                mensaje="✓ FOTO RECIBIDA: La fotografía fue enviada exitosamente para revisión profesional."
            )
        except HTTPException:
            db.rollback()
            if storage_key:
                delete_image_bytes(storage_key)
            if mask_storage_key:
                delete_image_bytes(mask_storage_key)
            raise
        except Exception as e:
            logger.error(f"Error procesando subida remota (compensación MinIO iniciada): {e}")
            db.rollback()
            if storage_key:
                delete_image_bytes(storage_key)
            if mask_storage_key:
                delete_image_bytes(mask_storage_key)
            raise HTTPException(status_code=500, detail="Error procesando la fotografía remota.")

    # Fallback sin DB
    return PilotPatientUploadOutput(
        exito=True,
        retry_allowed=False,
        analysis_uuid=str(uuid.uuid4()),
        mensaje="✓ FOTO RECIBIDA: La fotografía fue enviada exitosamente para revisión profesional."
    )


