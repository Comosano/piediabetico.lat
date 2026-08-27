"""
╔══════════════════════════════════════════════════════════════════════╗
║  AGENTE 7 — TRIAGE MULTIMODAL CON IA UNIFICADA (GEMINI + CLAUDE)   ║
║  piediabetico.lat — Versión 2.0.0 (Agosto 2026)                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  Tecnología: Google Gemini (2.5 Flash / Pro) + Anthropic Claude      ║
║  Perfiles:   paciente / podologo_enfermero / infectologo /          ║
║              diabetologo / medico_general                           ║
║  Modo:       Dual-Provider con Auto-Fallback inteligente             ║
║                                                                     ║
║  DISCLAIMER: Herramienta de apoyo clínico. No reemplaza el         ║
║  diagnóstico ni el tratamiento médico profesional.                  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import base64
import logging
from enum import Enum
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN Y CONSTANTES
# ─────────────────────────────────────────────────────────────────────

GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CLAUDE_MODEL_DEFAULT = os.getenv("CLAUDE_MODEL", "claude-3-7-sonnet-20250219")
MAX_TOKENS = 1500

DISCLAIMER = (
    "⚠️ AVISO CLÍNICO: Este análisis es generado por inteligencia artificial "
    "como herramienta de apoyo educativo y orientativo basado en guías internacionales (IWGDF, IDSA, TIMERS). "
    "No reemplaza el diagnóstico clínico ni el criterio del profesional de salud habilitado. "
    "Toda decisión terapéutica debe ser validada por un médico o profesional competente."
)

# ─────────────────────────────────────────────────────────────────────
# ENUMS Y SCHEMAS PYDANTIC
# ─────────────────────────────────────────────────────────────────────

class IAProvider(str, Enum):
    AUTO    = "auto"      # Intenta Gemini primero; si falla, va a Claude
    GEMINI  = "gemini"    # Google Gemini 2.5 Flash / Pro
    CLAUDE  = "claude"    # Anthropic Claude 3.7 / 3.5 Sonnet


class PerfilUsuario(str, Enum):
    PACIENTE           = "paciente"
    PODOLOGO_ENFERMERO = "podologo_enfermero"
    INFECTOLOGO        = "infectologo"
    DIABETOLOGO        = "diabetologo"
    MEDICO_GENERAL     = "medico_general"


class NivelUrgencia(str, Enum):
    BAJO       = "bajo"       # 🟢 Podés esperar / Consulta programada
    MODERADO   = "moderado"   # 🟡 Consultá esta semana (24-72 hs)
    ALTO       = "alto"       # 🔴 Consultá hoy / 24-48 horas
    EMERGENCIA = "emergencia" # 🚨 Guardia médica inmediata


class DatosClinicosContexto(BaseModel):
    """Contexto clínico del paciente para enriquecer el análisis de IA."""
    localizacion_ulcera:     Optional[str]   = Field(None, description="Ej: antepié plantar derecho, talón")
    tiempo_evolucion:        Optional[str]   = Field(None, description="Ej: 3 semanas, 2 meses")
    diabetes_tipo:           Optional[str]   = Field(None, description="Tipo 1 / Tipo 2 / Otro")
    hba1c:                   Optional[float] = Field(None, ge=4.0, le=20.0, description="HbA1c en %")
    creatinina:              Optional[float] = Field(None, ge=0.2, le=15.0, description="Creatinina en mg/dL")
    fiebre:                  Optional[bool]  = Field(None, description="¿Tiene fiebre actual?")
    pulsos_presentes:        Optional[bool]  = Field(None, description="¿Pulsos pedios y tibiales presentes?")
    sensibilidad_conservada: Optional[bool]  = Field(None, description="¿Monofilamento 10g normal?")
    antibioticos_previos:    Optional[bool]  = Field(None, description="¿Recibió antibióticos en las últimas 4 semanas?")
    hospitalizacion_previa:  Optional[bool]  = Field(None, description="¿Hospitalización en el último año?")
    # Cuestionario post-foto (Curapp inspired)
    olor_presente:           Optional[bool]  = Field(None, description="¿La herida tiene mal olor?")
    exudado_cantidad:        Optional[str]   = Field(None, description="ninguno / escaso / moderado / abundante")
    dolor_en_herida:         Optional[bool]  = Field(None, description="¿Siente dolor en la herida?")
    nota_libre:              Optional[str]   = Field(None, max_length=500, description="Observación adicional")


class TriageInput(BaseModel):
    imagen_base64: str = Field(
        ...,
        description="Imagen de la herida codificada en base64 (JPEG o PNG)."
    )
    perfil_usuario: PerfilUsuario = Field(
        ...,
        description="Perfil del usuario (paciente, podologo_enfermero, infectologo, diabetologo, medico_general)."
    )
    datos_clinicos: DatosClinicosContexto = Field(
        default_factory=DatosClinicosContexto,
        description="Contexto clínico del paciente. Más datos = mejor análisis."
    )
    imagen_mime_type: str = Field(
        default="image/jpeg",
        description="Tipo MIME de la imagen: image/jpeg o image/png"
    )
    proveedor_ia: IAProvider = Field(
        default=IAProvider.AUTO,
        description="Proveedor de IA: auto (Gemini con fallback a Claude), gemini o claude."
    )
    api_key_override: Optional[str] = Field(
        None,
        description="API key opcional enviada en la petición para pruebas directas."
    )


class TriageOutput(BaseModel):
    perfil_consultado:  str
    proveedor_utilizado: str
    modelo_utilizado:   str
    tiempo_ms:          int
    analisis_ia:        str  = Field(..., description="Análisis clínico completo")
    nivel_urgencia:     Optional[str] = Field(None, description="bajo / moderado / alto / emergencia")
    color_semaforo:     Optional[str] = Field(None, description="verde / amarillo / rojo")
    disclaimer:         str  = Field(..., description="Aviso clínico obligatorio")


# ─────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS POR PERFIL
# ─────────────────────────────────────────────────────────────────────

SYSTEM_PROMPTS = {

    # ─── PACIENTE ────────────────────────────────────────────────────
    "paciente": """
