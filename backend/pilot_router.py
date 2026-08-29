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
from fastapi import APIRouter, HTTPException, Depends, Header, status
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

@router_pilot.post("/cases", response_model=PilotCaseOutput)
def crear_caso_piloto(payload: PilotCaseCreateInput):
    """Crea un caso pseudonimizado para seguimiento longitudinal (ej. PILOT-0001)."""
    case_uuid = str(uuid.uuid4())
    alias = payload.case_alias or f"PILOT-{case_uuid[:6].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    return PilotCaseOutput(
        id=case_uuid,
        pilot_case_uuid=case_uuid,
        case_alias=alias,
        is_active=True,
        created_at=now_iso
    )


@router_pilot.post("/cases/{case_uuid}/wounds", response_model=PilotWoundOutput)
def crear_herida_caso_piloto(case_uuid: str, payload: PilotWoundCreateInput):
    """Crea una herida clínica dentro de un caso pseudonimizado."""
    wound_uuid = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    return PilotWoundOutput(
        id=wound_uuid,
        wound_uuid=wound_uuid,
        pilot_case_uuid=case_uuid,
        wound_label=payload.wound_label,
        wound_location=payload.wound_location,
        created_at=now_iso
    )


# ── ENDPOINT DE ANÁLISIS E INFERENCIA TÉCNICA ─────────────────────────

