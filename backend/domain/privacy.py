"""
🛡️ DOMINIO DE PRIVACIDAD, CONSENTIMIENTOS Y SANITIZACIÓN
piediabetico.lat — Privacy by Design Architecture
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid

class ImageCategoryEnum(str, Enum):
    ORIGINAL_CLINICAL = "original_clinical"
    CLINICAL_PROCESSED = "clinical_processed"
    RESEARCH_ANONYMIZED = "research_anonymized"

class ConsentTypeEnum(str, Enum):
    CLINICO = "clinico"
    INVESTIGACION_IA = "investigacion_ia"

class PatientConsentCreate(BaseModel):
    patient_id: uuid.UUID
    consent_type: ConsentTypeEnum
    version: str = "2026.1"
    accepted: bool
    accepted_by_role: str = "paciente"
    document_hash: Optional[str] = None

class SafeClinicalContextBuilder:
    """
    Minimización estricta de datos para IA Externa.
    Despoja nombre, DNI, email, teléfono, domicilio y N° historia clínica.
    """
    @staticmethod
    def build_safe_clinical_context(
        foot_side: str,
        location: str,
        evolution_time: str,
        fever: bool,
        odor: bool,
        quality_score: int,
        wound_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "lesion_id_anonima": wound_id or "DFU-ANONIMO",
            "lateralidad": foot_side,
            "ubicacion_anatomica": location,
            "tiempo_evolucion": evolution_time,
            "signos_locales": {
                "fiebre_o_escalofrios": fever,
                "olor_o_secrecion": odor
            },
            "calidad_optica_score": quality_score,
            "consenso_referencia": "IWGDF 2023"
        }
