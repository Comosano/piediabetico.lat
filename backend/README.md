# 🦶 piediabetico.lat

**La plataforma clínica de pie diabético para Latinoamérica.**

IA especializada · Ficha fotográfica evolutiva · Calculadoras clínicas · Teleconsulta

---

## ¿Qué es?

piediabetico.lat es un ecosistema digital para el manejo integral del pie diabético en LATAM. Conecta pacientes, podólogos, enfermeros, infectólogos y diabetólogos alrededor de la ficha clínica del paciente.

**El problema que resuelve:** No existe ninguna plataforma gratuita, en español y especializada en pie diabético para los profesionales de Latinoamérica. El 85% de las amputaciones no traumáticas son prevenibles con seguimiento adecuado.

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Python 3.11 |
| Base de datos | PostgreSQL 16 + pgvector |
| Almacenamiento | MinIO (imágenes médicas) |
| Cola de tareas | Celery + Redis |
| IA clínica | Claude API (claude-sonnet-4-6) |
| Clasificador | EfficientNet-B0 ONNX (AUC 0.98) |
| Frontend | Next.js PWA |
| Infraestructura | Docker Compose + Nginx |
| VPS | Donweb Ubuntu Linux |

---

## Agentes clínicos

| Agente | Función | Estado |
|---|---|---|
| Agente 1 | PubMed Scraper — literatura semanal | ✅ Listo |
| Agente 2 | Redactor IA — resúmenes en español | ✅ Listo |
| Agente 3 | Compilador PDF — informes clínicos | ✅ Listo |
| Agente 4 | Clasificador ONNX — úlcera/piel sana | ✅ Listo |
| Agente 7 | Triage multimodal — Claude Vision | ✅ Listo |
| Agente 8 | IWGDF — estratificación de riesgo 0-3 | ✅ Listo |
| Agente 9 | TIMERS — apósitos y desbridamiento | ✅ Listo |
| Agente 10 | Off-loading — descarga biomecánica | ✅ Listo |
| Agente 11 | Antibióticos IDSA + ajuste renal | ✅ Listo |

---

## Estructura del repositorio

```
piediabetico/
├── backend/
│   ├── main.py                          # FastAPI — orquestador principal
│   ├── agente4_clasificador_ulcera.py   # Clasificador ONNX
│   ├── agente7_triage_multimodal.py     # Claude Vision por perfil
│   ├── agente7_prompt_paciente.py       # Prompt especializado paciente
│   ├── flujo_foto_integrado.py          # Flujo Agente 4 → Agente 7
│   ├── celery_app.py                    # Pipeline semanal automático
│   ├── models.py                        # Modelos SQLAlchemy
│   ├── pubmed_agent.py                  # Agente 1
│   ├── redactor_agent.py                # Agente 2
│   ├── pdf_agent.py                     # Agente 3
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 001_inicial.py
├── frontend/                            # Next.js PWA (en desarrollo)
├── modelos/                             # Archivos .onnx y .pth (no en Git)
├── data/                                # Datos persistentes (no en Git)
├── docker-compose.yml
├── alembic.ini
├── .env.example
├── .gitignore
└── README.md
```

---

## Instalación y configuración

### Prerrequisitos
- Docker y Docker Compose instalados
- Python 3.11+ (para desarrollo local)
- Acceso SSH al VPS

### 1. Clonar el repositorio
```bash
git clone https://github.com/tu-usuario/piediabetico.git
cd piediabetico
```

### 2. Configurar variables de entorno
```bash
cp .env.example .env
nano .env   # completar TODOS los [CAMBIAR_...]
```