Sos un asistente de salud especializado en el cuidado del pie diabético.
Hablás directamente con una persona que tiene diabetes y está preocupada por su pie.

TU MISIÓN: Ayudar a la persona a entender qué está viendo en su pie y si necesita
atención médica urgente, con urgencia media, o puede esperar su próxima consulta.

REGLAS DE COMUNICACIÓN:
- Usá lenguaje SIMPLE, sin términos médicos. Si usás alguno, explicalo entre paréntesis.
- Hablá de vos a vos, de forma empática, clara y directa.
- Nunca causes pánico innecesario, pero tampoco minimices señales graves.
- Si hay algo que te preocupa, decilo claramente.
- Máximo 200-250 palabras. Oraciones cortas.

ESTRUCTURA DE TU RESPUESTA (siempre en este orden):
1. Lo que ves (1-2 oraciones en lenguaje simple)
2. Nivel de urgencia: UNA de estas tres opciones con su ícono exacto:
   🟢 PODÉS ESPERAR — Atendelo en tu próxima consulta programada
   🟡 CONSULTÁ ESTA SEMANA — Llamá a tu médico o podólogo en los próximos días (24 a 72 horas)
   🔴 CONSULTÁ HOY — Buscá atención médica hoy mismo / concurrir a guardia
3. Qué hacer ahora (2-3 instrucciones concretas y seguras)
4. Una señal de alarma: "Si ves esto, buscá atención urgente: ..."
5. Un mensaje cálido de aliento.

NUNCA:
- Recetes medicamentos
- Digas diagnósticos médicos definitivos
- Uses palabras como necrosis, esfacelo, isquemia sin explicarlas
- Recomiendes automedicación o remedios caseros agresivos
""",

    # ─── PODÓLOGO / ENFERMERO ─────────────────────────────────────────
    "podologo_enfermero": """
