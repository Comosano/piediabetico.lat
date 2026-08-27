import os
import sys
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List
from enum import Enum

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from pubmed_agent import PubMedScraperAgent
    from redactor_agent import RedactorAgent
    from pdf_agent import PDFCompilerAgent
except ImportError as e:
    logger.error(f"Error al importar módulos de agentes locales: {e}")
    PubMedScraperAgent = None
    RedactorAgent = None
    PDFCompilerAgent = None

app = FastAPI(
    title="Ecosistema de Pie Diabético - Orquestador API",
    description="Backend unificado con agentes clínicos para Latinoamérica.",
    version="1.1.0"
)

DISCLAIMER_EDUCATIVO = (
    "AVISO: Esta sugerencia es una herramienta de referencia educativa basada en guías "
    "IWGDF 2023. No reemplaza el criterio clínico del profesional habilitado."
)

# =====================================================================
# AGENTE 8 — IWGDF (ya existía)
# =====================================================================

class IWGDFInput(BaseModel):
    historia_ulcera: bool = Field(..., description="Antecedente de úlcera previa en el pie")
    historia_amputacion: bool = Field(..., description="Antecedente de amputación en extremidades inferiores")
    insuficiencia_renal_terminal: bool = Field(..., description="Paciente en diálisis o eGFR < 15")
    perdida_sensibilidad_lops: bool = Field(..., description="Monofilamento 10g anormal (menos de 8/10 puntos)")
    enfermedad_arterial_pad: bool = Field(..., description="Pulsos pedios/tibiales ausentes o ITB < 0.9")
    deformidad_pie: bool = Field(..., description="Dedos en garra, juanetes o artropatía de Charcot activa")

class IWGDFOutput(BaseModel):
    grupo_riesgo: int
    frecuencia_inspeccion: str
    tipo_descarga_calzado: str
    disclaimer: str

@app.post("/agentes/iwgdf", response_model=IWGDFOutput, tags=["Calculadoras Clínicas"])
def api_agente_iwgdf(datos: IWGDFInput):
    """
    Agente 8 — Estratificación preventiva IWGDF.
    Clasifica pacientes sin úlcera activa en grupos de riesgo 0 a 3.
    Referencia educativa con disclaimer clínico.
    """
    if datos.historia_ulcera or datos.historia_amputacion or datos.insuficiencia_renal_terminal:
        return IWGDFOutput(
            grupo_riesgo=3,
            frecuencia_inspeccion="Cada 1 a 3 meses por un equipo multidisciplinar especializado.",
            tipo_descarga_calzado="Calzado terapéutico a medida con plantillas de descarga activa personalizadas.",
            disclaimer=DISCLAIMER_EDUCATIVO
        )
    if (datos.perdida_sensibilidad_lops and datos.enfermedad_arterial_pad) or \
       (datos.perdida_sensibilidad_lops and datos.deformidad_pie) or \
       (datos.enfermedad_arterial_pad and datos.deformidad_pie):
        return IWGDFOutput(
            grupo_riesgo=2,
            frecuencia_inspeccion="Cada 2 a 3 meses por especialista en pie diabético o podología.",
            tipo_descarga_calzado="Calzado terapéutico extra-profundo con plantillas termoconformadas.",
            disclaimer=DISCLAIMER_EDUCATIVO
        )
    if datos.perdida_sensibilidad_lops or datos.enfermedad_arterial_pad:
        return IWGDFOutput(
            grupo_riesgo=1,
            frecuencia_inspeccion="Cada 3 a 6 meses por enfermería especializada o podología.",
            tipo_descarga_calzado="Calzado de horma ancha sin costuras internas, evaluado por especialista.",
            disclaimer=DISCLAIMER_EDUCATIVO
        )
    return IWGDFOutput(
        grupo_riesgo=0,
        frecuencia_inspeccion="Anual (preventivo) por médico de atención primaria.",
        tipo_descarga_calzado="Calzado comercial cómodo de horma ancha. Inspección diaria por el paciente.",
        disclaimer=DISCLAIMER_EDUCATIVO
    )

# =====================================================================
# AGENTE 9 — TIMERS (ya existía)
# =====================================================================

class TIMERSInput(BaseModel):
    tejido_no_viable: bool = Field(..., description="Esfacelo, fibrina o necrosis en el lecho")
    infeccion_inflamacion: bool = Field(..., description="Eritema > 0.5cm, calor, secreción fétida")
    humedad_exudado_alto: bool = Field(..., description="Humedad excesiva o exudado abundante")
    bordes_estancados: bool = Field(..., description="Bordes enrollados, engrosados o sin avance")

