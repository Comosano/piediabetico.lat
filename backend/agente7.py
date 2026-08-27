"""
PIEDIABETICO.LAT — Agente 7: Triage Multimodal con IA
======================================================
Versión 1.0 — Solo perfil PACIENTE (v1)
Los perfiles de profesionales se completan tras recibir
las respuestas de los cuestionarios clínicos.

Tecnología: Claude API (claude-sonnet-4-6) con visión multimodal
Uso: FastAPI endpoint POST /agentes/triage-multimodal

IMPORTANTE: Este agente es una herramienta de APOYO clínico.
No emite diagnósticos. No prescribe tratamientos.
Toda respuesta incluye disclaimer obligatorio y escala de urgencia
para facilitar la derivación apropiada.
"""

import anthropic
import base64
import logging
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CLIENTE ANTHROPIC
# ─────────────────────────────────────────────────────────────

def get_client() -> anthropic.Anthropic:
    """Inicializa el cliente de Anthropic. La API key viene de variable de entorno."""
    return anthropic.Anthropic()  # Lee ANTHROPIC_API_KEY del entorno


# ─────────────────────────────────────────────────────────────
# ENUMS Y MODELOS PYDANTIC
# ─────────────────────────────────────────────────────────────

class PerfilUsuario(str, Enum):
    PACIENTE        = "paciente"
    PODOLOGO        = "podologo"
    ENFERMERO       = "enfermero"
    INFECTOLOGO     = "infectologo"
    DIABETOLOGO     = "diabetologo"
    MEDICO_GENERAL  = "medico_general"


class NivelUrgencia(str, Enum):
    BAJO       = "bajo"       # Puede esperar turno programado
    MODERADO   = "moderado"   # Consulta esta semana
    ALTO       = "alto"       # Consulta en 24-48 horas
    EMERGENCIA = "emergencia" # Concurrir hoy a guardia


class TriageInput(BaseModel):
    perfil_usuario: PerfilUsuario = Field(
        ...,
        description="Rol del usuario que realiza la consulta"
    )
    imagen_base64: str = Field(
        ...,
        description="Foto de la herida codificada en base64 (JPEG o PNG)"
    )
    # Cuestionario post-foto (inspirado en Curapp)
    hay_fiebre: Optional[bool] = Field(
        default=None,
        description="¿El paciente tiene fiebre actual?"
    )
    hay_olor: Optional[bool] = Field(
        default=None,
        description="¿La herida tiene olor desagradable?"
    )
    exudado: Optional[str] = Field(
        default=None,
        description="Cantidad de exudado: ninguno / escaso / moderado / abundante"
    )
    tiempo_evolucion_dias: Optional[int] = Field(
        default=None,
        description="Días de evolución de la herida",
        ge=0, le=3650
    )
    # Datos clínicos adicionales (opcionales, mejoran el análisis)
    datos_clinicos_extra: Optional[str] = Field(
        default=None,
        description="Información clínica adicional en texto libre (ej: HbA1c, antibióticos previos)"
    )


class TriageOutput(BaseModel):
    nivel_urgencia: NivelUrgencia
    color_semaforo: str           # "verde" | "amarillo" | "rojo"
    titulo_respuesta: str
    analisis_visual: str          # Lo que la IA vio en la foto
    recomendacion_principal: str  # La acción más importante a tomar
    señales_alarma: list[str]     # Lista de señales preocupantes detectadas
    proximos_pasos: list[str]     # Pasos concretos ordenados
    cuando_ir_urgencias: str      # Cuándo debe ir a emergencias
    disclaimer: str               # Siempre presente


# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPTS POR PERFIL
# ─────────────────────────────────────────────────────────────

DISCLAIMER_BASE = (
    "Este análisis es una herramienta de orientación y apoyo. "
    "No reemplaza la evaluación presencial de un profesional de salud habilitado. "
    "Ante cualquier duda, consultá a tu médico o concurrí a un centro de salud."
)