Sos un asistente clínico especializado en pie diabético trabajando con un podólogo
o enfermero experto en curaciones de heridas crónicas.

TU MISIÓN: Analizar la herida y proporcionar una evaluación clínica estructurada
según la sistemática TIMERS que apoye la toma de decisiones en el punto de atención.

ESTRUCTURA DE TU RESPUESTA:

**EVALUACIÓN DEL LECHO DE LA HERIDA**
- Tejido predominante: [granulación / fibrina / esfacelo / necrosis seca / necrosis húmeda / mixto]
- Estimación visual: % aproximado por tipo de tejido
- Bordes: [activos y epitelizando / estancados / macerados / enrollados]
- Signos de infección local: [sí/no] — describir eritema, edema, calor local
- Exudado aparente: [ninguno / escaso / moderado / abundante]

**SISTEMÁTICA TIMERS**
- T (Tissue/Tejido no viable): [hallazgo y conducta de desbridamiento recomendada]
- I (Infection/Inflamación): [evaluación de biocarga e infección local]
- M (Moisture/Humedad): [balance de humedad: apósito absorbente vs hidratante]
- E (Edge/Bordes): [avance epitelial o barreras de cicatrización]
- R (Repair/Regeneración): [fase de cicatrización estimada]
- S (Social/Sistémico): [consideraciones de calzado y descarga]

**SUGERENCIA DE CONDUCTA & APÓSITO**
- Apósito primario y secundario sugerido
- Frecuencia de curación recomendada
- Recomendaciones de descarga (Off-loading)

Longitud: 250-350 palabras. Terminología clínica de enfermería/podología.
""",

    # ─── INFECTÓLOGO ──────────────────────────────────────────────────
    "infectologo": """
Sos un asistente clínico de infectología especializado en infecciones del pie diabético (DFI).
Trabajás con un infectólogo que necesita apoyo para la evaluación de la herida.

TU MISIÓN: Evaluar signos visuales de infección, severidad según clasificación IDSA/IWGDF,
y orientación de cobertura antibiótica empírica y criterios de hospitalización.

ESTRUCTURA DE TU RESPUESTA:

**SIGNOS VISUALES DE INFECCIÓN**
- Eritema perilesional: [extensión estimada en cm]
- Edema, induración y calor local
- Características del exudado (seroso, purulento, fétido)
- Sospecha de compromiso profundo (fascia, tendón, hueso / osteomielitis)

**CLASIFICACIÓN IDSA/IWGDF ESTIMADA**
- Nivel: [No infectada / Leve / Moderada / Grave] con justificación clínica.

**FACTORES DE RIESGO MICROBIOLÓGICOS**
- Probabilidad de SAMR, Pseudomonas aeruginosa, o flora mixta anaerobia.

**ORIENTACIÓN DE COBERTURA EMPÍRICA (Referencia IDSA 2023)**
- Esquema sugerido de primera línea
- Alternativa por alergias o ajuste renal
- Criterios de internación / desbridamiento quirúrgico urgente

Longitud: 300-400 palabras. Rigor infectológico.
""",

    # ─── DIABETÓLOGO ─────────────────────────────────────────────────
    "diabetologo": """
Sos un asistente clínico especializado en el manejo integral del pie diabético para diabetólogos.

TU MISIÓN: Integrar los hallazgos de imagen con el contexto metabólico y neuropático/vascular
para determinar clasificación Wagner, Texas, estrato IWGDF y pronóstico.

ESTRUCTURA DE TU RESPUESTA:

**CARACTERIZACIÓN DE LA ÚLCERA**
- Localización anatómica y mecanismo fisiopatológico (presión, cizallamiento, isquemia)
- Clasificación Wagner estimada (0 a 5)
- Clasificación Texas estimada (Grado 0-III, Estadio A-D)
- Estratificación de Riesgo IWGDF (Grupos 0–3)

**IMPACTO METABÓLICO & PRONÓSTICO**
- Correlación con niveles de HbA1c y micro/macroangiopatía
- Factores pronósticos de cicatrización vs riesgo de recidiva/amputación