class TIMERSOutput(BaseModel):
    conducta_desbridamiento: str
    apositivo_sugerido: str
    frecuencia_curacion: str
    disclaimer: str

@app.post("/agentes/timers", response_model=TIMERSOutput, tags=["Calculadoras Clínicas"])
def api_agente_timers(datos: TIMERSInput):
    """
    Agente 9 — Recomendador clínico TIMERS.
    Sugiere desbridamiento y apósitos según la biología de la úlcera.
    Referencia educativa con disclaimer clínico.
    """
    conducta = "Limpieza con solución salina o agua destilada estéril."
    apositivo = "Gasa estéril con solución fisiológica (mantenimiento básico)."
    frecuencia = "Cada 24 a 48 horas."

    if datos.tejido_no_viable:
        conducta = "Desbridamiento cortante activo o enzimático con colagenasa."
        apositivo = "Colagenasa en ungüento (ej. Santyl) o hidrogel para autólisis."

    if datos.infeccion_inflamacion:
        apositivo = "Apósitos bacteriostáticos con plata nanocristalina o DACC."
        frecuencia = "Cada 24 horas."
        if datos.humedad_exudado_alto:
            apositivo = "Espuma de poliuretano (Foam) con plata para control de humedad."
    elif datos.humedad_exudado_alto:
        apositivo = "Alginato de calcio o hidrocoloides absorbentes de alta capacidad."
        frecuencia = "Cada 48 a 72 horas según saturación."

    if datos.bordes_estancados:
        conducta += " + Estimulación mecánica de bordes o apósitos moduladores de metaloproteinasas (MMPs)."

    return TIMERSOutput(
        conducta_desbridamiento=conducta,
        apositivo_sugerido=apositivo,
        frecuencia_curacion=frecuencia,
        disclaimer=DISCLAIMER_EDUCATIVO
    )

# =====================================================================
# AGENTE 10 — OFF-LOADING (NUEVO)
# =====================================================================

class LocalizacionUlcera(str, Enum):
    ANTEPIE_PLANTAR  = "antepie_plantar"
    MEDIOPIE_PLANTAR = "mediopie_plantar"
    TALON            = "talon"
    DIGITAL          = "digital"
    DORSO_O_MALEOLAR = "dorso_o_maleolar"

class PieAfectado(str, Enum):
    DERECHO   = "derecho"
    IZQUIERDO = "izquierdo"
    BILATERAL = "bilateral"

class DeformidadAsociada(str, Enum):
    NINGUNA        = "ninguna"
    DEDOS_EN_GARRA = "dedos_en_garra"
    HALLUX_VALGUS  = "hallux_valgus"
    CHARCOT_CRONICO= "charcot_cronico"

class OffloadingInput(BaseModel):
    localizacion: LocalizacionUlcera = Field(
        ..., description="Localización anatómica de la úlcera"
    )
    pie_afectado: PieAfectado = Field(
        ..., description="Pie afectado por la úlcera"
    )
    isquemia_severa: bool = Field(
        default=False,
        description="ITB < 0.5 o pulsos distales ausentes"
    )
    infeccion_activa_frecuente: bool = Field(
        default=False,
        description="Infección moderada/grave que requiere curaciones diarias"
    )
    riesgo_caidas_alto: bool = Field(
        default=False,
        description="Fragilidad extrema, ataxia o historial de caídas"
    )
    deformidad: DeformidadAsociada = Field(
        default=DeformidadAsociada.NINGUNA,
        description="Deformidad estructural del pie"
    )
    peso_mayor_90kg: bool = Field(
        default=False,
        description="Peso corporal mayor a 90 kg (calibra densidad EVA)"
    )

class OffloadingOutput(BaseModel):
    dispositivo_primera_linea: str
    dispositivo_alternativo: str
    justificacion_iwgdf: str
    materiales_ortopodologicos: List[str]
    compensacion_postural: List[str]
    advertencias_seguridad: List[str]
    contraindicacion_dispositivo_fijo: bool
    motivos_contraindicacion: List[str]
    disclaimer: str