# ── PERFIL PACIENTE ───────────────────────────────────────────────────────────
# El más importante de la v1. Lenguaje simple, empático, accionable.
# Sin tecnicismos. Foco en qué hacer, no en qué es.
# Calibrado para pacientes de LATAM con bajo acceso a especialistas.

SYSTEM_PROMPT_PACIENTE = """Sos un asistente de salud especializado en el cuidado del pie diabético. 
Tu misión es ayudar a personas con diabetes a entender el estado de su herida y saber qué hacer.

CÓMO DEBÉS RESPONDER:
- Usá un lenguaje muy simple y cálido, como si le hablaras a un familiar.
- Nunca uses términos médicos sin explicarlos de inmediato.
- Siempre decí QUÉ hacer, no solo qué está pasando.
- Sé honesto pero no alarmista. Si algo es grave, decilo claro pero sin asustar innecesariamente.
- Considerá que el paciente puede vivir lejos de un especialista y tener recursos limitados.

QUÉ ANALIZÁS EN LA FOTO:
1. ¿Hay signos de infección? (enrojecimiento alrededor, pus, calor, hinchazón)
2. ¿Cuánto mide aproximadamente la herida?
3. ¿Cómo se ve el tejido? (¿está limpio y rosado, o hay partes negras o amarillas?)
4. ¿Los bordes están mejorando o estancados?
5. ¿Hay alguna señal que requiera atención urgente?

FORMATO DE TU RESPUESTA (siempre este orden):
1. Una oración inicial que diga lo más importante que viste
2. Qué ves en la herida (explicado simple)
3. Señales de alarma si las hay (sé claro pero calmo)
4. Qué hacer ahora mismo (pasos concretos)
5. Cuándo ir a urgencias o guardia (criterios claros)
6. Un mensaje de aliento al final

NIVELES DE URGENCIA que podés asignar:
- BAJO: La herida parece estable, puede esperar turno programado
- MODERADO: Hay cambios que requieren ver a un profesional esta semana  
- ALTO: Necesita atención en las próximas 24-48 horas
- EMERGENCIA: Debe ir a guardia hoy mismo

SEÑALES DE EMERGENCIA (si ves cualquiera de estas → urgencia EMERGENCIA):
- Enrojecimiento que se expande rápido más allá de la herida
- Pus abundante o de color verde/marrón oscuro
- Piel negra o morada alrededor de la herida
- Herida que se extiende a hueso o tendón visible
- Líneas rojas que salen de la herida (sepsis)
- Combinado con fiebre alta que el paciente reporta

RECORDÁ SIEMPRE:
- No diagnosticás. Orientás.
- No prescribís medicamentos.
- Siempre recomendás ver a un profesional.
- El disclaimer clínico va siempre al final."""


# ── PERFIL MÉDICO GENERAL ─────────────────────────────────────────────────────
# Médico de atención primaria en ciudad pequeña, sin especialidad en pie diabético.
# Necesita criterio de derivación claro y fundamentado.
# Se completa con cuestionario de especialistas (v1 provisional).

SYSTEM_PROMPT_MEDICO_GENERAL = """Sos un asistente clínico especializado en pie diabético para médicos generalistas.
Tu rol es apoyar la toma de decisiones de derivación y manejo inicial.

CONTEXTO: El médico que consulta atiende en un centro de salud sin especialistas en pie diabético.
Necesita saber si puede manejar el caso localmente o debe derivar, y con qué urgencia.

QUÉ ANALIZÁS:
1. Signos clínicos de infección y su severidad (clasificación IDSA: leve/moderada/grave)
2. Estimación de clasificación Wagner (0-5) si es posible por imagen
3. Señales vasculares (piel perilesional, temperatura aparente, coloración)
4. Estado del lecho de la herida (tejido viable vs no viable)
5. Criterios de internación presentes o no

FORMATO DE RESPUESTA:
1. Impresión clínica inicial (2-3 oraciones)
2. Hallazgos relevantes por imagen
3. Clasificación orientativa (Wagner estimado, severidad IDSA si aplica)
4. Criterio de derivación y urgencia
5. Manejo inicial recomendado mientras se concreta la derivación
6. Qué información adicional necesitás del paciente

NIVELES DE DERIVACIÓN:
- BAJO: Manejo ambulatorio local posible, control en 1 semana
- MODERADO: Derivación a podología o infectología en menos de 72 horas
- ALTO: Derivación urgente hoy o mañana
- EMERGENCIA: Internación directa, no diferible

Respondé con terminología médica apropiada para un colega."""


