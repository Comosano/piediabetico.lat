"""
╔══════════════════════════════════════════════════════════════════════╗
║  MAIN.PY — ORQUESTADOR UNIFICADO API CLÍNICA                       ║
║  piediabetico.lat — Versión 2.0.0 (Agosto 2026)                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  Agentes integrados:                                                ║
║    • Flujo Completo : /analizar-foto (Agente 4 ONNX + Agente 7 IA)   ║
║    • Agente 7       : Triage Multimodal (Gemini 2.5 + Claude 3.7)   ║
║    • Agente 4       : Clasificador Binario ONNX (EfficientNet-B0)   ║
║    • Agente 8       : Estratificación de Riesgo IWGDF (0-3)         ║
║    • Agente 9       : Manejo de Lecho TIMERS & Apósitos             ║
║    • Agente 10      : Descarga Biomecánica Off-loading IWGDF 2023   ║
║    • Agente 11      : Antibióticos IDSA + Ajuste Cockcroft-Gault    ║
║    • Agentes 1-2-3  : Pipeline PubMed Científico                    ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import secrets
import logging
from typing import List, Optional
from enum import Enum
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Asegurar path local
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Importación de Agentes y Routers ──────────────────────────────────
try:
    from flujo_foto_integrado import router_flujo
    FLUJO_DISPONIBLE = True
except ImportError as e:
    logger.warning(f"flujo_foto_integrado no disponible: {e}")
    FLUJO_DISPONIBLE = False

try:
    from agente7_triage_multimodal import router_agente7
    AGENTE7_DISPONIBLE = True
except ImportError as e:
    logger.warning(f"agente7_triage_multimodal no disponible: {e}")
    AGENTE7_DISPONIBLE = False

try:
    from agente4_clasificador_ulcera import router_agente4
    AGENTE4_DISPONIBLE = True
except ImportError as e:
    logger.warning(f"agente4_clasificador_ulcera no disponible: {e}")
    AGENTE4_DISPONIBLE = False

try:
    from celery_app import pipeline_manual
    CELERY_DISPONIBLE = True
except ImportError:
    CELERY_DISPONIBLE = False

try:
    from pubmed_agent import PubMedScraperAgent
    from redactor_agent import RedactorAgent
    from pdf_agent import PDFCompilerAgent
except ImportError:
    PubMedScraperAgent = RedactorAgent = PDFCompilerAgent = None


# ── Configuración de Entorno & Seguridad P0 ──────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
is_production = ENVIRONMENT in ["production", "prod"]

# En producción se deshabilitan docs, redoc y openapi público
app = FastAPI(
    title="piediabetico.lat — API Clínica Unificada",
    description=(
        "Plataforma clínica integral para el manejo, detección y triage del pie diabético en LATAM. "
        "Impulsada por Google Gemini, Anthropic Claude, y modelos ONNX especializados. "
        "Todas las calculadoras son herramientas de referencia educativa basadas en guías IWGDF 2023 e IDSA."
    ),
    version="2.0.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# CORS Allowlist diferenciada según entorno
default_origins = (
    "https://piediabetico.lat,https://app.piediabetico.lat,https://piediabetico.online"
    if is_production
    else "https://piediabetico.lat,https://app.piediabetico.lat,https://piediabetico.online,http://localhost:3000,http://localhost:8000,http://127.0.0.1:5500"
)
ALLOWED_ORIGINS = [orig.strip() for orig in os.getenv("ALLOWED_ORIGINS", default_origins).split(",") if orig.strip()]

# ── Habilitar CORS con Allowlist Estricta ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Dependencia de Autenticación para Triggers Administrativos / Internos ──
def verify_admin_token(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    expected_key = os.getenv("ADMIN_API_KEY", "")
    if not x_admin_key:
        raise HTTPException(
            status_code=401,
            detail="Credenciales administrativas requeridas (Cabecera X-Admin-Key)."
        )
    
    if not expected_key or not secrets.compare_digest(x_admin_key, expected_key):
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado: Cabecera X-Admin-Key inválida."
        )
    return True

# Registrar Routers
if FLUJO_DISPONIBLE:
    app.include_router(router_flujo)
    logger.info("✓ Router Flujo Foto Integrado registrado")

if AGENTE7_DISPONIBLE:
    app.include_router(router_agente7)
    logger.info("✓ Router Agente 7 (Triage Multimodal) registrado")

if AGENTE4_DISPONIBLE:
    app.include_router(router_agente4)
    logger.info("✓ Router Agente 4 (Clasificador ONNX) registrado")

try:
    from agente12_san_elian import router_san_elian
    app.include_router(router_san_elian)
    logger.info("✓ Router San Elián (SEWSS) & Matriz Multiescala registrado")
except ImportError as e:
    logger.warning(f"agente12_san_elian no disponible: {e}")

try:
    from agente13_turnos import router_turnos
    app.include_router(router_turnos)
    logger.info("✓ Router Turnos & Teleasistencia Médica registrado")
except ImportError as e:
    logger.warning(f"agente13_turnos no disponible: {e}")

try:
    from agente14_auth import router_auth
    app.include_router(router_auth)
    logger.info("✓ Router Autenticación & 2FA registrado")
except ImportError as e:
    logger.warning(f"agente14_auth no disponible: {e}")

try:
    from agente4_segmentacion_unet import router_segmentacion
    app.include_router(router_segmentacion)
    logger.info("✓ Router Agente 4B (Segmentación U-Net & Área cm²) registrado")
except ImportError as e:
    logger.warning(f"agente4_segmentacion_unet no disponible: {e}")

DISCLAIMER = (
    "AVISO: Herramienta de referencia educativa basada en guías IWGDF 2023 e IDSA. "
    "No reemplaza el criterio clínico del profesional habilitado."
)


# =====================================================================
# AGENTE 8 — IWGDF (Estratificación de Riesgo 0-3)
# =====================================================================

class IWGDFInput(BaseModel):
    historia_ulcera:              bool = Field(..., description="Antecedente de úlcera previa")
    historia_amputacion:          bool = Field(..., description="Antecedente de amputación previa")
    insuficiencia_renal_terminal: bool = Field(..., description="Diálisis o eGFR < 15 mL/min")
    perdida_sensibilidad_lops:    bool = Field(..., description="Monofilamento 10g anormal (LOPS)")
    enfermedad_arterial_pad:      bool = Field(..., description="Pulsos ausentes o ITB < 0.9 (PAD)")
    deformidad_pie:               bool = Field(..., description="Dedos en garra, prominencias óseas, Charcot")

class IWGDFOutput(BaseModel):
    grupo_riesgo:          int   = Field(..., description="Grupo de riesgo 0, 1, 2 o 3")
    frecuencia_inspeccion: str   = Field(..., description="Periodicidad recomendada de control")
    tipo_descarga_calzado: str   = Field(..., description="Recomendación de calzado / plantillas")
    disclaimer:            str   = Field(..., description="Aviso clínico")

@app.post("/agentes/iwgdf", response_model=IWGDFOutput, tags=["Calculadoras Clínicas"])
def api_agente_iwgdf(datos: IWGDFInput):
    """Agente 8 — Estratificación preventiva del riesgo según guías IWGDF 2023."""
    if datos.historia_ulcera or datos.historia_amputacion or datos.insuficiencia_renal_terminal:
        return IWGDFOutput(
            grupo_riesgo=3,
            frecuencia_inspeccion="Cada 1 a 3 meses por equipo multidisciplinar especializado.",
            tipo_descarga_calzado="Calzado terapéutico a medida con plantillas de descarga activa.",
            disclaimer=DISCLAIMER
        )
    if ((datos.perdida_sensibilidad_lops and datos.enfermedad_arterial_pad) or
        (datos.perdida_sensibilidad_lops and datos.deformidad_pie) or
        (datos.enfermedad_arterial_pad and datos.deformidad_pie)):
        return IWGDFOutput(
            grupo_riesgo=2,
            frecuencia_inspeccion="Cada 2 a 3 meses por especialista en pie diabético.",
            tipo_descarga_calzado="Calzado terapéutico extra-profundo con plantillas termoconformadas.",
            disclaimer=DISCLAIMER
        )
    if datos.perdida_sensibilidad_lops or datos.enfermedad_arterial_pad:
        return IWGDFOutput(
            grupo_riesgo=1,
            frecuencia_inspeccion="Cada 3 a 6 meses por enfermería o podología.",
            tipo_descarga_calzado="Calzado de horma ancha sin costuras internas.",
            disclaimer=DISCLAIMER
        )
    return IWGDFOutput(
        grupo_riesgo=0,
        frecuencia_inspeccion="Anual por médico de atención primaria.",
        tipo_descarga_calzado="Calzado comercial cómodo de horma ancha. Autoinspección diaria.",
        disclaimer=DISCLAIMER
    )


# =====================================================================
# AGENTE 9 — TIMERS (Apósitos y Desbridamiento)
# =====================================================================

class TIMERSInput(BaseModel):
    tejido_no_viable:      bool = Field(..., description="Esfacelo, fibrina o necrosis en el lecho")
    infeccion_inflamacion: bool = Field(..., description="Eritema > 0.5cm, calor local, edema, secreción")
    humedad_exudado_alto:  bool = Field(..., description="Exudado moderado o abundante")
    bordes_estancados:     bool = Field(..., description="Bordes no migrantes, hiperqueratósicos o macerados")

class TIMERSOutput(BaseModel):
    conducta_desbridamiento: str
    apositivo_sugerido:      str
    frecuencia_curacion:     str
    disclaimer:              str

@app.post("/agentes/timers", response_model=TIMERSOutput, tags=["Calculadoras Clínicas"])
def api_agente_timers(datos: TIMERSInput):
    """Agente 9 — Recomendador clínico TIMERS de apósitos y preparación del lecho."""
    conducta   = "Limpieza no traumática con solución salina estéril."
    apositivo  = "Gasa o hidrocoloide simple con solución fisiológica."
    frecuencia = "Cada 24 a 48 horas."

    if datos.tejido_no_viable:
        conducta  = "Desbridamiento cortante activo / enzimático con colagenasa."
        apositivo = "Colagenasa en ungüento o hidrogel hidratante para autólisis."
    
    if datos.infeccion_inflamacion:
        apositivo  = "Apósitos bacteriostáticos con plata nanocristalina o DACC."
        frecuencia = "Cada 24 horas."
        if datos.humedad_exudado_alto:
            apositivo = "Espuma de poliuretano (Foam) con plata nanocristalina."
    elif datos.humedad_exudado_alto:
        apositivo  = "Alginato de calcio o espuma hidrocelular de alta absorción."
        frecuencia = "Cada 48 a 72 horas según saturación."

    if datos.bordes_estancados:
        conducta += " + Desbridamiento de bordes y estimulación con apósitos moduladores de MMPs."

    return TIMERSOutput(
        conducta_desbridamiento=conducta,
        apositivo_sugerido=apositivo,
        frecuencia_curacion=frecuencia,
        disclaimer=DISCLAIMER
    )


# =====================================================================
# AGENTE 10 — OFF-LOADING (Descarga Biomecánica IWGDF 2023)
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
    localizacion:                LocalizacionUlcera   = Field(..., description="Localización anatómica de la lesión")
    pie_afectado:                PieAfectado          = Field(..., description="Pie afectado")
    isquemia_severa:             bool                 = Field(False, description="ITB < 0.5 o pulsos ausentes")
    infeccion_activa_frecuente:  bool                 = Field(False, description="Infección activa que requiere curaciones diarias")
    riesgo_caidas_alto:          bool                 = Field(False, description="Fragilidad o historial de caídas")
    deformidad:                  DeformidadAsociada   = Field(DeformidadAsociada.NINGUNA, description="Deformidad asociada")
    peso_mayor_90kg:             bool                 = Field(False, description="Peso corporal > 90 kg")

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
    """Agente 10 — Prescripción de Descarga Biomecánica según Guías IWGDF 2023."""
    motivos_contra = []
    if datos.isquemia_severa:
        motivos_contra.append("Isquemia severa (ITB < 0.5 o pulsos ausentes)")
    if datos.infeccion_activa_frecuente:
        motivos_contra.append("Infección activa que requiere curaciones diarias continuas")
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
        dispositivo_primera_linea=d1,
        dispositivo_alternativo=dalt,
        justificacion_iwgdf=just,
        materiales_ortopodologicos=mat,
        compensacion_postural=comp,
        advertencias_seguridad=adv,
        contraindicacion_dispositivo_fijo=contra_fijo,
        motivos_contraindicacion=motivos_contra,
        disclaimer=DISCLAIMER
    )


# =====================================================================
# AGENTE 11 — ANTIBIÓTICOS (IDSA + Ajuste Cockcroft-Gault)
# =====================================================================

class AntibioticInput(BaseModel):
    edad:                    int   = Field(..., ge=18, le=120, description="Edad en años")
    peso_kg:                 float = Field(..., ge=30, le=250, description="Peso corporal en kg")
    creatinina_serica:       float = Field(..., ge=0.2, le=15.0, description="Creatinina en mg/dL")
    sexo:                    str   = Field(..., pattern="^(M|F)$", description="M (Masculino) o F (Femenino)")
    severidad_infeccion:     str   = Field(..., pattern="^(leve|moderada|grave)$", description="leve / moderada / grave")
    riesgo_multirresistencia:bool  = Field(False, description="Sospecha de SAMR o Pseudomonas aeruginosa")

class AntibioticOutput(BaseModel):
    egfr_calculado:              float
    esquema_empirico:            str
    dosis_ajustada:              str
    advertencias_nefrotoxicidad: str
    disclaimer:                  str

@app.post("/agentes/antibioticos", response_model=AntibioticOutput, tags=["Calculadoras Clínicas"])
def api_agente_antibioticos(datos: AntibioticInput):
    """Agente 11 — Esquemas empíricos según guías IDSA + Ajuste por eGFR (Cockcroft-Gault)."""
    factor = 0.85 if datos.sexo == "F" else 1.0
    egfr   = ((140 - datos.edad) * datos.peso_kg) / (72 * datos.creatinina_serica) * factor

    esquema = "Cefalexina 500mg oral c/6h o Amoxicilina-Clavulánico 875/125mg oral c/12h"
    dosis   = "Dosis estándar de adulto."
    adv     = "Monitorear función renal y adecuada hidratación."

    if datos.severidad_infeccion == "leve":
        if datos.riesgo_multirresistencia:
            esquema = "TMP-SMX (Trimetoprima-Sulfametoxazol) 160/800mg oral c/12h (cobertura SAMR)"
            if egfr < 30:
                dosis = "TMP-SMX: reducir a 80/400mg oral c/12h."
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
                adv   = "ALERTA: eGFR < 15 mL/min. Evitar nefrotóxicos adicionales y ajustar vancomicina por niveles."
    elif datos.severidad_infeccion == "grave":
        esquema = "Meropenem 1g IV c/8h + Linezolid 600mg IV c/12h o Vancomicina IV"
        if egfr < 50:
            dosis = ("Meropenem: 1g IV c/12h." if egfr >= 26
                     else "Meropenem: 500mg IV c/12h." if egfr >= 10
                     else "Meropenem: 500mg IV c/24h.")
            adv = "Ajuste renal crítico para carbapenémicos en infección grave."

    return AntibioticOutput(
        egfr_calculado=round(egfr, 2),
        esquema_empirico=esquema,
        dosis_ajustada=dosis,
        advertencias_nefrotoxicidad=adv,
        disclaimer=DISCLAIMER
    )


# =====================================================================
# PIPELINE SEMANAL CIENTÍFICO (PUBMED)
# =====================================================================

def _ejecutar_pipeline():
    logger.info("[Pipeline] Iniciando sync directo...")
    if PubMedScraperAgent:
        PubMedScraperAgent().execute_weekly_sync()
    if RedactorAgent:
        RedactorAgent().execute_translation_pipeline()
    if PDFCompilerAgent:
        PDFCompilerAgent().compile_all_pdfs()
    logger.info("[Pipeline] Completado")

@app.post("/orquestador/sync-semanal", tags=["Orquestador"], dependencies=[Depends(verify_admin_token)])
@app.post("/pipeline-semanal/ejecutar", tags=["Orquestador"], dependencies=[Depends(verify_admin_token)])
def api_sync_semanal(background_tasks: BackgroundTasks):
    """Trigger administrativo protegido del pipeline PubMed → Redactor → PDF."""
    if CELERY_DISPONIBLE:
        pipeline_manual.delay()
        return {"status": "ok", "modo": "celery", "mensaje": "Pipeline administrativo encolado."}
    else:
        background_tasks.add_task(_ejecutar_pipeline)
        return {"status": "ok", "modo": "background", "mensaje": "Pipeline administrativo iniciado."}


# =====================================================================
# HEALTHCHECK & INFO MINIMALISTA P0
# =====================================================================

@app.get("/", tags=["Sistema"])
def root():
    """Respuesta mínima sin exponer detalles de arquitectura, proveedores ni claves."""
    if is_production:
        return {"status": "ok"}
    return {
        "status": "ok",
        "service": "piediabetico-api",
        "env": ENVIRONMENT
    }

@app.get("/health", tags=["Sistema"])
def health():
    """Healthcheck estándar minimalista sin hostnames ni versiones internas."""
    return {"status": "ok"}
