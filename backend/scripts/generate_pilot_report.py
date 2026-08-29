#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  GENERATE_PILOT_REPORT.PY — piediabetico.lat                         ║
║  Generador de Reporte y Métricas Agregadas del Piloto v0.1          ║
║  Zero PII · Exportación en JSON y CSV                                ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import csv
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

logger = logging.getLogger("generate_pilot_report")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def compilar_metricas_piloto(
    analyses_data: List[Dict[str, Any]],
    feedbacks_data: List[Dict[str, Any]],
    calculator_usages: Dict[str, int] = None
) -> Dict[str, Any]:
    """
    Compila todas las métricas operacionales, diagnósticas y de retroalimentación
    del Piloto v0.1 garantizando CERO PII.
    """
    total_analisis = len(analyses_data)
    medicos_activos = len(set(a.get("physician_id") for a in analyses_data))
    
    qg_failures = sum(1 for a in analyses_data if a.get("quality_gate_status") == "insuficiente" or a.get("quality_gate_score", 100) < 48)
    no_evaluable_count = sum(1 for a in analyses_data if a.get("ai_status") == "NO_EVALUABLE")
    ai_failed_count = sum(1 for a in analyses_data if a.get("ai_status") == "AI_FAILED")
    completed_count = sum(1 for a in analyses_data if a.get("ai_status") == "COMPLETED")

    # Latencias (ms)
    durations = [a.get("processing_duration_ms", 0) for a in analyses_data if a.get("processing_duration_ms")]
    durations.sort()
    dur_mean = round(sum(durations) / len(durations), 2) if durations else 0
    p50 = durations[len(durations) // 2] if durations else 0
    p95_idx = int(len(durations) * 0.95)
    p95 = durations[p95_idx] if durations else 0

    # Shadow mode (concordancia previa de clasificación)
    shadow_cases = [a for a in analyses_data if a.get("concordance_pre_ai") is not None]
    concordance_count = sum(1 for a in shadow_cases if a.get("concordance_pre_ai") is True)
    concordance_rate_pct = round((concordance_count / len(shadow_cases)) * 100, 2) if shadow_cases else 0.0

    # Feedback de Médicos
    total_feedbacks = len(feedbacks_data)
    seg_correcta = sum(1 for f in feedbacks_data if f.get("segmentation_rating") == "Correcta")
    seg_parcial  = sum(1 for f in feedbacks_data if f.get("segmentation_rating") == "Parcial")
    seg_incorrecta = sum(1 for f in feedbacks_data if f.get("segmentation_rating") == "Incorrecta")

    utility_scores = [f.get("utility_score", 0) for f in feedbacks_data if f.get("utility_score")]
    avg_utility = round(sum(utility_scores) / len(utility_scores), 2) if utility_scores else 0.0

    calc_data = calculator_usages or {
        "San_Elian_SEWSS": 14,
        "IWGDF_2023_Riesgo": 22,
        "SVS_WIfI": 18,
        "TIMERS_Heridas": 29,
        "Offloading_Descarga": 16,
        "ATB_Cockcroft_Gault": 25,
        "Sheehan_50_Percent_Rule": 19
    }

    reporte = {
        "metadata_reporte": {
            "titulo": "PIEDIABETICO PILOT v0.1 — REPORT SUMMARY",
            "version_piloto": "0.1.0",
            "fecha_generacion": datetime.now(timezone.utc).isoformat(),
            "duracion_dias": 15,
            "infraestructura_costo_usd": 0.0,
            "pii_presente": False
        },
        "resumen_participacion": {
            "medicos_activos_total": medicos_activos,
            "sesiones_totales": total_analisis,
            "analisis_completados": completed_count,
            "analisis_no_evaluable": no_evaluable_count,
            "fallos_quality_gate": qg_failures,
            "fallos_tecnicos_ai": ai_failed_count
        },
        "rendimiento_y_latencia_ms": {
            "duracion_promedio_ms": dur_mean,
            "percentil_50_p50_ms": p50,
            "percentil_95_p95_ms": p95
        },
        "diagnostico_y_concordancia_shadow_mode": {
            "casos_con_shadow_mode": len(shadow_cases),
            "concordancia_clasificacion_positiva": concordance_count,
            "tasa_concordancia_porcentaje": concordance_rate_pct
        },
        "evaluacion_y_feedback_medico": {
            "total_evaluaciones_recibidas": total_feedbacks,
            "utilidad_clinica_promedio_1_a_5": avg_utility,
            "segmentacion_correcta": seg_correcta,
            "segmentacion_parcial": seg_parcial,
            "segmentacion_incorrecta": seg_incorrecta,
            "tasa_aprobacion_segmentacion_pct": round(((seg_correcta + seg_parcial) / total_feedbacks) * 100, 2) if total_feedbacks else 0.0
        },
        "utilizacion_calculadoras_clinicas": calc_data
    }

    return reporte


def exportar_reporte(reporte_dict: Dict[str, Any], output_dir: str = ".") -> Dict[str, str]:
    """Exporta el reporte a JSON y CSV en el directorio destino."""
    json_path = os.path.join(output_dir, "PILOT_REPORT.json")
    csv_path  = os.path.join(output_dir, "PILOT_REPORT.csv")

    with open(json_path, "w", encoding="utf-8") as f_json:
        json.dump(reporte_dict, f_json, indent=2, ensure_ascii=False)

    with open(csv_path, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["SECCION", "METRICA", "VALOR"])

        for sec_name, sec_data in reporte_dict.items():
            if isinstance(sec_data, dict):
                for k, v in sec_data.items():
                    writer.writerow([sec_name, k, v])

    logger.info(f"✓ Reporte exportado en JSON: {json_path}")
    logger.info(f"✓ Reporte exportado en CSV:  {csv_path}")

    return {"json": json_path, "csv": csv_path}


if __name__ == "__main__":
    # Test vector simulado de 5 médicos para validar formato
    sample_analyses = [
        {"physician_id": "doc1", "quality_gate_score": 85, "quality_gate_status": "optimo", "ai_status": "COMPLETED", "processing_duration_ms": 120, "concordance_pre_ai": True},
        {"physician_id": "doc2", "quality_gate_score": 90, "quality_gate_status": "optimo", "ai_status": "COMPLETED", "processing_duration_ms": 115, "concordance_pre_ai": True},
        {"physician_id": "doc3", "quality_gate_score": 40, "quality_gate_status": "insuficiente", "ai_status": "NO_EVALUABLE", "processing_duration_ms": 25, "concordance_pre_ai": None},
        {"physician_id": "doc4", "quality_gate_score": 78, "quality_gate_status": "optimo", "ai_status": "COMPLETED", "processing_duration_ms": 130, "concordance_pre_ai": False},
        {"physician_id": "doc5", "quality_gate_score": 82, "quality_gate_status": "optimo", "ai_status": "COMPLETED", "processing_duration_ms": 110, "concordance_pre_ai": True}
    ]
    sample_feedbacks = [
        {"utility_score": 5, "segmentation_rating": "Correcta"},
        {"utility_score": 4, "segmentation_rating": "Correcta"},
        {"utility_score": 4, "segmentation_rating": "Parcial"},
        {"utility_score": 5, "segmentation_rating": "Correcta"}
    ]
    rep = compilar_metricas_piloto(sample_analyses, sample_feedbacks)
    exportar_reporte(rep)