def _calcular_offloading(datos: OffloadingInput) -> OffloadingOutput:
    """Motor de reglas determinista basado en IWGDF 2023."""

    # Determinar contraindicaciones para dispositivo no removible
    motivos_contra = []
    if datos.isquemia_severa:
        motivos_contra.append("Isquemia severa (ITB < 0.5 o pulsos ausentes)")
    if datos.infeccion_activa_frecuente:
        motivos_contra.append("Infección activa que requiere curaciones diarias")
    if datos.riesgo_caidas_alto:
        motivos_contra.append("Alto riesgo de caídas documentado")

    contraindicacion_fijo = len(motivos_contra) > 0

    # Pie sano para alza contralateral
    if datos.pie_afectado == PieAfectado.BILATERAL:
        pie_sano_texto = "ambos pies (prescripción bilateral especializada)"
    elif datos.pie_afectado == PieAfectado.DERECHO:
        pie_sano_texto = "pie izquierdo (sano)"
    else:
        pie_sano_texto = "pie derecho (sano)"

    # Densidad EVA según peso
    densidad_eva = "alta densidad (300 kg/m³)" if datos.peso_mayor_90kg else "densidad media (220 kg/m³)"

    # ── ANTEPIÉ Y MEDIOPIÉ PLANTAR ──────────────────────────────
    if datos.localizacion in [LocalizacionUlcera.ANTEPIE_PLANTAR, LocalizacionUlcera.MEDIOPIE_PLANTAR]:
        if not contraindicacion_fijo:
            disp_1   = "Bota Walker Alta NO Removible (bloqueada con precinto de seguridad) o Yeso de Contacto Total (TCC)"
            disp_alt = "Bota Walker Alta Removible con plantilla conformada (solo si hay intolerancia documentada al fijado)"
            justif   = ("IWGDF 2023 — Recomendación Fuerte: El dispositivo no removible garantiza "
                        "una reducción del 85% del pico de presión plantar y adherencia continua. "
                        "Es el Gold Standard para úlceras plantares de antepié y mediopié.")
        else:
            disp_1   = "Bota Walker Alta Removible con plantilla de descarga fenestrada"
            disp_alt = "Zapato quirúrgico de descarga de antepié (cuña invertida de Barouk)"
            justif   = (f"IWGDF 2023: Dispositivo removible indicado por contraindicaciones presentes: "
                        f"{'; '.join(motivos_contra)}.")

        materiales = [
            f"Plantilla multicapa: base EVA {densidad_eva} con cubierta de Plastazote de 6 mm.",
            "Descarga selectiva: fenestración circular bajo la zona de hiperapoyo identificada.",
            "Fieltro semicomprimido adhesivo de 7 mm en herradura, colocado perilesional en la piel.",
        ]

    # ── TALÓN / RETROPIÉ ────────────────────────────────────────
    elif datos.localizacion == LocalizacionUlcera.TALON:
        disp_1   = "Bota Walker con cuña posterior o ventana de descarga total de talón"
        disp_alt = "Calzado ortopédico de descarga posterior o Yeso TCC con cámara de aire en talón"
        justif   = ("IWGDF 2023: La desgravitación completa del retropié es obligatoria para anular "
                    "la presión vertical directa sobre el talón. Sin descarga completa no hay cicatrización.")
        materiales = [
            "Talonera de silicona con orificio fenestrado central bajo la úlcera.",
            "Almohadillado de protección en tendón de Aquiles para prevenir úlceras secundarias.",
            "Almohadilla antiescaras para descarga completa de talón durante el reposo en cama.",
        ]

    # ── DEDOS / INTERDIGITAL ─────────────────────────────────────
    elif datos.localizacion == LocalizacionUlcera.DIGITAL:
        disp_1   = "Calzado postquirúrgico extra-profundo con puntera ancha + Ortesis de silicona digital a medida"
        disp_alt = "Zapato de descarga con corte rígido y puntera abierta"
        justif   = ("IWGDF 2023: Eliminación del conflicto de roce con el calzado convencional "
                    "y redistribución de la carga metatarsiana mediante ortesis digital.")
        materiales = [
            "Ortesis de silicona vulcanizada a medida (tipo omega o separador interdigital).",
            "Fieltro de 3 mm de protección apical si hay roce distal activo.",
        ]
        if datos.deformidad == DeformidadAsociada.DEDOS_EN_GARRA:
            materiales.append(
                "Considerar Tenotomía Flexora Percutánea menor para prevenir recidivas "
                "(evaluación quirúrgica recomendada)."
            )

    # ── DORSO / MALEOLAR ─────────────────────────────────────────
    else:
        disp_1   = "Calzado terapéutico a medida con corte blando (lycra autoexpandible) sin costuras internas"
        disp_alt = "Sandalia terapéutica con tiras de velcro ajustables sobre la lesión"
        justif   = ("IWGDF 2023: Reducción del roce mecánico directo sobre prominencias óseas "
                    "dorsales o maleolares mediante calzado de corte blando adaptado.")
        materiales = [
            "Apósito de interfase hidrocelular fino de protección perilesional.",
        ]

    # ── COMPENSACIÓN POSTURAL (SIEMPRE OBLIGATORIA) ──────────────
    compensacion = [
        f"Alza de nivelación pélvica en el {pie_sano_texto}: compensar la altura del dispositivo "
        f"para prevenir lumbalgias, asimetría de marcha y sobrecarga de rodilla contralateral.",
    ]
    if datos.pie_afectado == PieAfectado.BILATERAL:
        compensacion.append(
            "Caso bilateral: derivación urgente a ortopedia o rehabilitación para plan de descarga especializado."
        )

    # ── ADVERTENCIAS DE SEGURIDAD ────────────────────────────────
    advertencias = [
        "Prohibición estricta de deambular descalzo o en medias, incluso dentro del domicilio.",
        "Revisión semanal de puntos de roce secundario: cresta tibial, maléolos y base de dedos.",
    ]
    if datos.isquemia_severa:
        advertencias.append(
            "Isquemia severa presente: derivación urgente a cirugía vascular antes de iniciar off-loading."
        )
    if datos.deformidad == DeformidadAsociada.CHARCOT_CRONICO:
        advertencias.append(
            "Pie de Charcot crónico: requiere calzado ortopédico a medida de horma de Charcot. "
            "No usar botas Walker estándar sin adaptación especializada."
        )

    return OffloadingOutput(
        dispositivo_primera_linea=disp_1,
        dispositivo_alternativo=disp_alt,
        justificacion_iwgdf=justif,
        materiales_ortopodologicos=materiales,
        compensacion_postural=compensacion,
        advertencias_seguridad=advertencias,
        contraindicacion_dispositivo_fijo=contraindicacion_fijo,
        motivos_contraindicacion=motivos_contra,
        disclaimer=DISCLAIMER_EDUCATIVO
    )


