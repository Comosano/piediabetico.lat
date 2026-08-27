"""
╔══════════════════════════════════════════════════════════════════════╗
║  MAIN.PY — ORQUESTADOR FINAL COMPLETO                              ║
║  piediabetico.lat — Versión 1.2.0                                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  Agentes incluidos:                                                 ║
║    8  — IWGDF (estratificación de riesgo)                          ║
║    9  — TIMERS (apósitos y curación)                               ║
║    10 — Off-loading biomecánico IWGDF 2023                         ║
║    11 — Antibióticos + ajuste renal Cockcroft-Gault                ║
║    7  — Triage multimodal Claude Vision (5 perfiles)               ║
║    1-2-3 — Pipeline PubMed → Redactor → PDF (via Celery)           ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Importar agentes locales ──────────────────────────────────────────
try:
    from pubmed_agent import PubMedScraperAgent
    from redactor_agent import RedactorAgent
    from pdf_agent import PDFCompilerAgent
except ImportError as e:
    logger.warning(f"Agentes de pipeline no disponibles: {e}")
    PubMedScraperAgent = RedactorAgent = PDFCompilerAgent = None

# ── Importar Agente 7 ─────────────────────────────────────────────────
try:
    from agente7_triage_multimodal import router_agente7
    AGENTE7_DISPONIBLE = True
except ImportError:
    logger.warning("agente7_triage_multimodal.py no encontrado")
    AGENTE7_DISPONIBLE = False

# ── Importar Celery (para disparar pipeline manualmente) ──────────────
try:
    from celery_app import pipeline_manual
    CELERY_DISPONIBLE = True
except ImportError:
    logger.warning("celery_app.py no encontrado")
    CELERY_DISPONIBLE = False

# ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="piediabetico.lat — API Clínica",
    description=(
        "Orquestador de agentes clínicos para el manejo del pie diabético en LATAM. "
        "Todas las calculadoras son herramientas de referencia educativa basadas en "
        "guías IWGDF 2023 e IDSA. No reemplazan el criterio clínico profesional."
    ),
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Registrar el router del Agente 7 si está disponible
if AGENTE7_DISPONIBLE:
    app.include_router(router_agente7)
    logger.info("✓ Agente 7 (Triage Multimodal) registrado")

DISCLAIMER = (
    "AVISO: Herramienta de referencia educativa basada en guías IWGDF 2023 e IDSA. "
    "No reemplaza el criterio clínico del profesional habilitado."
)

# =====================================================================
# AGENTE 8 — IWGDF
# =====================================================================

class IWGDFInput(BaseModel):
    historia_ulcera:              bool = Field(..., description="Antecedente de úlcera previa")
    historia_amputacion:          bool = Field(..., description="Antecedente de amputación")
    insuficiencia_renal_terminal: bool = Field(..., description="Diálisis o eGFR < 15")
    perdida_sensibilidad_lops:    bool = Field(..., description="Monofilamento 10g anormal")
    enfermedad_arterial_pad:      bool = Field(..., description="Pulsos ausentes o ITB < 0.9")
    deformidad_pie:               bool = Field(..., description="Dedos en garra, Charcot activo")

class IWGDFOutput(BaseModel):
    grupo_riesgo:          int
    frecuencia_inspeccion: str
    tipo_descarga_calzado: str
    disclaimer:            str

@app.post("/agentes/iwgdf", response_model=IWGDFOutput, tags=["Calculadoras Clínicas"])
def api_agente_iwgdf(datos: IWGDFInput):
    """Agente 8 — Estratificación preventiva IWGDF (grupos 0–3)."""
    if datos.historia_ulcera or datos.historia_amputacion or datos.insuficiencia_renal_terminal:
        return IWGDFOutput(grupo_riesgo=3,
            frecuencia_inspeccion="Cada 1 a 3 meses por equipo multidisciplinar especializado.",
            tipo_descarga_calzado="Calzado terapéutico a medida con plantillas de descarga activa.",
            disclaimer=DISCLAIMER)
    if ((datos.perdida_sensibilidad_lops and datos.enfermedad_arterial_pad) or
        (datos.perdida_sensibilidad_lops and datos.deformidad_pie) or
        (datos.enfermedad_arterial_pad and datos.deformidad_pie)):
        return IWGDFOutput(grupo_riesgo=2,
            frecuencia_inspeccion="Cada 2 a 3 meses por especialista en pie diabético.",
            tipo_descarga_calzado="Calzado terapéutico extra-profundo con plantillas termoconformadas.",
            disclaimer=DISCLAIMER)
    if datos.perdida_sensibilidad_lops or datos.enfermedad_arterial_pad:
        return IWGDFOutput(grupo_riesgo=1,
            frecuencia_inspeccion="Cada 3 a 6 meses por enfermería o podología.",
            tipo_descarga_calzado="Calzado de horma ancha sin costuras internas.",
            disclaimer=DISCLAIMER)
    return IWGDFOutput(grupo_riesgo=0,
        frecuencia_inspeccion="Anual por médico de atención primaria.",
        tipo_descarga_calzado="Calzado comercial cómodo de horma ancha. Inspección diaria.",
        disclaimer=DISCLAIMER)

# =====================================================================
# AGENTE 9 — TIMERS
# =====================================================================

class TIMERSInput(BaseModel):
    tejido_no_viable:      bool = Field(..., description="Esfacelo, fibrina o necrosis")
    infeccion_inflamacion: bool = Field(..., description="Eritema > 0.5cm, calor, secreción")
    humedad_exudado_alto:  bool = Field(..., description="Exudado abundante")
    bordes_estancados:     bool = Field(..., description="Bordes enrollados o sin avance")

class TIMERSOutput(BaseModel):
    conducta_desbridamiento: str
    apositivo_sugerido:      str
    frecuencia_curacion:     str
    disclaimer:              str

@app.post("/agentes/timers", response_model=TIMERSOutput, tags=["Calculadoras Clínicas"])
def api_agente_timers(datos: TIMERSInput):
    """Agente 9 — Recomendador TIMERS (apósitos y desbridamiento)."""
    conducta   = "Limpieza con solución salina estéril."
    apositivo  = "Gasa estéril con solución fisiológica."
    frecuencia = "Cada 24 a 48 horas."
    if datos.tejido_no_viable:
        conducta  = "Desbridamiento cortante activo o enzimático con colagenasa."
        apositivo = "Colagenasa en ungüento o hidrogel para autólisis."
    if datos.infeccion_inflamacion:
        apositivo  = "Apósitos bacteriostáticos con plata nanocristalina o DACC."
        frecuencia = "Cada 24 horas."
        if datos.humedad_exudado_alto:
            apositivo = "Espuma de poliuretano (Foam) con plata para control de humedad."
    elif datos.humedad_exudado_alto:
        apositivo  = "Alginato de calcio o hidrocoloides absorbentes de alta capacidad."
        frecuencia = "Cada 48 a 72 horas según saturación."
    if datos.bordes_estancados:
        conducta += " + Estimulación mecánica de bordes o apósitos moduladores de MMPs."
    return TIMERSOutput(conducta_desbridamiento=conducta, apositivo_sugerido=apositivo,
                        frecuencia_curacion=frecuencia, disclaimer=DISCLAIMER)

# =====================================================================
# AGENTE 10 — OFF-LOADING
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
    NINGUNA         = "ninguna"
    DEDOS_EN_GARRA  = "dedos_en_garra"
    HALLUX_VALGUS   = "hallux_valgus"
    CHARCOT_CRONICO = "charcot_cronico"

class OffloadingInput(BaseModel):
    localizacion:                LocalizacionUlcera   = Field(..., description="Localización anatómica de la úlcera")
    pie_afectado:                PieAfectado          = Field(..., description="Pie afectado")
    isquemia_severa:             bool                 = Field(False, description="ITB < 0.5 o pulsos ausentes")
    infeccion_activa_frecuente:  bool                 = Field(False, description="Infección moderada/grave con curaciones diarias")
    riesgo_caidas_alto:          bool                 = Field(False, description="Fragilidad extrema o historial de caídas")
    deformidad:                  DeformidadAsociada   = Field(DeformidadAsociada.NINGUNA, description="Deformidad estructural")
    peso_mayor_90kg:             bool                 = Field(False, description="Peso > 90 kg")

class OffloadingOutput(BaseModel):
    dispositivo_primera_linea:         str
    dispositivo_alternativo:           str
    justificacion_iwgdf:               str
    materiales_ortopodologicos:        List[str]
    compensacion_postural:             List[str]
    advertencias_seguridad:            List[str]
    contraindicacion_dispositivo_fijo: bool
    motivos_contraindicacion:          List[str]
    disclaimer:                        str

@app.post("/agentes/offloading", response_model=OffloadingOutput, tags=["Calculadoras Clínicas"])
def api_agente_offloading(datos: OffloadingInput):
    """Agente 10 — Prescripción de Descarga Biomecánica IWGDF 2023."""
    motivos_contra = []
    if datos.isquemia_severa:
        motivos_contra.append("Isquemia severa (ITB < 0.5 o pulsos ausentes)")
    if datos.infeccion_activa_frecuente:
        motivos_contra.append("Infección activa con curaciones diarias")
    if datos.riesgo_caidas_alto:
        motivos_contra.append("Alto riesgo de caídas documentado")
    contra_fijo = len(motivos_contra) > 0

    pie_sano = ("ambos pies" if datos.pie_afectado == PieAfectado.BILATERAL
                else "pie izquierdo" if datos.pie_afectado == PieAfectado.DERECHO
                else "pie derecho")
    densidad = "alta densidad (300 kg/m³)" if datos.peso_mayor_90kg else "densidad media (220 kg/m³)"

    if datos.localizacion in [LocalizacionUlcera.ANTEPIE_PLANTAR, LocalizacionUlcera.MEDIOPIE_PLANTAR]:
        d1   = "Bota Walker Alta NO Removible (bloqueada) o Yeso de Contacto Total (TCC)" if not contra_fijo else "Bota Walker Alta Removible con plantilla conformada"
        dalt = "Bota Walker Removible (solo si intolerancia documentada)" if not contra_fijo else "Zapato quirúrgico de cuña invertida de Barouk"
        just = "IWGDF 2023 — Gold Standard: dispositivo no removible reduce 85% el pico de presión plantar." if not contra_fijo else f"IWGDF 2023: dispositivo removible por contraindicaciones: {'; '.join(motivos_contra)}."
        mat  = [f"Plantilla multicapa: base EVA {densidad} + Plastazote 6mm.", "Fenestración circular bajo zona de hiperapoyo.", "Fieltro semicomprimido 7mm en herradura perilesional."]
    elif datos.localizacion == LocalizacionUlcera.TALON:
        d1   = "Bota Walker con cuña posterior o ventana de descarga total de talón"
        dalt = "Calzado ortopédico de descarga posterior o Yeso TCC con cámara de aire"
        just = "IWGDF 2023: desgravitación completa del retropié obligatoria para cicatrización."
        mat  = ["Talonera de silicona con orificio fenestrado central.", "Almohadillado de protección en tendón de Aquiles.", "Almohadilla antiescaras para descarga durante reposo."]
    elif datos.localizacion == LocalizacionUlcera.DIGITAL:
        d1   = "Calzado postquirúrgico extra-profundo con puntera ancha + Ortesis de silicona digital"
        dalt = "Zapato de descarga con corte rígido y puntera abierta"
        just = "IWGDF 2023: eliminar conflicto de roce y redistribuir carga metatarsiana."
        mat  = ["Ortesis de silicona vulcanizada a medida.", "Fieltro 3mm de protección apical si hay roce distal."]
        if datos.deformidad == DeformidadAsociada.DEDOS_EN_GARRA:
            mat.append("Considerar Tenotomía Flexora Percutánea (evaluación quirúrgica).")
    else:
        d1   = "Calzado terapéutico a medida con corte blando sin costuras internas"
        dalt = "Sandalia terapéutica con tiras de velcro ajustables"
        just = "IWGDF 2023: reducción del roce mecánico en prominencias dorsales o maleolares."
        mat  = ["Apósito de interfase hidrocelular fino de protección perilesional."]

    comp = [f"Alza de nivelación pélvica en el {pie_sano}: compensar altura del dispositivo."]
    if datos.pie_afectado == PieAfectado.BILATERAL:
        comp.append("Caso bilateral: derivación urgente a ortopedia/rehabilitación.")

    adv = ["Prohibición de deambular descalzo o en medias, incluso en el domicilio.",
           "Revisión semanal de puntos de roce secundario."]
    if datos.isquemia_severa:
        adv.append("Isquemia severa: derivación urgente a cirugía vascular antes del off-loading.")
    if datos.deformidad == DeformidadAsociada.CHARCOT_CRONICO:
        adv.append("Pie de Charcot: requiere horma de Charcot. No usar Walker estándar sin adaptación.")

    return OffloadingOutput(
        dispositivo_primera_linea=d1, dispositivo_alternativo=dalt,
        justificacion_iwgdf=just, materiales_ortopodologicos=mat,
        compensacion_postural=comp, advertencias_seguridad=adv,
        contraindicacion_dispositivo_fijo=contra_fijo,
        motivos_contraindicacion=motivos_contra, disclaimer=DISCLAIMER)

# =====================================================================
# AGENTE 11 — ANTIBIÓTICOS
# =====================================================================

class AntibioticInput(BaseModel):
    edad:                    int   = Field(..., ge=18, le=120)
    peso_kg:                 float = Field(..., ge=30, le=250)
    creatinina_serica:       float = Field(..., ge=0.2, le=15.0, description="mg/dL")
    sexo:                    str   = Field(..., pattern="^(M|F)$")
    severidad_infeccion:     str   = Field(..., pattern="^(leve|moderada|grave)$")
    riesgo_multirresistencia:bool  = Field(False, description="Sospecha SAMR o Pseudomonas")

class AntibioticOutput(BaseModel):
    egfr_calculado:              float
    esquema_empirico:            str
    dosis_ajustada:              str
    advertencias_nefrotoxicidad: str
    disclaimer:                  str

@app.post("/agentes/antibioticos", response_model=AntibioticOutput, tags=["Calculadoras Clínicas"])
def api_agente_antibioticos(datos: AntibioticInput):
    """Agente 11 — Esquemas empíricos IDSA + ajuste renal Cockcroft-Gault."""
    factor = 0.85 if datos.sexo == "F" else 1.0
    egfr   = ((140 - datos.edad) * datos.peso_kg) / (72 * datos.creatinina_serica) * factor

    esquema = "Cefalexina 500mg oral c/6h o Amoxicilina-Clavulánico 875/125mg oral c/12h"
    dosis   = "Dosis estándar de adulto."
    adv     = "Monitorear función hepática e hidratación."

    if datos.severidad_infeccion == "leve":
        if datos.riesgo_multirresistencia:
            esquema = "TMP-SMX 160/800mg oral c/12h (cobertura SAMR)"
            if egfr < 30:
                dosis = "TMP-SMX: reducir a 80/400mg c/12h."
                adv   = "Ajuste renal crítico por eGFR < 30 mL/min."
    elif datos.severidad_infeccion == "moderada":
        esquema = "Ampicilina-Sulbactam 1.5–3g IV c/6h o Ceftriaxona 1–2g IV c/24h"
        if datos.riesgo_multirresistencia:
            esquema = "Piperacilina-Tazobactam 4.5g IV c/6h + Vancomicina IV"
            if 15 <= egfr < 40:
                dosis = "Pip-Taz: reducir a 3.375g IV c/6h."
                adv   = "Ajuste renal por insuficiencia moderada."
            elif egfr < 15:
                dosis = "Pip-Taz: 2.25g IV c/8h o Meropenem 500mg IV c/24h."
                adv   = "ALERTA: eGFR < 15. Evitar nefrotóxicos adicionales."
    elif datos.severidad_infeccion == "grave":
        esquema = "Meropenem 1g IV c/8h + Linezolid 600mg IV c/12h"
        if egfr < 50:
            dosis = ("Meropenem: 1g c/12h." if egfr >= 26
                     else "Meropenem: 500mg c/12h." if egfr >= 10
                     else "Meropenem: 500mg c/24h.")
            adv = "Ajuste renal crítico para Meropenem en infección grave."

    return AntibioticOutput(egfr_calculado=round(egfr, 2), esquema_empirico=esquema,
                            dosis_ajustada=dosis, advertencias_nefrotoxicidad=adv,
                            disclaimer=DISCLAIMER)

# =====================================================================
# PIPELINE SEMANAL — disparador manual desde la API
# =====================================================================

def _ejecutar_pipeline():
    """Ejecuta el pipeline localmente (sin Celery) como fallback."""
    logger.info("[Pipeline] Iniciando modo directo (sin Celery)")
    if PubMedScraperAgent:
        PubMedScraperAgent().execute_weekly_sync()
    if RedactorAgent:
        RedactorAgent().execute_translation_pipeline()
    if PDFCompilerAgent:
        PDFCompilerAgent().compile_all_pdfs()
    logger.info("[Pipeline] Completado")

@app.post("/orquestador/sync-semanal", tags=["Orquestador"])
def api_sync_semanal(background_tasks: BackgroundTasks):
    """
    Dispara manualmente el pipeline PubMed → Redactor → PDF.
    Normalmente corre automáticamente cada sábado a las 23hs via Celery.
    """
    if CELERY_DISPONIBLE:
        pipeline_manual.delay()
        return {"status": "encolado", "modo": "celery",
                "mensaje": "Pipeline encolado en Celery. Corre en segundo plano."}
    else:
        background_tasks.add_task(_ejecutar_pipeline)
        return {"status": "encolado", "modo": "background_tasks",
                "mensaje": "Pipeline iniciado en segundo plano (Celery no disponible)."}

# =====================================================================
# SERVICIO DE NEWSLETTER & CONTACTO OFICIAL (RESEND / SMTP)
# =====================================================================

try:
    from email_service import registrar_suscriptor, registrar_consulta, enviar_email
    EMAIL_SERVICE_DISPONIBLE = True
except ImportError:
    EMAIL_SERVICE_DISPONIBLE = False

class NewsletterSubscribeRequest(BaseModel):
    email: str = Field(..., example="medico@hospital.com")
    perfil: str = Field("profesional", example="profesional")
    pais: Optional[str] = "LATAM"

class ContactoRequest(BaseModel):
    nombre: str = Field(..., example="Dr. Martín Gómez")
    email: str = Field(..., example="martin@hospital.com")
    telefono: Optional[str] = ""
    motivo: str = Field(..., example="propuesta_institucional")
    mensaje: str = Field(..., example="Nos gustaría incorporar el triage IA en nuestro hospital...")

@app.post("/api/newsletter/subscribe", tags=["Newsletter & Contacto"])
def api_subscribe_newsletter(req: NewsletterSubscribeRequest):
    """Registra suscriptor y dispara email de bienvenida con guías IWGDF."""
    if EMAIL_SERVICE_DISPONIBLE:
        return registrar_suscriptor(req.email, req.perfil, req.pais or "LATAM")
    return {"status": "success", "mode": "mock", "email": req.email}

@app.post("/api/contact", tags=["Newsletter & Contacto"])
def api_contact_submit(req: ContactoRequest):
    """Procesa formulario de contacto, genera ticket único y emite confirmación."""
    if EMAIL_SERVICE_DISPONIBLE:
        return registrar_consulta(req.nombre, req.email, req.telefono or "", req.motivo, req.mensaje)
    import random
    return {"status": "success", "ticket_id": f"CONS-{random.randint(1000, 9999)}"}

# =====================================================================
# HEALTHCHECK
# =====================================================================

@app.get("/", tags=["Sistema"])
def healthcheck():
    return {
        "status": "online",
        "version": "1.2.0",
        "agentes": {
            "8_iwgdf":       "POST /agentes/iwgdf",
            "9_timers":      "POST /agentes/timers",
            "10_offloading": "POST /agentes/offloading",
            "11_antibioticos":"POST /agentes/antibioticos",
            "7_triage_ia":   "POST /agentes/triage-multimodal" if AGENTE7_DISPONIBLE else "no disponible",
            "newsletter":    "POST /api/newsletter/subscribe",
            "contacto":      "POST /api/contact"
        },
        "pipeline": "POST /orquestador/sync-semanal",
        "celery":   CELERY_DISPONIBLE,
        "agente7":  AGENTE7_DISPONIBLE,
        "docs":     "/docs",
        "disclaimer": DISCLAIMER,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