**PLAN INTEGRAL MULTIDISCIPLINAR**
- Optimización glucémica y control de comorbilidades
- Indicación de interconsulta vascular o podológica
- Plan de descarga y seguimiento

Longitud: 300-400 palabras.
""",

    # ─── MÉDICO GENERAL ──────────────────────────────────────────────
    "medico_general": """
Sos un asistente clínico de apoyo para médicos generales o de atención primaria (CAPS / Centros de Salud).

TU MISIÓN: Proporcionar una evaluación clara y accionable con foco en detección de señales
de alarma y criterios precisos de derivación al especialista adecuado.

ESTRUCTURA DE TU RESPUESTA:

**QUÉ OBSERVO EN LA IMAGEN**
Descripción concisa de la lesión en términos médicos generales.

**NIVEL DE URGENCIA & DERIVACIÓN**
🟢 BAJO — Manejo ambulatorio en atención primaria, control programado.
🟡 MODERADO — Derivación a Podología/Enfermería especializada o Diabetología en 48-72h.
🔴 ALTO / EMERGENCIA — Derivación urgente a guardia / Infectología / Cirugía Vascular hoy.

**SEÑALES DE ALARMA PRESENTES**
Lista puntual de factores que justifican la conducta.

**MANEJO INICIAL EN EL CENTRO DE SALUD**
- Curación inicial segura mientras se concreta la derivación
- Qué estudios complementarios solicitar (Rx pie con sospecha ósea, lab, glucemia)
- Qué no hacer (contraindicaciones comunes)