# ── PERFILES PROFESIONALES ESPECIALIZADOS ─────────────────────────────────────
# Estos prompts se completan con las respuestas de los cuestionarios clínicos.
# Por ahora tienen versiones funcionales provisionales.

SYSTEM_PROMPT_PODOLOGO = """Sos un asistente clínico especializado en pie diabético para podólogos y enfermeros especializados en heridas.

QUÉ ANALIZÁS EN LA IMAGEN:
1. Estado del lecho de la herida según TIMERS (Tejido, Infección, Moisture/humedad, Edge/bordes)
2. Composición tisular estimada: % granulación, % fibrina/esfacelo, % necrosis
3. Estado de los bordes: avanzando, enrollados, macerados, epitelizando
4. Cantidad y tipo de exudado aparente
5. Signos de infección local: eritema perilesional, calor, edema, secreción
6. Deformidades visibles relevantes para el off-loading

FORMATO DE RESPUESTA:
1. Evaluación TIMERS punto por punto
2. Estimación de composición tisular del lecho
3. Estado de los bordes y la piel perilesional
4. Sugerencia de apósito y frecuencia de curación (referencia educativa)
5. Indicaciones de off-loading si son visibles
6. Señales que requieren escalar a médico o infectólogo
7. Próxima evaluación recomendada

Usá terminología clínica de enfermería y podología. Sé preciso y sistemático."""


SYSTEM_PROMPT_INFECTOLOGO = """Sos un asistente clínico especializado en infecciones de pie diabético para infectólogos.

CONTEXTO: El infectólogo que consulta ya tiene acceso a los datos clínicos del paciente 
y quiere un análisis visual complementario de la imagen de la herida.

QUÉ ANALIZÁS:
1. Signos de infección y su extensión: eritema, celulitis, linfangitis
2. Características del exudado visible: purulento, seroso, hemático
3. Profundidad aparente: superficial, subcutánea, fascia, hueso/tendón
4. Necrosis: húmeda, seca, extensión estimada
5. Señales de infección sistémica que la imagen pueda sugerir
6. Clasificación IDSA orientativa por imagen: leve/moderada/grave/amenaza de extremidad

FORMATO DE RESPUESTA:
1. Hallazgos de imagen relevantes para infectología
2. Clasificación IDSA orientativa con justificación visual
3. Señales de osteomielitis subyacente por imagen
4. Cobertura empírica sugerida según hallazgos (referencia educativa IDSA/IWGDF)
5. Estudios complementarios recomendados
6. Criterios de internación si aplica

Respondé con rigor clínico. Citá las guías cuando sea relevante."""


SYSTEM_PROMPT_DIABETOLOGO = """Sos un asistente clínico especializado en pie diabético para diabetólogos.

CONTEXTO: El diabetólogo tiene acceso al historial metabólico del paciente 
y consulta sobre los hallazgos de imagen de la úlcera.

QUÉ ANALIZÁS:
1. Características de la úlcera que orientan a etiología: neuropática vs isquémica vs neuroisquémica
2. Localización y morfología: relacionar con zonas de presión vs isquemia
3. Estado del tejido perilesional: callosidades, piel seca, atrofia
4. Signos de neuropatía o vasculopatía periférica visibles
5. Estimación de clasificación Wagner y Texas por imagen
6. Señales de Charcot activo si aplica

FORMATO DE RESPUESTA:
1. Etiología orientativa por imagen (neuropática/isquémica/neuroisquémica)
2. Clasificación Wagner y Texas estimadas
3. Correlación con estado metabólico si el médico proveyó datos
4. Impacto del control glucémico en la evolución esperada
5. Indicaciones de evaluación vascular (si aplica)
6. Frecuencia de seguimiento recomendada según riesgo

Integrá el análisis de imagen con la perspectiva metabólica del manejo integral."""


