"""
╔══════════════════════════════════════════════════════════════════════╗
║  AGENTE 4 — CLASIFICADOR BINARIO DE ÚLCERA                         ║
║  piediabetico.lat — Versión 1.0.0                                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  Modelo: EfficientNet-B0 entrenado con dataset DFU                  ║
║  Tarea:  Clasificación binaria — Úlcera / Piel sana                ║
║  AUC:    ~0.98 en validación                                        ║
║  Accuracy: ~95% en validación                                       ║
║                                                                     ║
║  Archivo del modelo: /opt/piediadbetico/modelos/                    ║
║    dfu_efficientnet_b0.onnx  (0.5 MB)                              ║
║                                                                     ║
║  Rol en el sistema:                                                 ║
║  Pre-filtro rápido antes del Agente 7 (Claude Vision).             ║
║  Si detecta úlcera → pasa al análisis completo.                    ║
║  Si detecta piel sana → ahorra la llamada a Claude API.            ║
╚══════════════════════════════════════════════════════════════════════╝

Integración en main.py:
    from agente4_clasificador_ulcera import router_agente4
    app.include_router(router_agente4)

Endpoint disponible:
    POST /agentes/clasificar-ulcera
"""

import os
import base64
import logging
import numpy as np
from io import BytesIO
from PIL import Image
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# CARGA DEL MODELO ONNX
# ─────────────────────────────────────────────────────────────────────

MODELO_PATH = os.getenv(
    "CLASIFICADOR_ONNX_PATH",
    "/opt/piediadbetico/modelos/dfu_efficientnet_b0.onnx"
)

# Normalización ImageNet (igual que en el entrenamiento)
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32)
IMG_SIZE = 224

# Clases en el mismo orden que el entrenamiento
CLASES = ["Normal(Healthy skin)", "Abnormal(Ulcer)"]

_session = None  # Se carga una vez al primer uso (lazy loading)


def _get_session():
    """Carga el modelo ONNX una sola vez y lo reutiliza."""
    global _session
    if _session is None:
        try:
            import onnxruntime as ort
            if not os.path.exists(MODELO_PATH):
                raise FileNotFoundError(
                    f"Modelo ONNX no encontrado en: {MODELO_PATH}\n"
                    f"Subí el archivo dfu_efficientnet_b0.onnx al VPS en esa ruta."
                )
            _session = ort.InferenceSession(
                MODELO_PATH,
                providers=["CPUExecutionProvider"]  # CPU — sin GPU necesaria
            )
            logger.info(f"✓ Modelo ONNX cargado desde: {MODELO_PATH}")
        except ImportError:
            raise ImportError(
                "onnxruntime no está instalado. "
                "Agregá 'onnxruntime==1.19.0' al requirements.txt"
            )
    return _session


# ─────────────────────────────────────────────────────────────────────
# PREPROCESAMIENTO DE IMAGEN
# ─────────────────────────────────────────────────────────────────────