@app.post(
    "/agentes/offloading",
    response_model=OffloadingOutput,
    tags=["Calculadoras Clínicas"],
    summary="Agente 10 — Prescripción de Descarga Biomecánica (Off-loading)",
)
def api_agente_offloading(datos: OffloadingInput):
    """
    **Agente 10 — Prescripción de Descarga Biomecánica (Off-loading)**

    Determina el dispositivo de descarga más adecuado para úlceras de pie diabético
    según las guías IWGDF 2023. Incluye:

    - Jerarquía terapéutica IWGDF (Gold Standard → alternativas)
    - Detección automática de contraindicaciones para dispositivos no removibles
    - Especificación de materiales ortopodológicos (densidad EVA, Plastazote, fieltros)
    - Compensación postural obligatoria (alza contralateral)
    - Advertencias de seguridad específicas por caso

    **Disclaimer:** Herramienta de referencia educativa. No reemplaza el criterio clínico.
    """
    try:
        resultado = _calcular_offloading(datos)
        logger.info(
            f"[Agente 10] Off-loading calculado — "
            f"localización: {datos.localizacion.value}, "
            f"contraindicación fijo: {resultado.contraindicacion_dispositivo_fijo}"
        )
        return resultado
    except Exception as e:
        logger.error(f"[Agente 10] Error en cálculo de off-loading: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno en el cálculo: {str(e)}")


# =====================================================================
# AGENTE 11 — ANTIBIÓTICOS (ya existía)
# =====================================================================

class AntibioticInput(BaseModel):
    edad: int = Field(..., ge=18, le=120)
    peso_kg: float = Field(..., ge=30, le=250)
    creatinina_serica: float = Field(..., ge=0.2, le=15.0, description="Creatinina sérica en mg/dL")
    sexo: str = Field(..., pattern="^(M|F)$", description="M para Masculino, F para Femenino")
    severidad_infeccion: str = Field(..., pattern="^(leve|moderada|grave)$")
    riesgo_multirresistencia: bool = Field(False, description="Sospecha de SAMR o Pseudomonas")

class AntibioticOutput(BaseModel):
    egfr_calculado: float
    esquema_empirico: str
    dosis_ajustada: str
    advertencias_nefrotoxicidad: str
    disclaimer: str

