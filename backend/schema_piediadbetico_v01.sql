-- ============================================================
-- PIEDIABETICO.LAT — Esquema de Base de Datos v0.1
-- PostgreSQL 16 + pgvector
-- Generado: Agosto 2026
-- ============================================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgvector;

-- ============================================================
-- DOMINIO 1: ORGANIZACIONES Y USUARIOS
-- ============================================================

CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(200) NOT NULL,
    slug            VARCHAR(100) UNIQUE NOT NULL,       -- ej: "hospital-garrahan"
    country         CHAR(2) NOT NULL DEFAULT 'AR',      -- ISO 3166-1 alpha-2
    plan            VARCHAR(20) NOT NULL DEFAULT 'free' CHECK (plan IN ('free','pro','institution')),
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(200) NOT NULL,
    role            VARCHAR(30) NOT NULL CHECK (role IN (
                        'admin',
                        'podologo',
                        'enfermero',
                        'infectologo',
                        'diabetologo',
                        'medico_general',
                        'universitario'
                    )),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices críticos de aislamiento por organización
CREATE INDEX idx_users_org ON users(organization_id);
CREATE UNIQUE INDEX idx_users_email ON users(email);

-- ============================================================
-- DOMINIO 2: PACIENTES (identificadores separados de datos clínicos)
-- ============================================================