# Mapa de prompts por perfil
SYSTEM_PROMPTS = {
    PerfilUsuario.PACIENTE:       SYSTEM_PROMPT_PACIENTE,
    PerfilUsuario.PODOLOGO:       SYSTEM_PROMPT_PODOLOGO,
    PerfilUsuario.ENFERMERO:      SYSTEM_PROMPT_PODOLOGO,      # Mismo prompt que podólogo en v1
    PerfilUsuario.INFECTOLOGO:    SYSTEM_PROMPT_INFECTOLOGO,
    PerfilUsuario.DIABETOLOGO:    SYSTEM_PROMPT_DIABETOLOGO,
    PerfilUsuario.MEDICO_GENERAL: SYSTEM_PROMPT_MEDICO_GENERAL,
}


# ─────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL PROMPT DE USUARIO
# ─────────────────────────────────────────────────────────────

def _construir_prompt_usuario(datos: TriageInput) -> str:
    """
    Construye el mensaje del usuario combinando la imagen con
    el cuestionario post-foto y los datos clínicos adicionales.
    """
    partes = ["Analizá esta foto de la herida."]

    # Datos del cuestionario post-foto
    if datos.hay_fiebre is not None:
        partes.append(f"Fiebre actual: {'SÍ' if datos.hay_fiebre else 'NO'}.")
    if datos.hay_olor is not None:
        partes.append(f"Olor en la herida: {'SÍ, hay olor desagradable' if datos.hay_olor else 'NO hay olor'}.")
    if datos.exudado:
        partes.append(f"Cantidad de exudado: {datos.exudado}.")
    if datos.tiempo_evolucion_dias is not None:
        partes.append(f"Tiempo de evolución de la herida: {datos.tiempo_evolucion_dias} días.")
    if datos.datos_clinicos_extra:
        partes.append(f"Información clínica adicional: {datos.datos_clinicos_extra}")

    # Instrucción de formato de respuesta
    partes.append(
        "\nRespondé en español. "
        "Determiná el nivel de urgencia (bajo/moderado/alto/emergencia). "
        "Incluí siempre un disclaimer clínico al final."
    )

    return " ".join(partes)


# ─────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL DE TRIAGE
# ─────────────────────────────────────────────────────────────

def ejecutar_triage(datos: TriageInput) -> dict:
    """
    Ejecuta el análisis multimodal con Claude Vision.
    Retorna un dict con la respuesta estructurada.
    """
    client = get_client()
    system_prompt = SYSTEM_PROMPTS[datos.perfil_usuario]

    prompt_usuario = _construir_prompt_usuario(datos)

    logger.info(
        f"[Agente 7] Ejecutando triage — perfil: {datos.perfil_usuario.value}, "
        f"fiebre: {datos.hay_fiebre}, olor: {datos.hay_olor}, "
        f"exudado: {datos.exudado}, evolución: {datos.tiempo_evolucion_dias}d"
    )

    # Llamada a Claude con visión
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": datos.imagen_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt_usuario,
                    },
                ],
            }
        ],
    )

    respuesta_texto = response.content[0].text
    logger.info(f"[Agente 7] Respuesta generada — tokens usados: {response.usage.output_tokens}")

    return {
        "perfil_usuario": datos.perfil_usuario.value,
        "respuesta_clinica": respuesta_texto,
        "tokens_usados": response.usage.output_tokens,
        "modelo": response.model,
        "disclaimer": DISCLAIMER_BASE,
    }


# ─────────────────────────────────────────────────────────────
# ENDPOINT FASTAPI
# ─────────────────────────────────────────────────────────────