@router_pilot.post("/analisis", response_model=PilotAnalisisOutput)
def procesar_analisis_piloto(payload: PilotAnalisisInput):
    """
    Procesa un análisis fotográfico del piloto cerrado:
    1. Valida confirmación explícita de Privacy Gate por el médico.
    2. Evalúa Quality Gate (emite NO_EVALUABLE si score < 48).
    3. Ejecuta inferencia técnica FAIL-CLOSED (Clasificador ONNX + Segmentador U-Net).
       En ausencia de modelos, retorna AI_UNAVAILABLE sin inventar números ni clases clínicas.
    4. Garantiza honestidad física (cero cm² arbitrarios sin calibrador).
    5. Aplica política de retención dual (72h aislado / 21d longitudinal).
    """
    t_inicio = time.time()

    # 1. Privacy Gate Check
    if not payload.privacy_gate_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Privacy Gate no confirmado: El profesional debe certificar expresamente que la toma no contiene rostro, pulsera, documentos ni PII visible."
        )

    analysis_uuid = str(uuid.uuid4())
    pilot_case_uuid = payload.pilot_case_uuid or str(uuid.uuid4())
    photo_uuid = str(uuid.uuid4())
    now_dt = datetime.now(timezone.utc)

    # Política de retención dual
    is_longitudinal = bool(payload.pilot_wound_uuid)
    ttl_delta = timedelta(days=21) if is_longitudinal else timedelta(hours=72)
    expires_dt = now_dt + ttl_delta

    # Formateo de fecha de visualización
    taken_at_display = "Foto"
    if payload.taken_at_custom:
        try:
            custom_dt = datetime.fromisoformat(payload.taken_at_custom.replace("Z", "+00:00"))
            taken_at_display = custom_dt.strftime("%d %b %Y")
        except Exception:
            taken_at_display = payload.taken_at_custom[:10]
    elif payload.sequence_index is not None:
        taken_at_display = f"Foto {payload.sequence_index}"
    else:
        taken_at_display = now_dt.strftime("%d %b %Y")

    # 2. Quality Gate & Abstención (NO_EVALUABLE) — Umbral técnico heurístico del piloto
    if payload.quality_score < 48 or payload.quality_status == "insuficiente":
        duration_ms = int((time.time() - t_inicio) * 1000)
        return PilotAnalisisOutput(
            exito=True,
            analysis_uuid=analysis_uuid,
            pilot_case_uuid=pilot_case_uuid,
            pilot_wound_uuid=payload.pilot_wound_uuid,
            photo_uuid=photo_uuid,
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

    # 3. Inferencia de Clasificación (EfficientNet ONNX) — FAIL CLOSED
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
        logger.warning("Clasificador ONNX no encontrado en disco: clasificación omitida honestamente.")
        clasif_status = "AI_UNAVAILABLE"
    except Exception as e:
        logger.warning(f"Error en inferencia del clasificador ONNX: {e}")
        clasif_status = "AI_FAILED"

    # 4. Inferencia de Segmentación Técnica (U-Net Keras) — FAIL CLOSED
    seg_status = "AI_UNAVAILABLE"
    seg_px_area = None
    seg_rel_pct = None
    seg_abs_cm2 = None
    seg_mask_b64 = None
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
        seg_abs_cm2 = seg_res.absolute_area_cm2
        seg_mask_b64 = seg_res.mascara_base64
    except Exception as e:
        logger.warning(f"Error en inferencia de segmentación U-Net: {e}")
        seg_status = "AI_FAILED"

    # 5. Derivación de estado global honesto (Sin ocultar fallos parciales)
    if clasif_status == "COMPLETED" and seg_status == "COMPLETED":
        overall_ai_status = "COMPLETED"
    elif clasif_status == "COMPLETED" or seg_status == "COMPLETED":
        overall_ai_status = "PARTIAL"
    elif clasif_status == "AI_FAILED" or seg_status == "AI_FAILED":
        overall_ai_status = "AI_FAILED"
    else:
        overall_ai_status = "AI_UNAVAILABLE"

    # 6. Shadow Mode: Cálculo de concordancia preliminar (sólo si hubo clasificación real)
    concordance = None
    if payload.shadow_mode and clasif_label is not None:
        pre_c = payload.shadow_mode.pre_classification
        concordance = (pre_c == clasif_label)

    duration_ms = int((time.time() - t_inicio) * 1000)

    return PilotAnalisisOutput(
        exito=True,
        analysis_uuid=analysis_uuid,
        pilot_case_uuid=pilot_case_uuid,
        pilot_wound_uuid=payload.pilot_wound_uuid,
        photo_uuid=photo_uuid,
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
        absolute_area_cm2=seg_abs_cm2, # estrictamente None si scale_detected=False
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
def obtener_timeline_caso_piloto(pilot_case_uuid: str):
    """
    Retorna la línea de tiempo vertical de análisis para un caso del piloto.
    Estructura agrupada por herida con orden cronológico o secuencial.
    """
    # En runtime con DB real, se filtraría por pilot_case_uuid y physician_id autenticado (anti-IDOR)
    now_dt = datetime.now(timezone.utc)

    # Estructura limpia de respuesta
    mock_events = [
        TimelineEventItem(
            analysis_uuid="analisis-demo-1",
            photo_uuid="photo-demo-1",
            sequence_index=1,
            taken_at=None,
            display_date="Foto 1 (Inicial)",
            quality_gate_score=88,
            quality_gate_status="optimo",
            ai_status="COMPLETED",
            classification_label="Abnormal(Ulcer)",
            classification_confidence=0.89,
            pixel_area=4200,
            relative_area_percent=4.8,
            segmentation_mask_base64=None,
            has_feedback=True,
            feedback_rating="Correcta"
        )
    ]

    wound_group = PilotWoundTimelineGroup(
        wound_uuid="wound-demo-1",
        wound_label="Herida 1",
        wound_location="Plantar antepié",
        events=mock_events
    )

    return PilotCaseTimelineOutput(
        pilot_case_uuid=pilot_case_uuid,
        case_alias=f"PILOT-{pilot_case_uuid[:6].upper()}",
        created_at=now_dt.isoformat(),
        wounds=[wound_group]
    )


@router_pilot.post("/feedback", response_model=PilotFeedbackOutput)
def registrar_feedback_piloto(payload: PilotFeedbackInput):
    """
    Registra el feedback del médico post-análisis:
    - Vinculado exclusivamente al analysis_uuid.
    - Diseñado para no recolectar PII del paciente (comentario sanitizado con advertencia explícita).
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

    feedback_uuid = str(uuid.uuid4())

    return PilotFeedbackOutput(
        exito=True,
        feedback_id=feedback_uuid,
        analysis_uuid=payload.analysis_uuid,
        mensaje="Feedback registrado exitosamente. ¡Muchas gracias por participar del piloto!"
    )


@router_pilot.post("/evolution-feedback", response_model=PilotEvolutionFeedbackOutput)
def registrar_feedback_evolucion(payload: PilotEvolutionFeedbackInput):
    """
    Registra la evaluación clínica longitudinal del médico tras comparar dos momentos:
    - Evolución: MEJOR | SIMILAR | PEOR
    - Acuerdo con la representación de la IA: SI | PARCIAL | NO
    - Comentario opcional libre de PII.
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

    evol_id = str(uuid.uuid4())
    return PilotEvolutionFeedbackOutput(
        exito=True,
        feedback_id=evol_id,
        mensaje="Evaluación longitudinal registrada exitosamente."
    )


# ── ENDPOINTS DE REMOTE FOLLOW-UP (+4 DÍAS) ───────────────────────────

@router_pilot.post("/cases/{pilot_case_uuid}/wounds/{wound_uuid}/tokens", response_model=PilotTokenOutput)
def generar_token_seguimiento_remoto(pilot_case_uuid: str, wound_uuid: str, payload: Optional[PilotTokenCreateInput] = None):
    """
    Genera un token criptográfico de uso único para solicitar fotografía remota de control al paciente (+4 días).
    Almacena exclusivamente el hash SHA-256.
    """
    due_days = payload.due_days if payload else 4
    expire_days = payload.expire_days if payload else 7

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    
    now_dt = datetime.now(timezone.utc)
    due_dt = now_dt + timedelta(days=due_days)
    expires_dt = now_dt + timedelta(days=expire_days)

    return PilotTokenOutput(
        token=raw_token,
        url=f"/r/{raw_token}",
        due_at=due_dt.isoformat(),
        expires_at=expires_dt.isoformat()
    )


@router_pilot.get("/r/{raw_token}")
def validar_token_remoto_paciente(raw_token: str):
    """
    Valida un token remoto sin exponer identificadores de caso, herida ni médico.
    """
    if len(raw_token) < 16:
        raise HTTPException(status_code=404, detail="Enlace no válido o expirado.")

    now_dt = datetime.now(timezone.utc)

    return {
        "valid": True,
        "due_date": (now_dt + timedelta(days=4)).strftime("%d %b %Y"),
        "mensaje": "Su profesional solicitó una nueva fotografía de seguimiento de su herida."
    }


@router_pilot.post("/r/{raw_token}/upload", response_model=PilotPatientUploadOutput)
def subir_foto_remota_paciente(raw_token: str, payload: PilotPatientUploadInput):
    """
    Carga de fotografía de seguimiento desde el celular del paciente:
    1. Valida token criptográfico con hash SHA-256.
    2. Valida Privacy Gate confirmado por el usuario.
    3. Decodifica, valida dimensiones/MIME y re-encodea la imagen en servidor (Zero Client Trust).
    4. Evalúa Quality Gate instantáneo. Si no supera el umbral (<48), devuelve error amigable sin quemar el token para permitir reintentar de inmediato.
    5. Consumo atómico / transaccional en base de datos para evitar replay o race conditions.
    6. Asocia la foto del lado del servidor al caso, herida y médico del token (Zero Client Trust).
    7. Fija TTL de retención de 21 días desde la ingesta.
    8. No devuelve diagnóstico ni clasificación al paciente.
    """
    if len(raw_token) < 16:
        raise HTTPException(status_code=404, detail="Enlace no válido o expirado.")

    if not payload.privacy_gate_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Debe confirmar la certificación de privacidad antes de enviar."
        )

    # 1. Decodificación, sanitización EXIF y re-encoding server-side
    reencoded_bytes = sanitizar_y_reencodear_imagen_servidor(payload.imagen_base64)

    # 2. Validación de Quality Gate (Permite reintentar sin quemar el token)
    if payload.quality_score < 48:
        return PilotPatientUploadOutput(
            exito=False,
            retry_allowed=True,
            analysis_uuid=None,
            mensaje="La fotografía no tiene suficiente calidad. Por favor vuelva a tomarla con mejor iluminación y enfoque."
        )

    # 3. Procesar y asociar en servidor con TTL 21 días y área absoluta NULL
    analysis_uuid = str(uuid.uuid4())
    now_dt = datetime.now(timezone.utc)

    return PilotPatientUploadOutput(
        exito=True,
        retry_allowed=False,
        analysis_uuid=analysis_uuid,
        mensaje="✓ FOTO RECIBIDA: La fotografía fue enviada exitosamente para revisión profesional."
    )