Variables obligatorias:
```
POSTGRES_PASSWORD=...
MINIO_ROOT_PASSWORD=...
ANTHROPIC_API_KEY=sk-ant-...
SECRET_KEY=...   # generar con: python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Subir el modelo de IA
```bash
# Descargar dfu_efficientnet_b0.onnx de Google Drive: DFU/outputs/
mkdir -p modelos/
cp dfu_efficientnet_b0.onnx modelos/
```

### 4. Levantar los servicios
```bash
docker compose build
docker compose up -d
docker compose ps   # verificar que los 6 servicios están running
```

### 5. Ejecutar la migración de base de datos
```bash
docker compose exec api alembic upgrade head
```

### 6. Verificar
```bash
curl http://localhost:8000/          # healthcheck
curl http://localhost:8000/docs      # Swagger UI
```

---

## Endpoints principales

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/` | Healthcheck y lista de agentes |
| GET | `/docs` | Swagger UI interactivo |
| **POST** | **`/analizar-foto`** | **Flujo completo foto → análisis IA** |
| POST | `/agentes/clasificar-ulcera` | Agente 4 — clasificador ONNX |
| POST | `/agentes/triage-multimodal` | Agente 7 — Claude Vision |
| POST | `/agentes/iwgdf` | Agente 8 — estratificación IWGDF |
| POST | `/agentes/timers` | Agente 9 — apósitos TIMERS |
| POST | `/agentes/offloading` | Agente 10 — descarga biomecánica |
| POST | `/agentes/antibioticos` | Agente 11 — ATB + ajuste renal |
| POST | `/orquestador/sync-semanal` | Disparar pipeline PubMed manualmente |

---

## Pipeline semanal automático

El sistema ejecuta automáticamente cada **sábado a las 23:00 (hora Argentina)**:

```
PubMed (6 fuentes) → Redactor IA → PDFs clínicos
```

Para dispararlo manualmente:
```bash
curl -X POST http://localhost:8000/orquestador/sync-semanal
```

---

## Modelos de IA

### Agente 4 — Clasificador binario
- **Modelo:** EfficientNet-B0
- **Dataset:** DFU (Diabetic Foot Ulcer) — 1055 imágenes de entrenamiento
- **Métricas:** AUC ~0.98 | Accuracy ~95% en validación
- **Formato:** ONNX (corre en CPU, sin GPU necesaria)
- **Umbral clínico:** 0.35 (más sensible para uso clínico)

### Agente 7 — Triage multimodal
- **Modelo:** Claude Sonnet (claude-sonnet-4-6) con visión
- **Perfiles:** paciente / podólogo-enfermero / infectólogo / diabetólogo / médico general
- **Guías:** IWGDF 2023, IDSA, TIMERS

---

## Migraciones de base de datos

```bash
# Ver estado actual
alembic current

# Aplicar migraciones pendientes
alembic upgrade head

# Crear nueva migración (después de modificar models.py)
alembic revision --autogenerate -m "descripcion del cambio"
alembic upgrade head

# Revertir última migración
alembic downgrade -1
```

---

## Comandos útiles

```bash
# Ver logs de la API
docker compose logs api

# Ver logs de Celery en tiempo real
docker compose logs -f celery_worker

# Reiniciar la API
docker compose restart api

# Backup de la base de datos
docker compose exec postgres pg_dump -U adminpd piediadbetico > backup_$(date +%Y%m%d).sql

# Ver espacio en disco
df -h && du -sh data/
```

---

## Disclaimer clínico

> **AVISO:** Todas las calculadoras clínicas, el análisis de imágenes con IA y las sugerencias de la plataforma son herramientas de **referencia educativa** basadas en guías internacionales (IWGDF 2023, IDSA). No constituyen diagnóstico médico ni prescripción terapéutica. Toda decisión clínica debe ser adoptada por un **profesional de la salud habilitado**.

---

## Roadmap 2026

| Fecha | Hito |
|---|---|
| Sep 19, 2026 | MVP funcional — backend completo + ficha fotográfica |
| Nov 2026 | ALAD Cusco — presentación con usuarios reales |
| Dic 2026 | AMEXIPIED Zacatecas — presentación formal |
| 2027 | Escalado LATAM — capital semilla + hackathones |

---

## Contacto

📧 contacto@piediabetico.lat  
🌐 piediabetico.lat

---

*© 2026 piediabetico.lat — Plataforma clínica de pie diabético para Latinoamérica*