CREATE TABLE patients (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    -- Identificadores separados del historial clínico (privacidad)
    mrn             VARCHAR(50),                        -- Número de historia clínica
    -- Datos demográficos mínimos
    birth_year      SMALLINT CHECK (birth_year BETWEEN 1900 AND 2025),
    sex             CHAR(1) CHECK (sex IN ('M','F','X')),
    country         CHAR(2) DEFAULT 'AR',
    -- Datos clínicos base (no identificatorios)
    diabetes_type   VARCHAR(10) CHECK (diabetes_type IN ('T1','T2','MODY','otro')),
    diagnosis_year  SMALLINT,
    -- Estado del paciente
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      UUID NOT NULL REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Un paciente pertenece estrictamente a una organización
CREATE INDEX idx_patients_org ON patients(organization_id);

-- ============================================================
-- DOMINIO 3: EPISODIOS Y EVALUACIONES CLÍNICAS
-- ============================================================

-- Evaluación clínica del pie (examen físico completo)
CREATE TABLE foot_assessments (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id              UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    assessed_by             UUID NOT NULL REFERENCES users(id),
    assessed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Neuropatía (monofilamento 10g: cuántos de 10 puntos detectados)
    monofilament_right      SMALLINT CHECK (monofilament_right BETWEEN 0 AND 10),
    monofilament_left       SMALLINT CHECK (monofilament_left BETWEEN 0 AND 10),
    -- Vascular
    pulse_right_pedio       BOOLEAN,
    pulse_right_tibial      BOOLEAN,
    pulse_left_pedio        BOOLEAN,
    pulse_left_tibial       BOOLEAN,
    itb_right               NUMERIC(4,2),               -- Índice tobillo-brazo
    itb_left                NUMERIC(4,2),
    -- Deformidades
    deformity_present       BOOLEAN DEFAULT FALSE,
    deformity_notes         TEXT,
    -- Antecedentes
    prev_ulcer              BOOLEAN DEFAULT FALSE,
    prev_amputation         BOOLEAN DEFAULT FALSE,
    charcot_active          BOOLEAN DEFAULT FALSE,
    -- Metabólico
    hba1c                   NUMERIC(4,1),               -- % HbA1c
    creatinine              NUMERIC(5,2),               -- mg/dL
    egfr                    NUMERIC(6,1),               -- Calculado Cockcroft-Gault
    -- Resultado IWGDF calculado (agente 8)
    iwgdf_risk_group        SMALLINT CHECK (iwgdf_risk_group BETWEEN 0 AND 3),
    iwgdf_followup_months   SMALLINT,
    -- Notas clínicas
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_assessments_patient ON foot_assessments(patient_id);
CREATE INDEX idx_assessments_date ON foot_assessments(assessed_at);

-- ============================================================
-- DOMINIO 4: HERIDAS
-- ============================================================

CREATE TABLE wounds (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    created_by      UUID NOT NULL REFERENCES users(id),
    -- Localización anatómica
    foot_side       CHAR(1) NOT NULL CHECK (foot_side IN ('D','I')), -- Derecho/Izquierdo
    location        VARCHAR(50) NOT NULL CHECK (location IN (
                        'plantar_antepie',
                        'plantar_mediopie',
                        'plantar_talon',
                        'dorsal',
                        'lateral',
                        'medial',
                        'interdigital',
                        'periungeal',
                        'muñon',
                        'otro'
                    )),
    location_notes  TEXT,
    -- Etiología
    etiology        VARCHAR(30) CHECK (etiology IN (
                        'neuropatica',
                        'isquemica',
                        'neuroisquemica',
                        'traumatica',
                        'postquirurgica',
                        'otra'
                    )),
    -- Estado general
    status          VARCHAR(20) NOT NULL DEFAULT 'activa' CHECK (status IN (
                        'activa',
                        'cicatrizada',
                        'amputada',
                        'cerrada_alta'
                    )),
    first_seen_at   DATE NOT NULL DEFAULT CURRENT_DATE,
    closed_at       DATE,
    -- Clasificación inicial
    wagner_grade    SMALLINT CHECK (wagner_grade BETWEEN 0 AND 5),
    texas_grade     VARCHAR(4),                         -- ej: "1A", "3B"
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wounds_patient ON wounds(patient_id);
CREATE INDEX idx_wounds_status ON wounds(status);

-- ============================================================
-- DOMINIO 5: EVALUACIONES DE HERIDA (TIMERS)
-- ============================================================

CREATE TABLE wound_evaluations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wound_id            UUID NOT NULL REFERENCES wounds(id) ON DELETE RESTRICT,
    evaluated_by        UUID NOT NULL REFERENCES users(id),
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- TIMERS
    tissue_necrotic     BOOLEAN DEFAULT FALSE,          -- T: tejido no viable
    tissue_notes        TEXT,
    infection_present   BOOLEAN DEFAULT FALSE,          -- I: infección/inflamación
    infection_signs     TEXT,                           -- eritema, calor, secreción
    moisture_high       BOOLEAN DEFAULT FALSE,          -- M: humedad/exudado
    exudate_amount      VARCHAR(10) CHECK (exudate_amount IN ('ninguno','escaso','moderado','abundante')),
    exudate_type        VARCHAR(20) CHECK (exudate_type IN ('seroso','serosanguinolento','purulento','necrotico')),
    edge_stalled        BOOLEAN DEFAULT FALSE,          -- E: bordes estancados
    edge_notes          TEXT,
    -- Resultado TIMERS (agente 9 - referencia educativa)
    timers_dressing_suggestion  TEXT,
    timers_debridement          TEXT,
    timers_frequency            TEXT,
    timers_disclaimer           TEXT DEFAULT 'Sugerencia educativa. No reemplaza el criterio clínico.',
    -- Notas clínicas libres (puede ser dictado por voz)
    clinical_notes      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wound_evals_wound ON wound_evaluations(wound_id);
CREATE INDEX idx_wound_evals_date ON wound_evaluations(evaluated_at);

-- ============================================================
-- DOMINIO 6: IMÁGENES
-- ============================================================

CREATE TABLE wound_images (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wound_id            UUID NOT NULL REFERENCES wounds(id) ON DELETE RESTRICT,
    wound_evaluation_id UUID REFERENCES wound_evaluations(id),
    uploaded_by         UUID NOT NULL REFERENCES users(id),
    -- Almacenamiento en MinIO
    storage_bucket      VARCHAR(100) NOT NULL,
    storage_key         VARCHAR(500) NOT NULL,          -- clave del objeto en MinIO
    file_hash_sha256    CHAR(64) NOT NULL,              -- hash del archivo original (inmutable)
    file_size_bytes     INTEGER,
    mime_type           VARCHAR(50) DEFAULT 'image/jpeg',
    -- Metadatos de captura
    device_type         VARCHAR(50),                    -- "mobile_android", "mobile_ios", etc.
    capture_method      VARCHAR(20) DEFAULT 'camera' CHECK (capture_method IN ('camera','gallery','upload')),
    -- Control de calidad de la imagen
    qc_blur_score       NUMERIC(5,3),                   -- 0=muy borrosa, 1=perfecta
    qc_exposure_ok      BOOLEAN,
    qc_scale_detected   BOOLEAN DEFAULT FALSE,          -- ¿se detectó marcador de referencia?
    qc_scale_px_per_mm  NUMERIC(8,4),                   -- píxeles por mm calculados
    qc_passed           BOOLEAN DEFAULT FALSE,
    qc_rejection_reason VARCHAR(100),
    -- Lateralidad y ángulo
    foot_side           CHAR(1) CHECK (foot_side IN ('D','I')),
    capture_angle       VARCHAR(20),                    -- "plantar", "dorsal", "lateral"
    -- Estado
    is_primary          BOOLEAN DEFAULT FALSE,          -- foto principal del episodio
    taken_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_images_wound ON wound_images(wound_id);
CREATE INDEX idx_images_eval ON wound_images(wound_evaluation_id);
CREATE INDEX idx_images_date ON wound_images(taken_at);

-- ============================================================
-- DOMINIO 7: INFERENCIAS DE IA
-- ============================================================

CREATE TABLE model_versions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(100) NOT NULL,              -- "FUSegNet v1.0", "HarDNet-DFUS v1.0"
    version         VARCHAR(30) NOT NULL,
    model_type      VARCHAR(30) NOT NULL CHECK (model_type IN (
                        'segmentacion',
                        'clasificacion_tisular',
                        'clasificacion_ulcera',
                        'explicabilidad',
                        'triage_multimodal'
                    )),
    architecture    VARCHAR(100),                       -- "EfficientNet-b7 + scSE"
    dataset_trained VARCHAR(200),                       -- "FUSeg 2021 + DFUC2022"
    dice_score      NUMERIC(5,4),                       -- métrica de evaluación
    iou_score       NUMERIC(5,4),
    weights_path    VARCHAR(500),                       -- ruta al archivo .pth/.onnx en MinIO
    is_active       BOOLEAN NOT NULL DEFAULT FALSE,     -- solo uno activo por tipo
    deployed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE inference_runs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    image_id            UUID NOT NULL REFERENCES wound_images(id) ON DELETE RESTRICT,
    model_version_id    UUID NOT NULL REFERENCES model_versions(id),
    -- Resultado de segmentación
    mask_storage_key    VARCHAR(500),                   -- máscara binaria en MinIO
    area_cm2            NUMERIC(8,4),                   -- área calculada
    area_px             INTEGER,
    -- Resultado de clasificación tisular
    granulation_pct     NUMERIC(5,2),                   -- % granulación
    fibrin_pct          NUMERIC(5,2),                   -- % fibrina/esfacelo
    necrosis_pct        NUMERIC(5,2),                   -- % necrosis
    -- Resultado de triage (Agente 7 - Claude Vision)
    triage_severity     SMALLINT CHECK (triage_severity BETWEEN 0 AND 10),
    triage_color        VARCHAR(10) CHECK (triage_color IN ('verde','amarillo','rojo')),
    triage_narrative    TEXT,
    triage_disclaimer   TEXT DEFAULT 'Análisis asistido por IA. Requiere validación clínica.',
    -- Cuestionario post-foto (Curapp)
    questionnaire_data  JSONB,                          -- respuestas al cuestionario dinámico
    -- Metadatos de ejecución
    inference_ms        INTEGER,                        -- tiempo en milisegundos
    error_message       TEXT,                           -- null si exitoso
    status              VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','success','failed','rejected')),
    -- Revisión humana obligatoria
    reviewed_by         UUID REFERENCES users(id),
    reviewed_at         TIMESTAMPTZ,
    review_action       VARCHAR(20) CHECK (review_action IN ('aceptado','corregido','rechazado')),
    correction_notes    TEXT,
    corrected_area_cm2  NUMERIC(8,4),                   -- si el clínico corrigió el área
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inferences_image ON inference_runs(image_id);
CREATE INDEX idx_inferences_status ON inference_runs(status);
CREATE INDEX idx_inferences_model ON inference_runs(model_version_id);

-- ============================================================
-- DOMINIO 8: INFORMES PDF
-- ============================================================

CREATE TABLE generated_reports (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_id          UUID NOT NULL REFERENCES patients(id),
    generated_by        UUID NOT NULL REFERENCES users(id),
    report_type         VARCHAR(30) NOT NULL CHECK (report_type IN (
                        'evolucion_herida',
                        'evaluacion_clinica',
                        'resumen_cientifico_semanal'
                    )),
    -- Contenido
    title               VARCHAR(300),
    period_start        DATE,
    period_end          DATE,
    -- Almacenamiento
    storage_key         VARCHAR(500),                   -- PDF en MinIO
    file_hash_sha256    CHAR(64),
    -- Control de versiones
    version             SMALLINT NOT NULL DEFAULT 1,
    supersedes_id       UUID REFERENCES generated_reports(id),
    -- Disclaimer obligatorio
    clinical_disclaimer TEXT NOT NULL DEFAULT 'Este informe es una herramienta de apoyo clínico. No reemplaza el diagnóstico ni el tratamiento médico.',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_patient ON generated_reports(patient_id);

-- ============================================================
-- DOMINIO 9: PIPELINE CIENTÍFICO (Agentes 1-2-3)
-- ============================================================

CREATE TABLE scientific_articles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pmid            VARCHAR(20) UNIQUE,                 -- PubMed ID
    doi             VARCHAR(200),
    title           TEXT NOT NULL,
    authors         TEXT[],
    journal         VARCHAR(300),
    pub_date        DATE,
    abstract        TEXT,
    url             VARCHAR(500),
    -- Procesamiento
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_duplicate    BOOLEAN DEFAULT FALSE,
    source          VARCHAR(50) DEFAULT 'pubmed'
);

CREATE TABLE scientific_summaries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id      UUID NOT NULL REFERENCES scientific_articles(id),
    audience        VARCHAR(20) NOT NULL CHECK (audience IN ('medico','paciente','general')),
    summary_text    TEXT NOT NULL,
    -- Embeddings para búsqueda semántica (pgvector)
    embedding       VECTOR(1536),
    -- Control de calidad
    generated_by    VARCHAR(50) DEFAULT 'claude-sonnet-4-6',
    reviewed        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_summaries_article ON scientific_summaries(article_id);
CREATE INDEX idx_summaries_embedding ON scientific_summaries USING ivfflat (embedding vector_cosine_ops);

-- ============================================================
-- DOMINIO 10: AUDITORÍA (trazabilidad completa)
-- ============================================================

CREATE TABLE audit_events (
    id              BIGSERIAL PRIMARY KEY,              -- BIGSERIAL para volumen
    user_id         UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    -- Qué pasó
    event_type      VARCHAR(50) NOT NULL CHECK (event_type IN (
                        'login',
                        'logout',
                        'patient_create',
                        'patient_view',
                        'patient_update',
                        'image_upload',
                        'image_view',
                        'inference_run',
                        'inference_review',
                        'report_generate',
                        'report_download',
                        'data_export',
                        'user_create',
                        'user_update',
                        'config_change'
                    )),
    entity_type     VARCHAR(50),                        -- "patient", "wound", "image"
    entity_id       UUID,
    -- Contexto
    ip_address      INET,
    user_agent      TEXT,
    extra_data      JSONB,                              -- datos adicionales del evento
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Particionamiento por mes para escalabilidad (opcional en fase inicial)
CREATE INDEX idx_audit_user ON audit_events(user_id);
CREATE INDEX idx_audit_org ON audit_events(organization_id);
CREATE INDEX idx_audit_type ON audit_events(event_type);
CREATE INDEX idx_audit_date ON audit_events(occurred_at);
CREATE INDEX idx_audit_entity ON audit_events(entity_type, entity_id);

-- ============================================================
-- FUNCIONES DE UTILIDAD
-- ============================================================

-- Auto-actualizar updated_at en cada UPDATE
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Aplicar trigger a todas las tablas con updated_at
CREATE TRIGGER trg_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_wounds_updated_at
    BEFORE UPDATE ON wounds
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- DATOS INICIALES (seeds para desarrollo)
-- ============================================================

INSERT INTO organizations (name, slug, country, plan)
VALUES ('Organización Demo', 'demo', 'AR', 'pro');

INSERT INTO model_versions (name, version, model_type, architecture, dataset_trained, dice_score, iou_score)
VALUES
    ('FUSegNet', '1.0', 'segmentacion', 'EfficientNet-b7 + scSE', 'FUSeg 2021', 0.9270, 0.8630),
    ('HarDNet-DFUS', '1.0', 'segmentacion', 'HarDNet-85', 'DFUC2022', 0.0000, 0.0000); -- actualizar con benchmark

-- ============================================================
-- COMENTARIOS FINALES
-- ============================================================
-- Reglas de seguridad a implementar en la capa API (Row Level Security):
--   - Un usuario solo puede ver pacientes de su propia organización
--   - Las inferencias son inmutables (no se permite UPDATE/DELETE)
--   - Los informes PDF mantienen versión anterior al ser reemplazados
--   - La auditoría es append-only (no se permite UPDATE/DELETE)
--   - Las imágenes se almacenan en MinIO con URLs firmadas (expiración 1 hora)