def _preprocesar_imagen(imagen_b64: str) -> np.ndarray:
    """
    Convierte una imagen base64 al tensor que espera el modelo ONNX.
    
    Pipeline:
        base64 → bytes → PIL Image → RGB → resize 224x224 
        → normalizar ImageNet → (1, 3, 224, 224) float32
    """
    try:
        imagen_bytes = base64.b64decode(imagen_b64)
        imagen = Image.open(BytesIO(imagen_bytes)).convert("RGB")
        imagen = imagen.resize((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
        arr = np.array(imagen, dtype=np.float32) / 255.0      # [0,1]
        arr = (arr - MEAN) / STD                               # normalizar
        arr = arr.transpose(2, 0, 1)                           # HWC → CHW
        arr = arr[np.newaxis, :]                               # → (1,3,H,W)
        return arr
    except Exception as e:
        raise ValueError(f"Error al procesar la imagen: {str(e)}")


# ─────────────────────────────────────────────────────────────────────
# INFERENCIA
# ─────────────────────────────────────────────────────────────────────

def _inferir(imagen_b64: str) -> dict:
    """
    Corre el modelo ONNX sobre la imagen y devuelve las probabilidades.
    """
    session = _get_session()
    tensor  = _preprocesar_imagen(imagen_b64)

    input_name  = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    logits = session.run([output_name], {input_name: tensor})[0][0]

    # Softmax manual
    exp_logits   = np.exp(logits - np.max(logits))
    probabilidades = exp_logits / exp_logits.sum()

    prob_normal = float(probabilidades[0])
    prob_ulcera = float(probabilidades[1])

    es_ulcera   = prob_ulcera > 0.5
    confianza   = prob_ulcera if es_ulcera else prob_normal

    return {
        "es_ulcera":    es_ulcera,
        "prob_ulcera":  round(prob_ulcera, 4),
        "prob_normal":  round(prob_normal, 4),
        "confianza":    round(confianza, 4),
        "clase":        "Úlcera detectada" if es_ulcera else "Piel sana",
    }


# ─────────────────────────────────────────────────────────────────────
# SCHEMAS PYDANTIC
# ─────────────────────────────────────────────────────────────────────

class ClasificadorInput(BaseModel):
    imagen_base64: str = Field(
        ...,
        description="Imagen codificada en base64 (JPEG o PNG). Mínimo 100x100px."
    )
    umbral_ulcera: float = Field(
        default=0.5,
        ge=0.1, le=0.95,
        description=(
            "Umbral de probabilidad para clasificar como úlcera. "
            "Default 0.5. Bajar a 0.3 aumenta sensibilidad (menos falsos negativos). "
            "Subir a 0.7 aumenta especificidad (menos falsos positivos)."
        )
    )


class ClasificadorOutput(BaseModel):
    es_ulcera:              bool  = Field(..., description="True si el modelo detecta úlcera")
    prob_ulcera:            float = Field(..., description="Probabilidad de úlcera (0 a 1)")
    prob_normal:            float = Field(..., description="Probabilidad de piel sana (0 a 1)")
    confianza:              float = Field(..., description="Confianza de la predicción ganadora")
    clase:                  str   = Field(..., description="Etiqueta: 'Úlcera detectada' o 'Piel sana'")
    derivar_a_agente7:      bool  = Field(..., description="True si debe pasar al análisis con Claude Vision")
    umbral_aplicado:        float = Field(..., description="Umbral de decisión usado")
    modelo:                 str   = Field(..., description="Identificador del modelo usado")
    disclaimer:             str   = Field(..., description="Aviso clínico")


DISCLAIMER = (
    "⚠️ Clasificación automática con AUC ~0.98 en validación. "
    "No es un diagnóstico clínico. Requiere validación por profesional de salud habilitado."
)


# ─────────────────────────────────────────────────────────────────────
# ROUTER FASTAPI
# ─────────────────────────────────────────────────────────────────────

router_agente4 = APIRouter(
    prefix="/agentes",
    tags=["Agente 4 — Clasificador de Úlcera"]
)


@router_agente4.post(
    "/clasificar-ulcera",
    response_model=ClasificadorOutput,
    summary="Agente 4 — Clasificación binaria úlcera / piel sana",
)
def api_clasificar_ulcera(datos: ClasificadorInput):
    """
    **Agente 4 — Clasificador Binario de Úlcera de Pie Diabético**

    Analiza una imagen y determina si contiene una úlcera de pie diabético
    o piel sana. Actúa como pre-filtro antes del análisis completo del Agente 7.

    **Modelo:** EfficientNet-B0 entrenado con dataset DFU
    **Métricas:** AUC ~0.98 | Accuracy ~95% en validación

    **Flujo recomendado:**
    1. Subir foto → Agente 4 clasifica (rápido, 100-200ms en CPU)
    2. Si `derivar_a_agente7 = true` → enviar al Agente 7 (Claude Vision)
    3. Si `derivar_a_agente7 = false` → informar al usuario que no se detecta úlcera

    **Ajuste del umbral:**
    - Contexto clínico (alta sensibilidad): umbral 0.3
    - Uso general: umbral 0.5 (default)
    - Alta especificidad: umbral 0.7

    **Disclaimer:** Herramienta de apoyo. No reemplaza el criterio clínico.
    """
    try:
        resultado = _inferir(datos.imagen_base64)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"[Agente 4] Error inesperado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno en la clasificación.")

    # Aplicar umbral personalizado
    es_ulcera_final = resultado["prob_ulcera"] >= datos.umbral_ulcera

    logger.info(
        f"[Agente 4] Clasificación — "
        f"úlcera: {es_ulcera_final}, "
        f"prob: {resultado['prob_ulcera']:.3f}, "
        f"umbral: {datos.umbral_ulcera}"
    )

    return ClasificadorOutput(
        es_ulcera         = es_ulcera_final,
        prob_ulcera       = resultado["prob_ulcera"],
        prob_normal       = resultado["prob_normal"],
        confianza         = resultado["confianza"],
        clase             = "Úlcera detectada" if es_ulcera_final else "Piel sana",
        derivar_a_agente7 = es_ulcera_final,
        umbral_aplicado   = datos.umbral_ulcera,
        modelo            = "EfficientNet-B0 DFU v1.0 (ONNX)",
        disclaimer        = DISCLAIMER,
    )


@router_agente4.get(
    "/clasificar-ulcera/estado",
    summary="Estado del modelo del Agente 4",
)
def estado_modelo():
    """Verifica si el modelo ONNX está cargado y listo."""
    modelo_existe = os.path.exists(MODELO_PATH)
    try:
        if modelo_existe:
            _get_session()
            modelo_cargado = True
        else:
            modelo_cargado = False
    except Exception:
        modelo_cargado = False

    return {
        "modelo_path":    MODELO_PATH,
        "modelo_existe":  modelo_existe,
        "modelo_cargado": modelo_cargado,
        "estado":         "listo" if modelo_cargado else "modelo no disponible",
        "metricas":       {"auc_validacion": 0.98, "accuracy_validacion": 0.95},
        "clases":         CLASES,
    }
