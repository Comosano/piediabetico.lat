"""
╔══════════════════════════════════════════════════════════════════════╗
║  CELERY — Configuración y Tareas Programadas                        ║
║  piediabetico.lat — Versión 1.0.0                                   ║
╠══════════════════════════════════════════════════════════════════════╣
║  Pipeline semanal automático:                                       ║
║  Sábados a las 23:00 (hora Argentina, UTC-3)                        ║
║  PubMed → Redactor IA → Compilador PDF                             ║
║                                                                     ║
║  Variables de entorno necesarias en .env:                           ║
║    REDIS_URL=redis://redis:6379/0                                   ║
║    ANTHROPIC_API_KEY=sk-ant-...                                     ║
║    GEMINI_API_KEY=... (opcional)                                    ║
║                                                                     ║
║  Cómo agregar al Docker Compose:                                    ║
║    Ver sección al final de este archivo                             ║
╚══════════════════════════════════════════════════════════════════════╝

Para correr manualmente (desarrollo):
    # Terminal 1 — Worker
    celery -A celery_app worker --loglevel=info

    # Terminal 2 — Beat (programador)
    celery -A celery_app beat --loglevel=info

    # Disparar la tarea manualmente sin esperar el sábado:
    celery -A celery_app call celery_app.pipeline_semanal_completo
"""

import os
import logging
from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE CELERY
# ─────────────────────────────────────────────────────────────────────

# Redis como broker (cola de mensajes) y backend (guarda resultados)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "piediabetico",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    # Serialización
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Zona horaria — Argentina (UTC-3)
    timezone="America/Argentina/Buenos_Aires",
    enable_utc=True,

    # Reintentos automáticos si una tarea falla
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,

    # Resultados se guardan 24 horas
    result_expires=86400,

    # Prefetch — procesar de a una tarea por vez
    # (importante para tareas pesadas como llamadas a la API)
    worker_prefetch_multiplier=1,
)

# ─────────────────────────────────────────────────────────────────────
# PROGRAMACIÓN AUTOMÁTICA (CELERY BEAT)
# ─────────────────────────────────────────────────────────────────────
# crontab(hour=23, minute=0, day_of_week=6)
#   hour=23     → 23:00 hs
#   minute=0    → en punto
#   day_of_week=6 → sábado (0=lunes, 6=domingo en Celery)
# ─────────────────────────────────────────────────────────────────────

app.conf.beat_schedule = {
    "pipeline-semanal-sabados-23hs": {
        "task": "celery_app.pipeline_semanal_completo",
        "schedule": crontab(hour=23, minute=0, day_of_week=6),
        "options": {"expires": 3600},  # si no se ejecuta en 1h, descartarlo
    },
}

# ─────────────────────────────────────────────────────────────────────
# TAREA: PIPELINE SEMANAL COMPLETO
# ─────────────────────────────────────────────────────────────────────

