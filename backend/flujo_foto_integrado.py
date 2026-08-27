"""
╔══════════════════════════════════════════════════════════════════════╗
║  FLUJO INTEGRADO — Agente 4 → Agente 7 (Gemini / Claude)           ║
║  piediabetico.lat — Versión 2.0.0                                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  1. Agente 4 (ONNX, ~100ms):                                        ║
║     └── Clasifica si hay úlcera o piel sana                         ║
║         ├── Piel sana → responde rápido                             ║
║         └── Úlcera → deriva al Agente 7                             ║
║                                                                     ║
║  2. Agente 7 (Gemini / Claude Vision):                              ║
║     └── Análisis clínico adaptado al perfil del usuario             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agente4_clasificador_ulcera import (
    ClasificadorInput,
    _inferir as clasificar_imagen,
)
from agente7_triage_multimodal import (
    TriageInput,
    DatosClinicosContexto,
    PerfilUsuario,
    IAProvider,
    ejecutar_triage,
    TriageOutput,
)

logger = logging.getLogger(__name__)

router_flujo = APIRouter(tags=["Flujo Integrado — Foto Completo"])

DISCLAIMER = (
    "⚠️ Análisis asistido por IA. No reemplaza el criterio clínico profesional."
)


class FotoAnalisisInput(BaseModel):
    imagen_base64: str = Field(
        ...,
        description="Foto de la herida o del pie en base64 (JPEG o PNG)."
    )
    perfil_usuario: PerfilUsuario = Field(
        default=PerfilUsuario.PACIENTE,
        description="Perfil del usuario (paciente, podologo_enfermero, infectologo, diabetologo, medico_general)."
    )
    datos_clinicos: DatosClinicosContexto = Field(
        default_factory=DatosClinicosContexto,
        description="Contexto clínico del paciente."
    )
    imagen_mime_type: str = Field(
        default="image/jpeg",
        description="Tipo MIME: image/jpeg o image/png"
    )
    umbral_ulcera: float = Field(
        default=0.35,
        ge=0.1, le=0.95,
        description="Umbral del clasificador para derivar al análisis completo (default 0.35)."
    )
    forzar_analisis_completo: bool = Field(
        default=False,
        description="Si True, omite el Agente 4 y ejecuta directo el Agente 7."
    )
    proveedor_ia: IAProvider = Field(
        default=IAProvider.AUTO,
        description="Proveedor de IA: auto (Gemini con fallback a Claude), gemini o claude."
    )
    api_key_override: Optional[str] = Field(
        None,
        description="API key opcional si se envía desde el cliente web."
    )


class FotoAnalisisOutput(BaseModel):
    # Resultado Agente 4
    clasificacion_realizada:   bool          = Field(..., description="Si se ejecutó el clasificador ONNX")
    es_ulcera:                 bool          = Field(..., description="True si se detectó sospecha de úlcera")
    prob_ulcera:               float         = Field(..., description="Probabilidad de úlcera (0 a 1)")
    clase_detectada:           str           = Field(..., description="'Úlcera detectada' o 'Piel sana'")

    # Resultado Agente 7
    analisis_realizado:        bool          = Field(..., description="Si se ejecutó el análisis multimodal")
    analisis_clinico:          Optional[str] = Field(None, description="Dictamen clínico de la IA")
    proveedor_utilizado:       Optional[str] = Field(None, description="Proveedor que ejecutó el análisis")
    modelo_utilizado:          Optional[str] = Field(None, description="Modelo de IA usado")
    tiempo_ms:                 Optional[int] = Field(None, description="Tiempo de procesamiento en ms")
    nivel_urgencia:            Optional[str] = Field(None, description="bajo / moderado / alto / emergencia")
    color_semaforo:            Optional[str] = Field(None, description="verde / amarillo / rojo")
    motivo_sin_analisis:       Optional[str] = Field(None, description="Detalle si no fue derivado")

    # Metadatos
    perfil_consultado:         str           = Field(..., description="Perfil consultado")
    umbral_aplicado:           float         = Field(..., description="Umbral aplicado")
    disclaimer:                str           = Field(..., description="Aviso clínico")


def _ejecutar_flujo(datos: FotoAnalisisInput) -> FotoAnalisisOutput:
    """Orquesta el flujo Agente 4 -> Agente 7."""
    es_ulcera = True
    prob_ulcera = 1.0
    clase = "Análisis directo"
    clasificacion_realizada = False

    # Paso 1: Intentar clasificador ONNX si no se fuerza el análisis
    if not datos.forzar_analisis_completo:
        try:
            logger.info("[Flujo] Ejecutando Agente 4 (Clasificador ONNX)...")
            res_clasif = clasificar_imagen(datos.imagen_base64)
            clasificacion_realizada = True
            prob_ulcera = res_clasif["prob_ulcera"]
            es_ulcera = prob_ulcera >= datos.umbral_ulcera
            clase = res_clasif["clase"]
        except Exception as e:
            logger.warning(f"[Flujo] Agente 4 no disponible ({e}), derivando directo a Agente 7.")
            es_ulcera = True
            clasificacion_realizada = False

    # Paso 2: Si es úlcera o forzado -> Agente 7
    if es_ulcera or datos.forzar_analisis_completo:
        logger.info(f"[Flujo] Derivando a Agente 7 ({datos.proveedor_ia.value})...")
        triage_in = TriageInput(
            imagen_base64=datos.imagen_base64,
            perfil_usuario=datos.perfil_usuario,
            datos_clinicos=datos.datos_clinicos,
            imagen_mime_type=datos.imagen_mime_type,
            proveedor_ia=datos.proveedor_ia,
            api_key_override=datos.api_key_override,
        )
        triage_res = ejecutar_triage(triage_in)

        return FotoAnalisisOutput(
            clasificacion_realizada=clasificacion_realizada,
            es_ulcera=True,
            prob_ulcera=round(prob_ulcera, 4),
            clase_detectada=clase if clasificacion_realizada else "Derivado a IA",
            analisis_realizado=True,
            analisis_clinico=triage_res.analisis_ia,
            proveedor_utilizado=triage_res.proveedor_utilizado,
            modelo_utilizado=triage_res.modelo_utilizado,
            tiempo_ms=triage_res.tiempo_ms,
            nivel_urgencia=triage_res.nivel_urgencia,
            color_semaforo=triage_res.color_semaforo,
            motivo_sin_analisis=None,
            perfil_consultado=datos.perfil_usuario.value,
            umbral_aplicado=datos.umbral_ulcera,
            disclaimer=DISCLAIMER,
        )
    else:
        # Piel sana detectada por el clasificador
        mensaje_piel_sana = (
            "🟢 Piel sana detectada por el clasificador preliminar (probabilidad de úlcera < umbral). "
            "No se observan signos evidentes de úlcera activa. Se recomienda mantener inspección periódica y calzado adecuado."
        )
        return FotoAnalisisOutput(
            clasificacion_realizada=True,
            es_ulcera=False,
            prob_ulcera=round(prob_ulcera, 4),
            clase_detectada=clase,
            analisis_realizado=False,
            analisis_clinico=mensaje_piel_sana,
            proveedor_utilizado="ONNX Local",
            modelo_utilizado="EfficientNet-B0 DFU",
            tiempo_ms=120,
            nivel_urgencia="bajo",
            color_semaforo="verde",
            motivo_sin_analisis="El modelo preliminar clasificó la imagen como piel sana.",
            perfil_consultado=datos.perfil_usuario.value,
            umbral_aplicado=datos.umbral_ulcera,
            disclaimer=DISCLAIMER,
        )


@router_flujo.post(
    "/analizar-foto",
    response_model=FotoAnalisisOutput,
    summary="Flujo Completo: Clasificación + Triage Multimodal",
)
def api_analizar_foto(datos: FotoAnalisisInput):
    """
    **Flujo Integral de Análisis Fotográfico de Pie Diabético**
    
    1. Agente 4 (Clasificador ONNX) detecta si hay lesión/úlcera.
    2. Agente 7 (Gemini / Claude Vision) genera el análisis clínico especializado.
    """
    try:
        return _ejecutar_flujo(datos)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Flujo] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
