"""
AGENTE 12: Sistema de Puntuación San Elián (SEWSS) & Matriz Multiescala
piediabetico.lat — Ecosistema Clínico LATAM

Implementa:
1. Calculadora de San Elián (San Elian Wound Score System - SEWSS):
   - Rango: 10 a 30 puntos
   - 10 Factores en 3 categorías:
     * Factores Anatómicos/Topográficos (Localización, Aspecto, N° Zonas)
     * Factores Tisulares/Morfológicos (Profundidad, Área, Fase Cicatrización)
     * Factores Agravantes/Biológicos (Isquemia, Infección, Neuropatía, Edema)
   - Grados I, II, III con pronóstico de rescate y conducta clínica.
2. Motor de Matriz Multiescala Unificada (IWGDF, San Elián, Texas, Wagner, TIMERS, IDSA).
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from fastapi import APIRouter

router_san_elian = APIRouter(prefix="/calculadoras", tags=["Calculadoras Clínicas — San Elián & Multiescala"])

# ─────────────────────────────────────────────────────────────────────
# ESQUEMA DE ENTRADA Y SALIDA SAN ELIÁN
# ─────────────────────────────────────────────────────────────────────

class SanElianInput(BaseModel):
    # Categoría A: Factores Anatómicos
    location: int = Field(1, ge=1, le=3, description="1: Falanges, 2: Antepié/Mediopé, 3: Retropé/Múltiples")
    topographic_aspect: int = Field(1, ge=1, le=3, description="1: Dorsal/Plantar simple, 2: Medial/Lateral/Interdigital, 3: Circunferencial/Transfixiante")
    number_of_zones: int = Field(1, ge=1, le=3, description="1: 1 zona, 2: 2 zonas, 3: 3 o más zonas")
    
    # Categoría B: Factores Tisulares
    depth: int = Field(1, ge=1, le=3, description="1: Superficial, 2: Parcial/Subcutánea, 3: Profunda/Ósea")
    area: int = Field(1, ge=1, le=3, description="1: <1.5 cm², 2: 1.5-5.0 cm², 3: >5.0 cm²")
    healing_phase: int = Field(1, ge=1, le=3, description="1: Granulación (>75%), 2: Fibrina/Esfacelo, 3: Necrosis (>50%)")
    
    # Categoría C: Factores Agravantes
    ischemia: int = Field(1, ge=1, le=3, description="1: Sin isquemia (Pulsos presentes), 2: Isquemia moderada, 3: Isquemia crítica")
    infection: int = Field(1, ge=1, le=3, description="1: No infectada, 2: Infección local leve/mod, 3: Severa/SIRS/Sepsis")
    neuropathy: int = Field(1, ge=1, le=3, description="1: Normal, 2: Pérdida sensibilidad (LOPS), 3: Neuropatía severa + Charcot")
    edema: int = Field(1, ge=1, le=3, description="1: Sin edema, 2: Edema local con fóvea, 3: Edema regional severo/Linfedema")


class SanElianOutput(BaseModel):
    score_total: int
    grado: str
    severidad: str
    color_alerta: str
    pronostico_rescate: str
    conducta_clinica: str
    desglose_categorias: Dict[str, int]


def calcular_sewss(data: SanElianInput) -> SanElianOutput:
    puntos_anatomicos = data.location + data.topographic_aspect + data.number_of_zones
    puntos_tisulares = data.depth + data.area + data.healing_phase
    puntos_agravantes = data.ischemia + data.infection + data.neuropathy + data.edema
    
    score_total = puntos_anatomicos + puntos_tisulares + puntos_agravantes
    
    if score_total <= 10:
        grado = "Grado I"
        severidad = "Leve / Bajo Riesgo"
        color = "verde"
        pronostico = "Excelente (>90% probabilidad de cicatrización y rescate completo sin amputación)."
        conducta = "Manejo ambulatorio protocolizado, curación avanzada tópica, control metabólico estricto y descarga preventiva. Control podológico cada 7 a 14 días."
    elif score_total <= 20:
        grado = "Grado II"
        severidad = "Moderado / Riesgo Intermedio"
        color = "amarillo"
        pronostico = "Riesgo de amputación menor/parcial (dedo/antepié). Rescate de extremidad altamente viable con intervención oportuna."
        conducta = "Manejo multidisciplinario intensivo (infectología, podología quirúrgica, cirugía vascular). Desbridamiento activo, antibioterapia dirigida y revascularización si procede. Control cada 48 a 72 horas."
    else:
        grado = "Grado III"
        severidad = "Severo / Alto Riesgo"
        color = "rojo"
        pronostico = "Alto riesgo de amputación mayor (infracondílea/supracondílea) y elevada morbimortalidad sistémica."
        conducta = "Internación hospitalaria urgente inmediata, angiografía/revascularización de urgencia, desbridamiento quirúrgico amplio en quirófano / control de sepsis, balance de rescate vs amputación funcional temprana."

    return SanElianOutput(
        score_total=score_total,
        grado=grado,
        severidad=severidad,
        color_alerta=color,
        pronostico_rescate=pronostico,
        conducta_clinica=conducta,
        desglose_categorias={
            "factores_anatomicos_pts": puntos_anatomicos,
            "factores_tisulares_pts": puntos_tisulares,
            "factores_agravantes_pts": puntos_agravantes
        }
    )


# ─────────────────────────────────────────────────────────────────────
# MATRIZ MULTIESCALA UNIFICADA (EVALUACIÓN INTEGRAL)
# ─────────────────────────────────────────────────────────────────────

class MatrizMultiescalaInput(BaseModel):
    # Datos clínicos universales
    profundidad_tejido: str = Field("fascia_tendon", description="superficial / fascia_tendon / hueso_articulacion")
    infeccion_severidad: str = Field("moderada", description="no_infectada / leve / moderada / severa")
    isquemia_estado: str = Field("moderada", description="sin_isquemia / moderada / critica")
    neuropatia_lops: bool = Field(True, description="Pérdida de sensibilidad protectora")
    deformidad_pie: bool = Field(True, description="Deformidad o prominencias óseas")
    antecedente_ulcera_amputacion: bool = Field(False, description="Historia previa de úlcera")
    area_cm2: float = Field(2.4, description="Área en cm²")
    localizacion: str = Field("antepie_plantar", description="dedos / antepie_plantar / talon")
    exudado_humedad: str = Field("alto", description="bajo / moderado / alto")
    esfacelo_fibrina: bool = Field(True, description="Presencia de tejido desvitalizado")


class FilaEscala(BaseModel):
    escala: str
    clasificacion: str
    estadio_grado: str
    significado_clinico: str
    conducta_clave: str
    color_semaforo: str


class MatrizMultiescalaOutput(BaseModel):
    resumen_paciente: str
    evaluacion_integral: List[FilaEscala]
    consenso_multidisciplinar: str


def generar_matriz_multiescala(data: MatrizMultiescalaInput) -> MatrizMultiescalaOutput:
    matriz: List[FilaEscala] = []

    # 1. San Elián (SEWSS)
    pts_prof = 3 if data.profundidad_tejido == "hueso_articulacion" else (2 if data.profundidad_tejido == "fascia_tendon" else 1)
    pts_inf = 3 if data.infeccion_severidad == "severa" else (2 if data.infeccion_severidad in ["leve", "moderada"] else 1)
    pts_isq = 3 if data.isquemia_estado == "critica" else (2 if data.isquemia_estado == "moderada" else 1)
    pts_area = 3 if data.area_cm2 > 5.0 else (2 if data.area_cm2 >= 1.5 else 1)
    pts_loc = 3 if data.localizacion == "talon" else (2 if data.localizacion == "antepie_plantar" else 1)
    pts_neuro = 2 if data.neuropatia_lops else 1
    
    score_se = pts_loc + 1 + 1 + pts_prof + pts_area + (2 if data.esfacelo_fibrina else 1) + pts_isq + pts_inf + pts_neuro + 1
    if score_se <= 10:
        se_grado, se_color = "Grado I (10 pts)", "verde"
        se_rec = "Manejo ambulatorio protocolizado y cura avanzada."
    elif score_se <= 20:
        se_grado, se_color = f"Grado II ({score_se} pts)", "amarillo"
        se_rec = "Desbridamiento activo + terapia multidisciplinaria (Rescate viable)."
    else:
        se_grado, se_color = f"Grado III ({score_se} pts)", "rojo"
        se_rec = "Internación hospitalaria urgente por alto riesgo de amputación mayor."

    matriz.append(FilaEscala(
        escala="San Elián (SEWSS)",
        clasificacion="Puntuación Pronóstica de Amputación vs Rescate",
        estadio_grado=se_grado,
        significado_clinico=f"Puntaje {score_se}/30. Estratificación anatómica y biológica combinada.",
        conducta_clave=se_rec,
        color_semaforo=se_color
    ))

    # 2. Universidad de Texas (UT Classification)
    grado_texas = "Grado 3" if data.profundidad_tejido == "hueso_articulacion" else ("Grado 2" if data.profundidad_tejido == "fascia_tendon" else "Grado 1")
    tiene_inf = data.infeccion_severidad in ["leve", "moderada", "severa"]
    tiene_isq = data.isquemia_estado in ["moderada", "critica"]
    
    if tiene_inf and tiene_isq:
        estadio_texas, texas_color = "Estadio D (Infección + Isquemia)", "rojo"
    elif tiene_inf:
        estadio_texas, texas_color = "Estadio B (Infectada)", "amarillo"
    elif tiene_isq:
        estadio_texas, texas_color = "Estadio C (Isquémica)", "amarillo"
    else:
        estadio_texas, texas_color = "Estadio A (Limpia, sin isquemia)", "verde"

    matriz.append(FilaEscala(
        escala="Universidad de Texas",
        clasificacion="Matriz Profundidad vs Isquemia/Infección",
        estadio_grado=f"{grado_texas} {estadio_texas}",
        significado_clinico="Evalúa sinergia deletérea entre hipoperfusión y biocarga profunda.",
        conducta_clave="Control infeccioso estricto y valoración vascular prioritaria.",
        color_semaforo=texas_color
    ))

    # 3. Wagner-Meggitt
    if data.isquemia_estado == "critica" and data.infeccion_severidad == "severa":
        wagner, wag_color = "Grado 4 (Gangrena localizada)", "rojo"
    elif data.profundidad_tejido == "hueso_articulacion":
        wagner, wag_color = "Grado 3 (Úlcera profunda con osteomielitis/absceso)", "rojo"
    elif data.profundidad_tejido == "fascia_tendon":
        wagner, wag_color = "Grado 2 (Úlcera profunda compromete tendón/fascia)", "amarillo"
    else:
        wagner, wag_color = "Grado 1 (Úlcera superficial sin afección profunda)", "verde"

    matriz.append(FilaEscala(
        escala="Wagner-Meggitt",
        clasificacion="Clasificación Anatómica Clásica (0 a 5)",
        estadio_grado=wagner,
        significado_clinico="Profundidad anatómica y presencia de gangrena.",
        conducta_clave="Tratamiento según profundidad tisular.",
        color_semaforo=wag_color
    ))

    # 4. IWGDF 2023 (Estratificación de Riesgo)
    if data.antecedente_ulcera_amputacion or data.profundidad_tejido != "superficial":
        iwgdf_grupo, iwgdf_color = "Grupo 3 (Riesgo Muy Alto)", "rojo"
        iwgdf_conducta = "Control cada 1-2 meses. Calzado terapéutico a medida con descarga."
    elif (data.neuropatia_lops and tiene_isq) or (data.neuropatia_lops and data.deformidad_pie):
        iwgdf_grupo, iwgdf_color = "Grupo 2 (Riesgo Alto)", "amarillo"
        iwgdf_conducta = "Control cada 2-3 meses. Evaluación biomecánica especializada."
    elif data.neuropatia_lops or tiene_isq:
        iwgdf_grupo, iwgdf_color = "Grupo 1 (Riesgo Moderado)", "verde"
        iwgdf_conducta = "Control cada 3-6 meses. Educación en autoinspección diaria."
    else:
        iwgdf_grupo, iwgdf_color = "Grupo 0 (Bajo Riesgo)", "verde"
        iwgdf_conducta = "Revisión anual de despistaje neurológico y vascular."

    matriz.append(FilaEscala(
        escala="IWGDF 2023",
        clasificacion="Estratificación Global de Prevención de Úlcera",
        estadio_grado=iwgdf_grupo,
        significado_clinico="Determina frecuencia de control y nivel de protección podológica.",
        conducta_clave=iwgdf_conducta,
        color_semaforo=iwgdf_color
    ))

    # 5. TIMERS (Manejo de Lecho)
    timers_desc = f"T: {'Desbridamiento de detritos' if data.esfacelo_fibrina else 'Lecho viable'} | I: {data.infeccion_severidad.upper()} | M: Exudado {data.exudado_humedad.upper()}"
    matriz.append(FilaEscala(
        escala="TIMERS",
        clasificacion="Matriz de Preparación del Lecho de la Herida",
        estadio_grado="Protocolo Activo",
        significado_clinico=timers_desc,
        conducta_clave="Apósitos específicos según humedad y biocarga.",
        color_semaforo="amarillo" if data.esfacelo_fibrina or data.exudado_humedad == "alto" else "verde"
    ))

    # 6. IDSA / IWGDF Infección
    idsa_color = "rojo" if data.infeccion_severidad == "severa" else ("amarillo" if data.infeccion_severidad == "moderada" else "verde")
    matriz.append(FilaEscala(
        escala="IDSA / PEDIS Infección",
        clasificacion="Criterios Clínicos de Severidad Infecciosa",
        estadio_grado=f"Infección {data.infeccion_severidad.capitalize()}",
        significado_clinico="Estratificación para antibioterapia empírica y vía de administración.",
        conducta_clave="Ajuste posológico según eGFR Cockcroft-Gault y cobertura dirigida.",
        color_semaforo=idsa_color
    ))

    return MatrizMultiescalaOutput(
        resumen_paciente=f"Lesión en {data.localizacion.replace('_', ' ').capitalize()} de {data.area_cm2} cm² con profundidad {data.profundidad_tejido.replace('_', ' ')}.",
        evaluacion_integral=matriz,
        consenso_multidisciplinar="Se requiere abordaje conjunto: Cirugía vascular (evaluación de flujo), Infectología (esquema antibiótico ajustado), Diabetología (optimización glucémica) y Podología (cura avanzada + off-loading)."
    )

# ── Endpoints ────────────────────────────────────────────────────────
@router_san_elian.post("/san-elian", response_model=SanElianOutput)
def endpoint_san_elian(payload: SanElianInput):
    return calcular_sewss(payload)

@router_san_elian.post("/matriz-multiescala", response_model=MatrizMultiescalaOutput)
def endpoint_matriz_multiescala(payload: MatrizMultiescalaInput):
    return generar_matriz_multiescala(payload)
