"""
🧬 DOMINIO CLÍNICO: IDENTIDAD DE LESIÓN Y EVALUACIONES LONGITUDINALES
piediabetico.lat — IWGDF 2023 / TIMERS Architecture
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
import uuid

class FootSideEnum(str, Enum):
    DERECHO = "D"
    IZQUIERDO = "I"

class WoundStatusEnum(str, Enum):
    ACTIVA = "activa"
    EN_CICATRIZACION = "en_cicatrizacion"
    CICATRIZADA = "cicatrizada"
    AMPUTADA = "amputada"
    RECIDIVA = "recidiva"

class WoundLocationEnum(str, Enum):
    HALLUX_PLANTAR = "hallux_plantar"
    HALLUX_DORSAL = "hallux_dorsal"
    METATARSO_1_3 = "metatarso_1_3"
    METATARSO_4_5 = "metatarso_4_5"
    TALON = "talon"
    MEDIOPIE = "mediopie"
    MALEOLO_INTERNO = "maleolo_interno"
    MALEOLO_EXTERNO = "maleolo_externo"
    DORSO = "dorso"
    INTERDIGITAL = "interdigital"

class WoundBase(BaseModel):
    patient_id: uuid.UUID
    foot_side: FootSideEnum
    location: WoundLocationEnum
    location_notes: Optional[str] = None
    etiology: Optional[str] = "neuropatica"  # neuropatica, isquemica, neuroisquemica
    first_seen_at: date = Field(default_factory=date.today)
    status: WoundStatusEnum = WoundStatusEnum.ACTIVA
    wagner_grade: Optional[int] = Field(None, ge=0, le=5)
    texas_grade: Optional[str] = None

class WoundCreate(WoundBase):
    pass

class WoundEvaluationCreate(BaseModel):
    wound_id: uuid.UUID
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    area_cm2: Optional[float] = None
    reduction_pct_4w: Optional[float] = None
    triage_semaforo: str = "verde"  # verde, amarillo, rojo, gris
    quality_score: Optional[int] = Field(None, ge=0, le=100)
    tissue_granulation_pct: Optional[float] = None
    tissue_slough_pct: Optional[float] = None
    tissue_necrotic_pct: Optional[float] = None
    infection_present: bool = False
    exudate_amount: Optional[str] = "escaso"
    timers_dressing_suggestion: Optional[str] = None
    clinical_notes: Optional[str] = None

class Wound(WoundBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    evaluations: List[WoundEvaluationCreate] = []

    class Config:
        orm_mode = True