# Este bloque se importa desde main.py así:
# from agente7 import router_agente7
# app.include_router(router_agente7)

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel as PydanticBaseModel

router_agente7 = APIRouter(tags=["Agente 7 — Triage Multimodal IA"])


class TriageRequest(PydanticBaseModel):
    perfil_usuario: PerfilUsuario
    imagen_base64: str = Field(..., description="Imagen en base64 (JPEG/PNG)")
    hay_fiebre: Optional[bool] = None
    hay_olor: Optional[bool] = None
    exudado: Optional[str] = Field(default=None, pattern="^(ninguno|escaso|moderado|abundante)$")
    tiempo_evolucion_dias: Optional[int] = Field(default=None, ge=0, le=3650)
    datos_clinicos_extra: Optional[str] = None


class TriageResponse(PydanticBaseModel):
    perfil_usuario: str
    respuesta_clinica: str
    tokens_usados: int
    modelo: str
    disclaimer: str


@router_agente7.post(
    "/agentes/triage-multimodal",
    response_model=TriageResponse,
    summary="Agente 7 — Triage multimodal con Claude Vision",
)
def api_triage_multimodal(request: TriageRequest):
    """
    **Agente 7 — Triage Multimodal con IA**

    Analiza una fotografía de herida de pie diabético y genera
    un análisis clínico adaptado al perfil del usuario:

    - **paciente**: Lenguaje simple, qué hacer, cuándo ir a urgencias
    - **podologo / enfermero**: Evaluación TIMERS, apósitos, off-loading
    - **infectologo**: Clasificación IDSA, profundidad, cobertura empírica
    - **diabetologo**: Etiología, Wagner/Texas, correlación metabólica
    - **medico_general**: Criterio de derivación y manejo inicial

    **Importante:** Herramienta de apoyo clínico. No reemplaza la evaluación presencial.

    **Cuestionario post-foto (mejora el análisis):**
    - hay_fiebre: ¿Fiebre actual?
    - hay_olor: ¿Olor desagradable?
    - exudado: ninguno / escaso / moderado / abundante
    - tiempo_evolucion_dias: Días de evolución
    - datos_clinicos_extra: Texto libre con datos adicionales
    """
    try:
        datos = TriageInput(
            perfil_usuario=request.perfil_usuario,
            imagen_base64=request.imagen_base64,
            hay_fiebre=request.hay_fiebre,
            hay_olor=request.hay_olor,
            exudado=request.exudado,
            tiempo_evolucion_dias=request.tiempo_evolucion_dias,
            datos_clinicos_extra=request.datos_clinicos_extra,
        )
        resultado = ejecutar_triage(datos)
        return TriageResponse(**resultado)

    except anthropic.APIConnectionError:
        logger.error("[Agente 7] Error de conexión con Anthropic API")
        raise HTTPException(
            status_code=503,
            detail="No se pudo conectar con el servicio de IA. Intentá en unos minutos."
        )
    except anthropic.RateLimitError:
        logger.error("[Agente 7] Rate limit de Anthropic API")
        raise HTTPException(
            status_code=429,
            detail="Límite de consultas alcanzado. Intentá en unos segundos."
        )
    except Exception as e:
        logger.error(f"[Agente 7] Error inesperado: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno en el análisis de imagen: {str(e)}"
        )


# ─────────────────────────────────────────────────────────────
# USO DESDE MAIN.PY
# ─────────────────────────────────────────────────────────────
#
# En main.py agregar estas dos líneas:
#
#   from agente7 import router_agente7
#   app.include_router(router_agente7)
#
# El endpoint queda disponible en:
#   POST /agentes/triage-multimodal
#   Documentación interactiva: /docs
#
# ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # Test rápido de que los prompts cargan correctamente
    print("Perfiles disponibles:")
    for perfil, prompt in SYSTEM_PROMPTS.items():
        palabras = len(prompt.split())
        print(f"  {perfil.value:20s} — {palabras} palabras en el system prompt")
    print("\nAgente 7 listo para integrar en main.py")
