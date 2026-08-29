"""
PIEDIABETICO.LAT — Modelos SQLAlchemy v0.1
PostgreSQL 16 + pgvector

Uso:
    from models import Base, Organization, User, Patient, ...
    
    # Crear todas las tablas (vía Alembic):
    alembic upgrade head
    
    # O directamente en desarrollo:
    Base.metadata.create_all(engine)
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer,
    Numeric, SmallInteger, String, Text, UniqueConstraint,
    CheckConstraint, Index, event
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# pgvector — instalar con: pip install pgvector
try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False
    Vector = None


# ─────────────────────────────────────────────────────────────
# BASE
# ─────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────
# DOMINIO 1: ORGANIZACIONES Y USUARIOS
# ─────────────────────────────────────────────────────────────

class Organization(Base):
    """
    Institución médica o equipo clínico.
    Toda entidad clínica está asociada a una organización.
    El aislamiento entre organizaciones se aplica en la capa API.
    """
    __tablename__ = "organizations"

    id         : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name       : Mapped[str]       = mapped_column(String(200), nullable=False)
    slug       : Mapped[str]       = mapped_column(String(100), unique=True, nullable=False)
    country    : Mapped[str]       = mapped_column(String(2), nullable=False, default='AR')
    plan       : Mapped[str]       = mapped_column(String(20), nullable=False, default='free')
    active     : Mapped[bool]      = mapped_column(Boolean, nullable=False, default=True)
    created_at : Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at : Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("plan IN ('free','pro','institution')", name="ck_org_plan"),
    )

    # Relaciones
    users    : Mapped[List["User"]]    = relationship("User", back_populates="organization")
    patients : Mapped[List["Patient"]] = relationship("Patient", back_populates="organization")


class User(Base):
    """
    Profesional de salud con acceso al sistema.
    Cada usuario pertenece estrictamente a una organización.
    """
    __tablename__ = "users"

    id              : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    email           : Mapped[str]              = mapped_column(String(255), unique=True, nullable=False)
    password_hash   : Mapped[str]              = mapped_column(String(255), nullable=False)
    full_name       : Mapped[str]              = mapped_column(String(200), nullable=False)
    role            : Mapped[str]              = mapped_column(String(30), nullable=False)
    is_active       : Mapped[bool]             = mapped_column(Boolean, nullable=False, default=True)
    pilot_enabled   : Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    last_login_at   : Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at      : Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at      : Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','medico_general','infectologo','diabetologo','cirujano_vascular','podologo','enfermero','profesional','universitario','investigador','paciente','cuidador')",
            name="ck_user_role"
        ),
        Index("idx_users_org", "organization_id"),
    )

    # Relaciones
    organization : Mapped["Organization"] = relationship("Organization", back_populates="users")


# ─────────────────────────────────────────────────────────────
# DOMINIO 2: PACIENTES
# ─────────────────────────────────────────────────────────────

class Patient(Base):
    """
    Paciente con diabetes.
    Los identificadores (MRN) están separados de los datos clínicos
    para facilitar la desidentificación en investigación.
    """
    __tablename__ = "patients"

    id              : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    created_by      : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Identificador institucional (separado del historial)
    mrn             : Mapped[Optional[str]]  = mapped_column(String(50))
    # Datos demográficos mínimos
    birth_year      : Mapped[Optional[int]]  = mapped_column(SmallInteger)
    sex             : Mapped[Optional[str]]  = mapped_column(String(1))
    country         : Mapped[str]            = mapped_column(String(2), default='AR')
    # Datos clínicos base
    diabetes_type   : Mapped[Optional[str]]  = mapped_column(String(10))
    diagnosis_year  : Mapped[Optional[int]]  = mapped_column(SmallInteger)
    is_active       : Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    created_at      : Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at      : Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("birth_year BETWEEN 1900 AND 2025", name="ck_patient_birth_year"),
        CheckConstraint("sex IN ('M','F','X')", name="ck_patient_sex"),
        CheckConstraint("diabetes_type IN ('T1','T2','MODY','otro')", name="ck_patient_diabetes_type"),
        Index("idx_patients_org", "organization_id"),
    )

    # Relaciones
    organization  : Mapped["Organization"]        = relationship("Organization", back_populates="patients")
    assessments   : Mapped[List["FootAssessment"]] = relationship("FootAssessment", back_populates="patient")
    wounds        : Mapped[List["Wound"]]          = relationship("Wound", back_populates="patient")
    reports       : Mapped[List["GeneratedReport"]] = relationship("GeneratedReport", back_populates="patient")


# ─────────────────────────────────────────────────────────────
# DOMINIO 3: EVALUACIONES CLÍNICAS DEL PIE
# ─────────────────────────────────────────────────────────────

class FootAssessment(Base):
    """
    Examen físico completo del pie.
    Incluye neuropatía (monofilamento), vascular (pulsos/ITB),
    metabólico (HbA1c, creatinina) y resultado IWGDF calculado.
    
    El campo iwgdf_risk_group es calculado por el Agente 8.
    Se almacena como referencia educativa con disclaimer clínico.
    """
    __tablename__ = "foot_assessments"

    id              : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id      : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    assessed_by     : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assessed_at     : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Neuropatía sensitiva protectora
    monofilament_right : Mapped[Optional[int]] = mapped_column(SmallInteger)
    monofilament_left  : Mapped[Optional[int]] = mapped_column(SmallInteger)
    # Vascular
    pulse_right_pedio  : Mapped[Optional[bool]] = mapped_column(Boolean)
    pulse_right_tibial : Mapped[Optional[bool]] = mapped_column(Boolean)
    pulse_left_pedio   : Mapped[Optional[bool]] = mapped_column(Boolean)
    pulse_left_tibial  : Mapped[Optional[bool]] = mapped_column(Boolean)
    itb_right          : Mapped[Optional[float]] = mapped_column(Numeric(4, 2))
    itb_left           : Mapped[Optional[float]] = mapped_column(Numeric(4, 2))
    # Deformidades
    deformity_present  : Mapped[bool]           = mapped_column(Boolean, default=False)
    deformity_notes    : Mapped[Optional[str]]  = mapped_column(Text)
    # Antecedentes
    prev_ulcer         : Mapped[bool]           = mapped_column(Boolean, default=False)
    prev_amputation    : Mapped[bool]           = mapped_column(Boolean, default=False)
    charcot_active     : Mapped[bool]           = mapped_column(Boolean, default=False)
    # Metabólico
    hba1c              : Mapped[Optional[float]] = mapped_column(Numeric(4, 1))
    creatinine         : Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    egfr               : Mapped[Optional[float]] = mapped_column(Numeric(6, 1))
    # Resultado IWGDF (Agente 8 — referencia educativa)
    iwgdf_risk_group     : Mapped[Optional[int]]  = mapped_column(SmallInteger)
    iwgdf_followup_months: Mapped[Optional[int]]  = mapped_column(SmallInteger)
    # Notas
    notes              : Mapped[Optional[str]]   = mapped_column(Text)
    created_at         : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("monofilament_right BETWEEN 0 AND 10", name="ck_mono_right"),
        CheckConstraint("monofilament_left BETWEEN 0 AND 10",  name="ck_mono_left"),
        CheckConstraint("iwgdf_risk_group BETWEEN 0 AND 3",    name="ck_iwgdf_group"),
        Index("idx_assessments_patient", "patient_id"),
        Index("idx_assessments_date",    "assessed_at"),
    )

    patient : Mapped["Patient"] = relationship("Patient", back_populates="assessments")


# ─────────────────────────────────────────────────────────────
# DOMINIO 4: HERIDAS
# ─────────────────────────────────────────────────────────────

class Wound(Base):
    """
    Úlcera de pie diabético activa o cerrada.
    Una herida puede tener múltiples evaluaciones y fotos a lo largo del tiempo.
    """
    __tablename__ = "wounds"

    id           : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id   : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False)
    created_by   : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    foot_side    : Mapped[str]             = mapped_column(String(1), nullable=False)
    location     : Mapped[str]             = mapped_column(String(50), nullable=False)
    location_notes: Mapped[Optional[str]] = mapped_column(Text)
    etiology     : Mapped[Optional[str]]  = mapped_column(String(30))
    status       : Mapped[str]            = mapped_column(String(20), nullable=False, default='activa')
    first_seen_at: Mapped[date]           = mapped_column(Date, nullable=False, server_default=func.current_date())
    closed_at    : Mapped[Optional[date]] = mapped_column(Date)
    wagner_grade : Mapped[Optional[int]]  = mapped_column(SmallInteger)
    texas_grade  : Mapped[Optional[str]]  = mapped_column(String(4))
    notes        : Mapped[Optional[str]]  = mapped_column(Text)
    created_at   : Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at   : Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("foot_side IN ('D','I')", name="ck_wound_foot_side"),
        CheckConstraint("status IN ('activa','cicatrizada','amputada','cerrada_alta')", name="ck_wound_status"),
        CheckConstraint("wagner_grade BETWEEN 0 AND 5", name="ck_wagner_grade"),
        Index("idx_wounds_patient", "patient_id"),
        Index("idx_wounds_status",  "status"),
    )

    patient     : Mapped["Patient"]              = relationship("Patient", back_populates="wounds")
    evaluations : Mapped[List["WoundEvaluation"]] = relationship("WoundEvaluation", back_populates="wound")
    images      : Mapped[List["WoundImage"]]      = relationship("WoundImage", back_populates="wound")


# ─────────────────────────────────────────────────────────────
# DOMINIO 5: EVALUACIONES DE HERIDA (TIMERS)
# ─────────────────────────────────────────────────────────────

class WoundEvaluation(Base):
    """
    Evaluación clínica de la herida en un momento dado.
    Implementa la escala TIMERS: Tejido, Infección, Moisture (humedad), Edge (bordes).
    
    Las sugerencias de apósitos son referencia educativa del Agente 9.
    Incluyen disclaimer clínico obligatorio.
    """
    __tablename__ = "wound_evaluations"

    id                  : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wound_id            : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("wounds.id", ondelete="RESTRICT"), nullable=False)
    evaluated_by        : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    evaluated_at        : Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    # T — Tejido
    tissue_necrotic     : Mapped[bool]           = mapped_column(Boolean, default=False)
    tissue_notes        : Mapped[Optional[str]]  = mapped_column(Text)
    # I — Infección / Inflamación
    infection_present   : Mapped[bool]           = mapped_column(Boolean, default=False)
    infection_signs     : Mapped[Optional[str]]  = mapped_column(Text)
    # M — Moisture / Humedad
    moisture_high       : Mapped[bool]           = mapped_column(Boolean, default=False)
    exudate_amount      : Mapped[Optional[str]]  = mapped_column(String(10))
    exudate_type        : Mapped[Optional[str]]  = mapped_column(String(20))
    # E — Edge / Bordes
    edge_stalled        : Mapped[bool]           = mapped_column(Boolean, default=False)
    edge_notes          : Mapped[Optional[str]]  = mapped_column(Text)
    # Resultado Agente 9 (referencia educativa con disclaimer)
    timers_dressing_suggestion : Mapped[Optional[str]] = mapped_column(Text)
    timers_debridement         : Mapped[Optional[str]] = mapped_column(Text)
    timers_frequency           : Mapped[Optional[str]] = mapped_column(String(100))
    timers_disclaimer          : Mapped[str]           = mapped_column(
        Text, nullable=False,
        default='Sugerencia educativa basada en guías TIMERS. No reemplaza el criterio clínico del profesional.'
    )
    # Notas libres (puede ser dictado por voz)
    clinical_notes      : Mapped[Optional[str]]  = mapped_column(Text)
    created_at          : Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("exudate_amount IN ('ninguno','escaso','moderado','abundante')", name="ck_exudate_amount"),
        CheckConstraint("exudate_type IN ('seroso','serosanguinolento','purulento','necrotico')", name="ck_exudate_type"),
        Index("idx_wound_evals_wound", "wound_id"),
        Index("idx_wound_evals_date",  "evaluated_at"),
    )

    wound  : Mapped["Wound"]           = relationship("Wound", back_populates="evaluations")
    images : Mapped[List["WoundImage"]] = relationship("WoundImage", back_populates="wound_evaluation")


# ─────────────────────────────────────────────────────────────
# DOMINIO 6: IMÁGENES
# ─────────────────────────────────────────────────────────────

class WoundImage(Base):
    """
    Fotografía de la herida almacenada en MinIO.
    
    La imagen original es INMUTABLE — nunca se sobreescribe.
    El hash SHA256 garantiza integridad.
    El control de calidad (QC) determina si la imagen es válida para IA.
    """
    __tablename__ = "wound_images"

    id                   : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wound_id             : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("wounds.id", ondelete="RESTRICT"), nullable=False)
    wound_evaluation_id  : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("wound_evaluations.id"))
    uploaded_by          : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # Almacenamiento MinIO
    storage_bucket       : Mapped[str]             = mapped_column(String(100), nullable=False)
    storage_key          : Mapped[str]             = mapped_column(String(500), nullable=False)
    file_hash_sha256     : Mapped[str]             = mapped_column(String(64), nullable=False)
    file_size_bytes      : Mapped[Optional[int]]   = mapped_column(Integer)
    mime_type            : Mapped[str]             = mapped_column(String(50), default='image/jpeg')
    # Metadatos de captura
    device_type          : Mapped[Optional[str]]   = mapped_column(String(50))
    capture_method       : Mapped[str]             = mapped_column(String(20), default='camera')
    # Control de calidad
    qc_blur_score        : Mapped[Optional[float]] = mapped_column(Numeric(5, 3))
    qc_exposure_ok       : Mapped[Optional[bool]]  = mapped_column(Boolean)
    qc_scale_detected    : Mapped[bool]            = mapped_column(Boolean, default=False)
    qc_scale_px_per_mm   : Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    qc_passed            : Mapped[bool]            = mapped_column(Boolean, default=False)
    qc_rejection_reason  : Mapped[Optional[str]]   = mapped_column(String(100))
    # Orientación
    foot_side            : Mapped[Optional[str]]   = mapped_column(String(1))
    capture_angle        : Mapped[Optional[str]]   = mapped_column(String(20))
    is_primary           : Mapped[bool]            = mapped_column(Boolean, default=False)
    taken_at             : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at           : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("capture_method IN ('camera','gallery','upload')", name="ck_capture_method"),
        CheckConstraint("foot_side IN ('D','I')",                         name="ck_image_foot_side"),
        Index("idx_images_wound", "wound_id"),
        Index("idx_images_eval",  "wound_evaluation_id"),
        Index("idx_images_date",  "taken_at"),
    )

    wound            : Mapped["Wound"]               = relationship("Wound", back_populates="images")
    wound_evaluation : Mapped[Optional["WoundEvaluation"]] = relationship("WoundEvaluation", back_populates="images")
    inferences       : Mapped[List["InferenceRun"]]  = relationship("InferenceRun", back_populates="image")


# ─────────────────────────────────────────────────────────────
# DOMINIO 7: MODELOS DE IA E INFERENCIAS
# ─────────────────────────────────────────────────────────────

class ModelVersion(Base):
    """
    Versión de un modelo de IA.
    Toda inferencia queda ligada a la versión exacta del modelo que la generó.
    Solo puede haber un modelo activo por tipo en cada momento.
    """
    __tablename__ = "model_versions"

    id              : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            : Mapped[str]             = mapped_column(String(100), nullable=False)
    version         : Mapped[str]             = mapped_column(String(30), nullable=False)
    model_type      : Mapped[str]             = mapped_column(String(30), nullable=False)
    architecture    : Mapped[Optional[str]]   = mapped_column(String(100))
    dataset_trained : Mapped[Optional[str]]   = mapped_column(String(200))
    dice_score      : Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    iou_score       : Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    weights_path    : Mapped[Optional[str]]   = mapped_column(String(500))
    is_active       : Mapped[bool]            = mapped_column(Boolean, nullable=False, default=False)
    deployed_at     : Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at      : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "model_type IN ('segmentacion','clasificacion_tisular','clasificacion_ulcera','explicabilidad','triage_multimodal')",
            name="ck_model_type"
        ),
    )

    inferences : Mapped[List["InferenceRun"]] = relationship("InferenceRun", back_populates="model_version")


class InferenceRun(Base):
    """
    Resultado de una inferencia de IA sobre una imagen.
    
    REGLAS CRÍTICAS:
    - Toda inferencia es INMUTABLE una vez creada.
    - Las correcciones se guardan en campos separados (corrected_area_cm2, etc).
    - La revisión humana es OBLIGATORIA — review_action debe completarse.
    - El disclaimer clínico está embebido en el modelo.
    """
    __tablename__ = "inference_runs"

    id                  : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id            : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("wound_images.id", ondelete="RESTRICT"), nullable=False)
    model_version_id    : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("model_versions.id"), nullable=False)
    # Segmentación
    mask_storage_key    : Mapped[Optional[str]]   = mapped_column(String(500))
    area_cm2            : Mapped[Optional[float]] = mapped_column(Numeric(8, 4))
    area_px             : Mapped[Optional[int]]   = mapped_column(Integer)
    # Clasificación tisular
    granulation_pct     : Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    fibrin_pct          : Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    necrosis_pct        : Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    # Triage multimodal (Agente 7 — Claude Vision)
    triage_severity     : Mapped[Optional[int]]   = mapped_column(SmallInteger)
    triage_color        : Mapped[Optional[str]]   = mapped_column(String(10))
    triage_narrative    : Mapped[Optional[str]]   = mapped_column(Text)
    triage_disclaimer   : Mapped[str]             = mapped_column(
        Text, nullable=False,
        default='Análisis asistido por IA. Requiere validación del profesional de salud. No reemplaza el diagnóstico clínico.'
    )
    # Cuestionario post-foto (inspirado en Curapp)
    questionnaire_data  : Mapped[Optional[dict]]  = mapped_column(JSONB)
    # Métricas de ejecución
    inference_ms        : Mapped[Optional[int]]   = mapped_column(Integer)
    error_message       : Mapped[Optional[str]]   = mapped_column(Text)
    status              : Mapped[str]             = mapped_column(String(20), nullable=False, default='pending')
    # Revisión humana OBLIGATORIA
    reviewed_by         : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at         : Mapped[Optional[datetime]]  = mapped_column(DateTime(timezone=True))
    review_action       : Mapped[Optional[str]]       = mapped_column(String(20))
    correction_notes    : Mapped[Optional[str]]       = mapped_column(Text)
    corrected_area_cm2  : Mapped[Optional[float]]     = mapped_column(Numeric(8, 4))
    created_at          : Mapped[datetime]            = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("triage_severity BETWEEN 0 AND 10",                              name="ck_triage_severity"),
        CheckConstraint("triage_color IN ('verde','amarillo','rojo')",                    name="ck_triage_color"),
        CheckConstraint("status IN ('pending','success','failed','rejected')",            name="ck_inference_status"),
        CheckConstraint("review_action IN ('aceptado','corregido','rechazado')",          name="ck_review_action"),
        Index("idx_inferences_image",  "image_id"),
        Index("idx_inferences_status", "status"),
        Index("idx_inferences_model",  "model_version_id"),
    )

    image         : Mapped["WoundImage"]   = relationship("WoundImage", back_populates="inferences")
    model_version : Mapped["ModelVersion"] = relationship("ModelVersion", back_populates="inferences")


# ─────────────────────────────────────────────────────────────
# DOMINIO 8: INFORMES PDF
# ─────────────────────────────────────────────────────────────

class GeneratedReport(Base):
    """
    Informe clínico PDF generado por el sistema.
    Los informes están versionados — reemplazar uno crea uno nuevo,
    el anterior queda como histórico referenciado por supersedes_id.
    """
    __tablename__ = "generated_reports"

    id              : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id      : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    generated_by    : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    report_type     : Mapped[str]             = mapped_column(String(30), nullable=False)
    title           : Mapped[Optional[str]]   = mapped_column(String(300))
    period_start    : Mapped[Optional[date]]  = mapped_column(Date)
    period_end      : Mapped[Optional[date]]  = mapped_column(Date)
    storage_key     : Mapped[Optional[str]]   = mapped_column(String(500))
    file_hash_sha256: Mapped[Optional[str]]   = mapped_column(String(64))
    version         : Mapped[int]             = mapped_column(SmallInteger, nullable=False, default=1)
    supersedes_id   : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("generated_reports.id"))
    clinical_disclaimer : Mapped[str]         = mapped_column(
        Text, nullable=False,
        default='Este informe es una herramienta de apoyo clínico. No reemplaza el diagnóstico ni el tratamiento médico.'
    )
    created_at      : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "report_type IN ('evolucion_herida','evaluacion_clinica','resumen_cientifico_semanal')",
            name="ck_report_type"
        ),
        Index("idx_reports_patient", "patient_id"),
    )

    patient : Mapped["Patient"] = relationship("Patient", back_populates="reports")


# ─────────────────────────────────────────────────────────────
# DOMINIO 9: PIPELINE CIENTÍFICO (Agentes 1-2-3)
# ─────────────────────────────────────────────────────────────

class ScientificArticle(Base):
    """
    Artículo científico recuperado por el Agente 1 (PubMed).
    El PMID es el identificador único — previene duplicados.
    """
    __tablename__ = "scientific_articles"

    id          : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pmid        : Mapped[Optional[str]]   = mapped_column(String(20), unique=True)
    doi         : Mapped[Optional[str]]   = mapped_column(String(200))
    title       : Mapped[str]             = mapped_column(Text, nullable=False)
    journal     : Mapped[Optional[str]]   = mapped_column(String(300))
    pub_date    : Mapped[Optional[date]]  = mapped_column(Date)
    abstract    : Mapped[Optional[str]]   = mapped_column(Text)
    url         : Mapped[Optional[str]]   = mapped_column(String(500))
    fetched_at  : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_duplicate: Mapped[bool]            = mapped_column(Boolean, default=False)
    source      : Mapped[str]             = mapped_column(String(50), default='pubmed')

    summaries : Mapped[List["ScientificSummary"]] = relationship("ScientificSummary", back_populates="article")


class ScientificSummary(Base):
    """
    Resumen generado por el Agente 2 (Redactor IA).
    Tiene versiones por audiencia: médico, paciente, general.
    El campo embedding permite búsqueda semántica con pgvector.
    """
    __tablename__ = "scientific_summaries"

    id           : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id   : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("scientific_articles.id"), nullable=False)
    audience     : Mapped[str]            = mapped_column(String(20), nullable=False)
    summary_text : Mapped[str]            = mapped_column(Text, nullable=False)
    generated_by : Mapped[str]            = mapped_column(String(50), default='claude-sonnet-4-6')
    reviewed     : Mapped[bool]           = mapped_column(Boolean, default=False)
    created_at   : Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    # pgvector — solo si la extensión está disponible
    if PGVECTOR_AVAILABLE:
        embedding = Column(Vector(1536))

    __table_args__ = (
        CheckConstraint("audience IN ('medico','paciente','general')", name="ck_summary_audience"),
        Index("idx_summaries_article", "article_id"),
    )

    article : Mapped["ScientificArticle"] = relationship("ScientificArticle", back_populates="summaries")


# ─────────────────────────────────────────────────────────────
# DOMINIO 10: AUDITORÍA
# ─────────────────────────────────────────────────────────────

class AuditEvent(Base):
    """
    Registro inmutable de todas las acciones en el sistema.
    
    REGLAS:
    - Append-only: nunca se hace UPDATE ni DELETE sobre esta tabla.
    - Se registran: accesos, cambios, inferencias, descargas.
    - Usar BIGSERIAL (no UUID) por el alto volumen esperado.
    """
    __tablename__ = "audit_events"

    id              : Mapped[int]                = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id         : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    organization_id : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    event_type      : Mapped[str]                = mapped_column(String(50), nullable=False)
    entity_type     : Mapped[Optional[str]]      = mapped_column(String(50))
    entity_id       : Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    ip_address      : Mapped[Optional[str]]      = mapped_column(String(45))   # IPv4 e IPv6
    user_agent      : Mapped[Optional[str]]      = mapped_column(Text)
    extra_data      : Mapped[Optional[dict]]     = mapped_column(JSONB)
    occurred_at     : Mapped[datetime]           = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        CheckConstraint("""
            event_type IN (
                'login','logout',
                'patient_create','patient_view','patient_update',
                'image_upload','image_view',
                'inference_run','inference_review',
                'report_generate','report_download',
                'data_export',
                'user_create','user_update',
                'config_change'
            )
        """, name="ck_audit_event_type"),
        Index("idx_audit_user",   "user_id"),
        Index("idx_audit_org",    "organization_id"),
        Index("idx_audit_type",   "event_type"),
        Index("idx_audit_entity", "entity_type", "entity_id"),
    )


# ─────────────────────────────────────────────────────────────
# DOMINIO 11: RELACIONES DE CUIDADO CLÍNICO (RBAC PERSISTENTE)
# ─────────────────────────────────────────────────────────────

class CareRelationship(Base):
    """
    Relación de atención clínica activa entre un profesional o cuidador y un paciente.
    Base de la autorización tridimensional en PostgreSQL: ROLE + CARE_RELATIONSHIP + RESOURCE_OWNERSHIP.
    """
    __tablename__ = "care_relationships"

    id               : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id  : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    patient_id       : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    user_id          : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str]                = mapped_column(String(30), nullable=False, default='medico_tratante')
    is_active        : Mapped[bool]               = mapped_column(Boolean, nullable=False, default=True)
    created_at       : Mapped[datetime]           = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at       : Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("relationship_type IN ('medico_tratante','cuidador','interconsultor','familiar')", name="ck_care_rel_type"),
        Index("idx_care_rel_patient", "patient_id"),
        Index("idx_care_rel_user", "user_id"),
        UniqueConstraint("patient_id", "user_id", name="uq_patient_user_rel")
    )

    patient : Mapped["Patient"] = relationship("Patient")
    user    : Mapped["User"]    = relationship("User")


# ─────────────────────────────────────────────────────────────
# DOMINIO 8: PILOTO CERRADO v0.1 (ZERO PII)
# ─────────────────────────────────────────────────────────────

class PilotCase(Base):
    """
    Caso de prueba en el Piloto v0.1.
    Estrictamente desidentificado (cero PII de pacientes).
    """
    __tablename__ = "pilot_cases"

    id              : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pilot_case_uuid : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    physician_id    : Mapped[uuid.UUID]       = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    case_alias      : Mapped[Optional[str]]   = mapped_column(String(50), nullable=True) # e.g. "PILOT-0001"
    is_active       : Mapped[bool]            = mapped_column(Boolean, nullable=False, default=True)
    created_at      : Mapped[datetime]        = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_pilot_cases_physician", "physician_id"),
        Index("idx_pilot_cases_uuid", "pilot_case_uuid"),
        Index("idx_pilot_cases_alias", "case_alias"),
    )

    physician : Mapped["User"] = relationship("User")
    wounds    : Mapped[List["PilotWound"]]    = relationship("PilotWound", back_populates="pilot_case", cascade="all, delete-orphan")
    analyses  : Mapped[List["PilotAnalysis"]] = relationship("PilotAnalysis", back_populates="pilot_case", cascade="all, delete-orphan")


class PilotWound(Base):
    """
    Herida o lesión clínica identificada dentro de un PilotCase.
    Permite seguimiento longitudinal de múltiples lesiones en un mismo paciente.
    """
    __tablename__ = "pilot_wounds"

    id              : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wound_uuid      : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    pilot_case_id   : Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id", ondelete="CASCADE"), nullable=False)
    wound_label     : Mapped[str]       = mapped_column(String(100), nullable=False, default="Herida 1") # e.g. "Herida 1"
    wound_location  : Mapped[str]       = mapped_column(String(100), nullable=False, default="Plantar")  # e.g. "Talón", "Hallux"
    created_at      : Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_pilot_wounds_case", "pilot_case_id"),
        Index("idx_pilot_wounds_uuid", "wound_uuid"),
    )

    pilot_case : Mapped["PilotCase"]           = relationship("PilotCase", back_populates="wounds")
    analyses   : Mapped[List["PilotAnalysis"]] = relationship("PilotAnalysis", back_populates="pilot_wound")


class PilotAnalysis(Base):
    """
    Sesión individual de análisis fotográfico e inferencia en el Piloto v0.1.
    Almacena resultados técnicos, shadow mode y control de retención TTL:
    - 72 horas para fotos aisladas.
    - 21 días para fotos longitudinales vinculadas a PilotCase + PilotWound.
    """
    __tablename__ = "pilot_analyses"

    id                         : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pilot_case_id              : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_cases.id", ondelete="CASCADE"), nullable=False)
    pilot_wound_id             : Mapped[Optional[uuid.UUID]]= mapped_column(UUID(as_uuid=True), ForeignKey("pilot_wounds.id", ondelete="SET NULL"), nullable=True)
    physician_id               : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    analysis_uuid              : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    photo_uuid                 : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    photo_storage_key          : Mapped[Optional[str]]    = mapped_column(String(500), nullable=True)
    photo_mime_type            : Mapped[str]              = mapped_column(String(50), default="image/jpeg")
    privacy_gate_confirmed     : Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    quality_gate_score         : Mapped[Optional[int]]    = mapped_column(Integer, nullable=True)
    quality_gate_status        : Mapped[Optional[str]]    = mapped_column(String(50), nullable=True) # "optimo", "advertencia", "insuficiente"
    ai_status                  : Mapped[str]              = mapped_column(String(50), nullable=False, default="PENDING") # "COMPLETED", "NO_EVALUABLE", "AI_FAILED", "PROVIDER_FAILED", "UPLOAD_FAILED"
    model_name                 : Mapped[str]              = mapped_column(String(100), default="EfficientNet-B0 + U-Net")
    model_version              : Mapped[str]              = mapped_column(String(50), default="1.0.0")
    classification_label       : Mapped[Optional[str]]    = mapped_column(String(100), nullable=True)
    classification_confidence  : Mapped[Optional[float]]  = mapped_column(Numeric(5, 4), nullable=True)
    scale_detected             : Mapped[bool]             = mapped_column(Boolean, nullable=False, default=False)
    pixel_area                 : Mapped[Optional[int]]    = mapped_column(Integer, nullable=True)
    relative_area_percent      : Mapped[Optional[float]]  = mapped_column(Numeric(5, 2), nullable=True)
    absolute_area_cm2          : Mapped[Optional[float]]  = mapped_column(Numeric(8, 2), nullable=True) # estrictamente NULL si scale_detected=False
    segmentation_mask_key      : Mapped[Optional[str]]    = mapped_column(String(500), nullable=True)
    shadow_mode_assessment     : Mapped[Optional[dict]]   = mapped_column(JSONB, nullable=True) # Impresión preliminar ciega del médico
    processing_duration_ms     : Mapped[Optional[int]]    = mapped_column(Integer, nullable=True)
    taken_at_custom            : Mapped[Optional[datetime]]= mapped_column(DateTime(timezone=True), nullable=True) # Fecha histórica real si se conoce
    sequence_index             : Mapped[Optional[int]]    = mapped_column(Integer, nullable=True) # 1, 2, 3...
    created_at                 : Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at                 : Mapped[datetime]         = mapped_column(DateTime(timezone=True), nullable=False) # 72h o 21d
    deleted_at                 : Mapped[Optional[datetime]]= mapped_column(DateTime(timezone=True), nullable=True) # Timestamp de purga de foto

    __table_args__ = (
        Index("idx_pilot_analysis_case", "pilot_case_id"),
        Index("idx_pilot_analysis_wound", "pilot_wound_id"),
        Index("idx_pilot_analysis_physician", "physician_id"),
        Index("idx_pilot_analysis_uuid", "analysis_uuid"),
        Index("idx_pilot_analysis_expires", "expires_at"),
    )

    pilot_case  : Mapped["PilotCase"]     = relationship("PilotCase", back_populates="analyses")
    pilot_wound : Mapped[Optional["PilotWound"]] = relationship("PilotWound", back_populates="analyses")
    physician   : Mapped["User"]          = relationship("User")
    feedback    : Mapped[Optional["PilotFeedback"]] = relationship("PilotFeedback", back_populates="analysis", uselist=False, cascade="all, delete-orphan")


class PilotFeedback(Base):
    """
    Evaluación y retroalimentación emitida por el médico sobre el análisis individual de la IA.
    Estrictamente desidentificada.
    """
    __tablename__ = "pilot_feedbacks"

    id                          : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id                 : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_analyses.id", ondelete="CASCADE"), unique=True, nullable=False)
    physician_id                : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_clinically_evaluable     : Mapped[bool]             = mapped_column(Boolean, nullable=False) # Sí / No
    segmentation_rating         : Mapped[str]              = mapped_column(String(50), nullable=False) # "Correcta", "Parcial", "Incorrecta"
    concordance_rating          : Mapped[str]              = mapped_column(String(50), nullable=False) # "Sí", "Parcial", "No"
    would_modify_classification : Mapped[bool]             = mapped_column(Boolean, nullable=False) # Sí / No
    utility_score               : Mapped[int]              = mapped_column(SmallInteger, nullable=False) # 1 a 5
    comment                     : Mapped[Optional[str]]    = mapped_column(String(250), nullable=True)
    created_at                  : Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("segmentation_rating IN ('Correcta','Parcial','Incorrecta')", name="ck_pilot_fb_seg"),
        CheckConstraint("concordance_rating IN ('Sí','Parcial','No')", name="ck_pilot_fb_conc"),
        CheckConstraint("utility_score BETWEEN 1 AND 5", name="ck_pilot_fb_utility"),
        Index("idx_pilot_fb_analysis", "analysis_id"),
        Index("idx_pilot_fb_physician", "physician_id"),
    )

    analysis  : Mapped["PilotAnalysis"] = relationship("PilotAnalysis", back_populates="feedback")
    physician : Mapped["User"]          = relationship("User")


class PilotEvolutionFeedback(Base):
    """
    Evaluación médica longitudinal comparativa entre dos análisis de la misma herida.
    """
    __tablename__ = "pilot_evolution_feedbacks"

    id                              : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    baseline_analysis_id            : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_analyses.id", ondelete="CASCADE"), nullable=False)
    followup_analysis_id            : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("pilot_analyses.id", ondelete="CASCADE"), nullable=False)
    physician_id                    : Mapped[uuid.UUID]     = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    clinical_evolution              : Mapped[str]           = mapped_column(String(20), nullable=False) # "MEJOR", "SIMILAR", "PEOR"
    system_representation_agreement : Mapped[str]           = mapped_column(String(20), nullable=False) # "SI", "PARCIAL", "NO"
    comment                         : Mapped[Optional[str]] = mapped_column(String(250), nullable=True)
    created_at                      : Mapped[datetime]      = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("clinical_evolution IN ('MEJOR','SIMILAR','PEOR')", name="ck_pilot_evol_rating"),
        CheckConstraint("system_representation_agreement IN ('SI','PARCIAL','NO')", name="ck_pilot_evol_agree"),
        Index("idx_pilot_evol_baseline", "baseline_analysis_id"),
        Index("idx_pilot_evol_followup", "followup_analysis_id"),
        Index("idx_pilot_evol_physician", "physician_id"),
    )

    baseline_analysis : Mapped["PilotAnalysis"] = relationship("PilotAnalysis", foreign_keys=[baseline_analysis_id])
    followup_analysis : Mapped["PilotAnalysis"] = relationship("PilotAnalysis", foreign_keys=[followup_analysis_id])
    physician         : Mapped["User"]          = relationship("User")


# ─────────────────────────────────────────────────────────────
# HELPER: crear todas las tablas en desarrollo
# ─────────────────────────────────────────────────────────────

def create_all(database_url: str) -> None:
    """
    Crea todas las tablas directamente (solo para desarrollo local).
    En staging y producción usar: alembic upgrade head
    """
    from sqlalchemy import create_engine
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    print(f"✓ {len(Base.metadata.tables)} tablas creadas en {database_url}")


if __name__ == "__main__":
    import os
    db_url = os.getenv("DATABASE_URL", "postgresql://adminpd:password@localhost:5432/piediadbetico")
    create_all(db_url)