@app.post("/agentes/antibioticos", response_model=AntibioticOutput, tags=["Calculadoras Clínicas"])
def api_agente_antibioticos(datos: AntibioticInput):
    """
    Agente 11 — Ajustador de Antimicrobianos IDSA/IWGDF.
    Sugiere esquemas empíricos y ajusta dosis por Cockcroft-Gault.
    Referencia educativa con disclaimer clínico.
    """
    factor_sexo = 0.85 if datos.sexo == "F" else 1.0
    egfr = ((140 - datos.edad) * datos.peso_kg) / (72 * datos.creatinina_serica) * factor_sexo

    esquema = "Cefalexina 500mg oral c/6h o Amoxicilina-Clavulánico 875/125mg oral c/12h"
    dosis = "Dosis estándar de adulto (sin ajuste necesario)."
    advertencia = "Monitorear función hepática e hidratación general."

    if datos.severidad_infeccion == "leve":
        if datos.riesgo_multirresistencia:
            esquema = "Trimetoprima-Sulfametoxazol (TMP-SMX) 160/800mg oral c/12h (cobertura SAMR)"
            if egfr < 30:
                dosis = "TMP-SMX: Reducir a 80/400mg c/12h."
                advertencia = "Ajuste renal crítico por eGFR < 30 mL/min para TMP-SMX."

    elif datos.severidad_infeccion == "moderada":
        esquema = "Ampicilina-Sulbactam 1.5g a 3g IV c/6h o Ceftriaxona 1g a 2g IV c/24h"
        if datos.riesgo_multirresistencia:
            esquema = "Piperacilina-Tazobactam 4.5g IV c/6h + Vancomicina IV ajustada por niveles"
            if 15 <= egfr < 40:
                dosis = "Pip-Taz: Reducir a 3.375g IV c/6h."
                advertencia = "Ajuste renal activo por insuficiencia renal moderada."
            elif egfr < 15:
                dosis = "Pip-Taz: 2.25g IV c/8h o Meropenem 500mg IV c/24h."
                advertencia = "Alerta extrema: eGFR < 15. Evitar nefrotóxicos adicionales."

    elif datos.severidad_infeccion == "grave":
        esquema = "Meropenem 1g IV c/8h + Linezolid 600mg IV c/12h"
        if egfr < 50:
            if 26 <= egfr <= 50:
                dosis = "Meropenem: 1g IV c/12h."
            elif 10 <= egfr <= 25:
                dosis = "Meropenem: 500mg IV c/12h."
            else:
                dosis = "Meropenem: 500mg IV c/24h."
            advertencia = "Ajuste renal crítico para Meropenem en infección grave."

    return AntibioticOutput(
        egfr_calculado=round(egfr, 2),
        esquema_empirico=esquema,
        dosis_ajustada=dosis,
        advertencias_nefrotoxicidad=advertencia,
        disclaimer=DISCLAIMER_EDUCATIVO
    )

# =====================================================================
# ENDPOINT: PIPELINE CIENTÍFICO SEMANAL (ya existía)
# =====================================================================

def task_orquestador_sync_semanal():
    logger.info("--- [ORQUESTADOR] Iniciando sincronización semanal ---")
    if PubMedScraperAgent is not None:
        scraper = PubMedScraperAgent()
        if not scraper.execute_weekly_sync():
            logger.error("[ORQUESTADOR] Error en PubMed. Abortando.")
            return
    if RedactorAgent is not None:
        redactor = RedactorAgent()
        if not redactor.execute_translation_pipeline():
            logger.error("[ORQUESTADOR] Error en Redactor. Abortando.")
            return
    if PDFCompilerAgent is not None:
        compiler = PDFCompilerAgent()
        if not compiler.compile_all_pdfs():
            logger.error("[ORQUESTADOR] Error en PDF Compiler.")
            return
    logger.info("--- [ORQUESTADOR] Sincronización semanal completada ---")

@app.post("/orquestador/sync-semanal", tags=["Orquestador"])
def api_trigger_sync_semanal(background_tasks: BackgroundTasks):
    """Desencadena el pipeline semanal: PubMed → Redactor IA → PDFs clínicos."""
    background_tasks.add_task(task_orquestador_sync_semanal)
    return {"status": "Sincronización semanal encolada en segundo plano."}

# =====================================================================
# HEALTHCHECK
# =====================================================================

@app.get("/", tags=["Sistema"])
def healthcheck():
    """Estado del sistema y endpoints disponibles."""
    return {
        "status": "online",
        "version": "1.1.0",
        "agentes_disponibles": [
            "POST /agentes/iwgdf        — Agente 8: Estratificación IWGDF (grupos 0–3)",
            "POST /agentes/timers       — Agente 9: Recomendador TIMERS (apósitos)",
            "POST /agentes/offloading   — Agente 10: Off-loading biomecánico IWGDF 2023 ✓ NUEVO",
            "POST /agentes/antibioticos — Agente 11: Antibióticos + ajuste renal",
            "POST /orquestador/sync-semanal — Pipeline PubMed → PDF",
        ],
        "docs": "/docs",
        "disclaimer": DISCLAIMER_EDUCATIVO
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