Longitud: 200-300 palabras. Claro, estructurado y accionable.
""",
}


# ─────────────────────────────────────────────────────────────────────
# CONSTRUCTOR DEL PROMPT DE USUARIO
# ─────────────────────────────────────────────────────────────────────

def construir_user_prompt(perfil: PerfilUsuario, datos: DatosClinicosContexto) -> str:
    lineas = ["Por favor analizá esta fotografía de una lesión/pie de paciente con diabetes."]

    ctx = []
    if datos.localizacion_ulcera:
        ctx.append(f"Localización: {datos.localizacion_ulcera}")
    if datos.tiempo_evolucion:
        ctx.append(f"Tiempo de evolución: {datos.tiempo_evolucion}")
    if datos.diabetes_tipo:
        ctx.append(f"Tipo de diabetes: {datos.diabetes_tipo}")
    if datos.hba1c is not None:
        ctx.append(f"HbA1c: {datos.hba1c}%")
    if datos.creatinina is not None:
        ctx.append(f"Creatinina sérica: {datos.creatinina} mg/dL")
    if datos.fiebre is not None:
        ctx.append(f"Fiebre actual: {'SÍ' if datos.fiebre else 'NO'}")
    if datos.pulsos_presentes is not None:
        ctx.append(f"Pulsos distales (pedio/tibial): {'Presentes' if datos.pulsos_presentes else 'Ausentes o débiles'}")
    if datos.sensibilidad_conservada is not None:
        ctx.append(f"Sensibilidad protectora (Monofilamento 10g): {'Conservada' if datos.sensibilidad_conservada else 'Pérdida de sensibilidad (LOPS)'}")
    if datos.antibioticos_previos:
        ctx.append("Recibió antibióticos en las últimas 4 semanas: SÍ")
    if datos.hospitalizacion_previa:
        ctx.append("Hospitalización en el último año: SÍ")
    if datos.olor_presente is not None:
        ctx.append(f"Mal olor en la herida: {'SÍ, olor fétido' if datos.olor_presente else 'Sin mal olor'}")
    if datos.exudado_cantidad:
        ctx.append(f"Cantidad de exudado: {datos.exudado_cantidad}")
    if datos.dolor_en_herida is not None:
        ctx.append(f"Dolor referido en la lesión: {'SÍ' if datos.dolor_en_herida else 'NO (posible neuropatía)'}")
    if datos.nota_libre:
        ctx.append(f"Nota del profesional/paciente: {datos.nota_libre}")

    if ctx:
        lineas.append("\nINFORMACIÓN CLÍNICA Y ANTECEDENTES DEL PACIENTE:")
        for item in ctx:
            lineas.append(f"• {item}")

    lineas.append(
        "\nRespondé en español siguiendo estrictamente el rol y estructura definida para este perfil. "
        "Asegurate de incluir el nivel de urgencia adecuado."
    )

    return "\n".join(lineas)


# ─────────────────────────────────────────────────────────────────────
# MOTORES DE INFERENCIA
# ─────────────────────────────────────────────────────────────────────

def _inferir_gemini(datos: TriageInput, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """Inferencia con Google Gemini (2.5 Flash / 1.5 Pro)."""
    api_key = datos.api_key_override or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Variable de entorno GEMINI_API_KEY no configurada.")

    imagen_bytes = base64.b64decode(datos.imagen_base64)
    mime_type = datos.imagen_mime_type or "image/jpeg"

    # Intentar con el SDK moderno google-genai
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL_DEFAULT,
            contents=[
                types.Part.from_bytes(data=imagen_bytes, mime_type=mime_type),
                user_prompt,
            ],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=MAX_TOKENS,
                temperature=0.2,
            ),
        )
        return {
            "texto": response.text,
            "modelo": f"Google {GEMINI_MODEL_DEFAULT}",
            "proveedor": "Google Gemini",
        }
    except ImportError:
        # Fallback a google.generativeai si google-genai no está instalado
        import google.generativeai as genai_legacy
        genai_legacy.configure(api_key=api_key)
        
        modelo_nombre = "gemini-1.5-flash" if "2.5" in GEMINI_MODEL_DEFAULT else GEMINI_MODEL_DEFAULT
        model = genai_legacy.GenerativeModel(
            model_name=modelo_nombre,
            system_instruction=system_prompt,
            generation_config={"max_output_tokens": MAX_TOKENS, "temperature": 0.2}
        )
        
        img_part = {"mime_type": mime_type, "data": imagen_bytes}
        response = model.generate_content([img_part, user_prompt])
        return {
            "texto": response.text,
            "modelo": f"Google {modelo_nombre}",
            "proveedor": "Google Gemini",
        }


def _inferir_claude(datos: TriageInput, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """Inferencia con Anthropic Claude (3.7 / 3.5 Sonnet)."""
    api_key = datos.api_key_override or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Variable de entorno ANTHROPIC_API_KEY no configurada.")

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=CLAUDE_MODEL_DEFAULT,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": datos.imagen_mime_type,
                            "data": datos.imagen_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                ],
            }
        ],
    )

    texto = "".join(b.text for b in response.content if b.type == "text")
    return {
        "texto": texto,
        "modelo": f"Anthropic {response.model}",
        "proveedor": "Anthropic Claude",
    }


def _extraer_metadatos_urgencia(texto: str) -> Dict[str, Optional[str]]:
    """Extrae el nivel de semáforo y urgencia del texto para enriquecer la respuesta."""
    texto_lower = texto.lower()

    if "🔴" in texto or "consultá hoy" in texto_lower or "emergencia" in texto_lower or "guardia hoy" in texto_lower:
        return {"nivel_urgencia": "alto", "color_semaforo": "rojo"}
    elif "🟡" in texto or "consultá esta semana" in texto_lower or "moderado" in texto_lower or "próximos días" in texto_lower:
        return {"nivel_urgencia": "moderado", "color_semaforo": "amarillo"}
    elif "🟢" in texto or "podés esperar" in texto_lower or "bajo" in texto_lower or "próxima consulta" in texto_lower:
        return {"nivel_urgencia": "bajo", "color_semaforo": "verde"}
    
    return {"nivel_urgencia": "moderado", "color_semaforo": "amarillo"}


# ─────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL DE EJECUCIÓN
# ─────────────────────────────────────────────────────────────────────

def ejecutar_triage(datos: TriageInput) -> TriageOutput:
    """
    Ejecuta el triage multimodal con el proveedor seleccionado o con
    auto-fallback (Gemini -> Claude).
    """
    inicio = time.time()
    perfil_key = datos.perfil_usuario.value
    if perfil_key not in SYSTEM_PROMPTS:
        raise ValueError(f"Perfil '{perfil_key}' no soportado.")

    system_prompt = SYSTEM_PROMPTS[perfil_key]
    user_prompt = construir_user_prompt(datos.perfil_usuario, datos.datos_clinicos)

    resultado = None
    ultimo_error = None

    proveedores_a_intentar = []
    if datos.proveedor_ia == IAProvider.GEMINI:
        proveedores_a_intentar = ["gemini"]
    elif datos.proveedor_ia == IAProvider.CLAUDE:
        proveedores_a_intentar = ["claude"]
    else:  # AUTO
        proveedores_a_intentar = ["gemini", "claude"]

    for prov in proveedores_a_intentar:
        try:
            if prov == "gemini":
                resultado = _inferir_gemini(datos, system_prompt, user_prompt)
                break
            elif prov == "claude":
                resultado = _inferir_claude(datos, system_prompt, user_prompt)
                break
        except Exception as e:
            logger.warning(f"[Agente 7] Falló inferencia con {prov}: {e}")
            ultimo_error = e

    if not resultado:
        mensaje_error = f"Error al ejecutar triage con IA. Detalle: {str(ultimo_error)}"
        logger.error(f"[Agente 7] {mensaje_error}")
        raise HTTPException(status_code=502, detail=mensaje_error)

    tiempo_ms = int((time.time() - inicio) * 1000)
    meta = _extraer_metadatos_urgencia(resultado["texto"])

    return TriageOutput(
        perfil_consultado=perfil_key,
        proveedor_utilizado=resultado["proveedor"],
        modelo_utilizado=resultado["modelo"],
        tiempo_ms=tiempo_ms,
        analisis_ia=resultado["texto"],
        nivel_urgencia=meta["nivel_urgencia"],
        color_semaforo=meta["color_semaforo"],
        disclaimer=DISCLAIMER,
    )


# ─────────────────────────────────────────────────────────────────────
# ROUTER FASTAPI
# ─────────────────────────────────────────────────────────────────────

router_agente7 = APIRouter(prefix="/agentes", tags=["Agente 7 — Triage Multimodal IA"])


@router_agente7.post(
    "/triage-multimodal",
    response_model=TriageOutput,
    summary="Agente 7 — Triage Multimodal con Gemini y Claude",
)
def api_triage_multimodal(datos: TriageInput):
    """
    **Agente 7 — Triage Multimodal con Inteligencia Artificial**

    Analiza fotografías de lesiones y úlceras en pie diabético con IA de visión de última generación.
    Soporta **Google Gemini (2.5 Flash / Pro)** y **Anthropic Claude (3.7 / 3.5 Sonnet)**.
    """
    try:
        return ejecutar_triage(datos)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Agente 7] Error inesperado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al procesar el triage.")


@router_agente7.get(
    "/triage-multimodal/perfiles",
    summary="Listar perfiles clínicos disponibles",
)
def listar_perfiles():
    return {
        "perfiles": {
            "paciente": "Lenguaje empático, semáforo visual (🟢🟡🔴), qué hacer y señales de alarma",
            "podologo_enfermero": "Evaluación TIMERS completa, desbridamiento, apósitos y descarga",
            "infectologo": "Signos de infección, clasificación IDSA, sospecha de resistencia y ATB empírico",
            "diabetologo": "Wagner, Texas, IWGDF, control glucémico (HbA1c) y pronóstico integral",
            "medico_general": "Evaluación clara en atención primaria, manejo inicial y criterios de derivación",
        },
        "proveedores_soportados": ["gemini (Google)", "claude (Anthropic)", "auto (Híbrido con fallback)"],
        "disclaimer": DISCLAIMER,
    }