@app.task(
    bind=True,
    name="celery_app.pipeline_semanal_completo",
    max_retries=2,
    default_retry_delay=300,  # reintentar en 5 minutos si falla
)
def pipeline_semanal_completo(self):
    """
    Pipeline semanal automático — se ejecuta cada sábado a las 23:00.

    Pasos:
        1. Agente 1 (PubMed) — busca artículos nuevos de la semana
        2. Agente 2 (Redactor IA) — genera resúmenes en español
        3. Agente 3 (PDF Compiler) — compila los PDFs clínicos

    Si algún paso falla, reintenta automáticamente hasta 2 veces.
    """
    logger.info("=" * 60)
    logger.info("[CELERY] Pipeline semanal iniciado — sábado 23:00")
    logger.info("=" * 60)

    # ── PASO 1: PubMed ────────────────────────────────────────────
    logger.info("[Paso 1/3] Agente 1 — PubMed Scraper")
    try:
        from pubmed_agent import PubMedScraperAgent
        scraper = PubMedScraperAgent()
        resultado_pubmed = scraper.execute_weekly_sync()
        if not resultado_pubmed:
            raise Exception("PubMedScraperAgent devolvió False — sin artículos nuevos o error de red.")
        logger.info("[Paso 1/3] ✓ PubMed completado")
    except ImportError:
        logger.error("[Paso 1/3] ✗ pubmed_agent.py no encontrado")
        raise self.retry(exc=Exception("pubmed_agent.py no disponible"))
    except Exception as e:
        logger.error(f"[Paso 1/3] ✗ Error en PubMed: {e}")
        raise self.retry(exc=e)

    # ── PASO 2: Redactor IA ───────────────────────────────────────
    logger.info("[Paso 2/3] Agente 2 — Redactor IA")
    try:
        from redactor_agent import RedactorAgent
        redactor = RedactorAgent()
        resultado_redactor = redactor.execute_translation_pipeline()
        if not resultado_redactor:
            raise Exception("RedactorAgent devolvió False — sin contenido para procesar.")
        logger.info("[Paso 2/3] ✓ Redactor completado")
    except ImportError:
        logger.error("[Paso 2/3] ✗ redactor_agent.py no encontrado")
        raise self.retry(exc=Exception("redactor_agent.py no disponible"))
    except Exception as e:
        logger.error(f"[Paso 2/3] ✗ Error en Redactor: {e}")
        raise self.retry(exc=e)

    # ── PASO 3: Compilador PDF ────────────────────────────────────
    logger.info("[Paso 3/3] Agente 3 — Compilador PDF")
    try:
        from pdf_agent import PDFCompilerAgent
        compiler = PDFCompilerAgent()
        resultado_pdf = compiler.compile_all_pdfs()
        if not resultado_pdf:
            raise Exception("PDFCompilerAgent devolvió False — error al compilar PDFs.")
        logger.info("[Paso 3/3] ✓ PDFs compilados")
    except ImportError:
        logger.error("[Paso 3/3] ✗ pdf_agent.py no encontrado")
        raise self.retry(exc=Exception("pdf_agent.py no disponible"))
    except Exception as e:
        logger.error(f"[Paso 3/3] ✗ Error en PDF Compiler: {e}")
        raise self.retry(exc=e)

    logger.info("=" * 60)
    logger.info("[CELERY] ✓ Pipeline semanal completado exitosamente")
    logger.info("=" * 60)

    return {
        "status": "completado",
        "pasos": ["pubmed", "redactor", "pdf"],
        "mensaje": "Pipeline semanal ejecutado correctamente el sábado 23:00"
    }


# ─────────────────────────────────────────────────────────────────────
# TAREA: DISPARADOR MANUAL (desde la API FastAPI)
# ─────────────────────────────────────────────────────────────────────

@app.task(
    name="celery_app.pipeline_manual",
    max_retries=1,
)
def pipeline_manual():
    """
    Igual que el pipeline semanal pero disparado manualmente
    desde el endpoint POST /orquestador/sync-semanal de FastAPI.
    Útil para pruebas o para forzar una actualización fuera de horario.
    """
    logger.info("[CELERY] Pipeline manual disparado desde la API")
    return pipeline_semanal_completo()


# ─────────────────────────────────────────────────────────────────────
# SEÑALES: log cuando una tarea falla definitivamente
# ─────────────────────────────────────────────────────────────────────

from celery.signals import task_failure

@task_failure.connect
def on_task_failure(task_id, exception, traceback, **kwargs):
    logger.error(
        f"[CELERY] Tarea fallida definitivamente — "
        f"task_id: {task_id}, error: {exception}"
    )
    # Aquí se puede agregar notificación por email o Slack en el futuro


# ─────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA (solo para desarrollo local)
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.start()


# ═════════════════════════════════════════════════════════════════════
# INSTRUCCIONES PARA AGREGAR AL DOCKER COMPOSE
# ═════════════════════════════════════════════════════════════════════
#
# Agregar estos dos servicios al docker-compose.yml existente,
# DESPUÉS del servicio "api":
#
# ─────────────────────────────────────────────────────────────────────
#
#   celery_worker:
#     build: ./backend
#     command: celery -A celery_app worker --loglevel=info --concurrency=2
#     restart: always
#     env_file: .env
#     depends_on:
#       - redis
#       - postgres
#     volumes:
#       - ./backend:/app
#
#   celery_beat:
#     build: ./backend
#     command: celery -A celery_app beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
#     restart: always
#     env_file: .env
#     depends_on:
#       - redis
#       - celery_worker
#     volumes:
#       - ./backend:/app
#
# ─────────────────────────────────────────────────────────────────────
#
# TAMBIÉN agregar en requirements.txt del backend:
#
#   celery[redis]==5.3.6
#   redis==5.0.1
#
# ─────────────────────────────────────────────────────────────────────
#
# VERIFICAR que está funcionando (en el VPS):
#
#   # Ver los workers activos
#   docker compose logs celery_worker
#
#   # Ver el programador beat
#   docker compose logs celery_beat
#
#   # Disparar el pipeline manualmente sin esperar el sábado:
#   docker compose exec celery_worker \
#     celery -A celery_app call celery_app.pipeline_semanal_completo
#
#   # Ver tareas programadas
#   docker compose exec celery_beat \
#     celery -A celery_app inspect scheduled
#
# ═════════════════════════════════════════════════════════════════════
