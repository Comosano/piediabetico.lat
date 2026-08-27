"""Crear tablas iniciales piediabetico.lat

Revision ID: 001_inicial
Revises: 
Create Date: 2026-08-22

Para ejecutar:
    alembic upgrade head

Para revertir:
    alembic downgrade base
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_inicial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensiones necesarias
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS pgvector')

    # ── organizations ──────────────────────────────────────────
    op.create_table('organizations',
        sa.Column('id',         postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name',       sa.String(200),  nullable=False),
        sa.Column('slug',       sa.String(100),  nullable=False, unique=True),
        sa.Column('country',    sa.String(2),    nullable=False, server_default='AR'),
        sa.Column('plan',       sa.String(20),   nullable=False, server_default='free'),
        sa.Column('active',     sa.Boolean(),    nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("plan IN ('free','pro','institution')", name='ck_org_plan'),
    )

    # ── users ──────────────────────────────────────────────────
    op.create_table('users',
        sa.Column('id',              postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('email',           sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash',   sa.String(255), nullable=False),
        sa.Column('full_name',       sa.String(200), nullable=False),
        sa.Column('role',            sa.String(30),  nullable=False),
        sa.Column('is_active',       sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('last_login_at',   sa.DateTime(timezone=True)),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "role IN ('admin','podologo','enfermero','infectologo','diabetologo','medico_general','universitario')",
            name='ck_user_role'
        ),
    )
    op.create_index('idx_users_org', 'users', ['organization_id'])

    # ── patients ───────────────────────────────────────────────
    op.create_table('patients',
        sa.Column('id',              postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_by',      postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('mrn',             sa.String(50)),
        sa.Column('birth_year',      sa.SmallInteger()),
        sa.Column('sex',             sa.String(1)),
        sa.Column('country',         sa.String(2), server_default='AR'),
        sa.Column('diabetes_type',   sa.String(10)),
        sa.Column('diagnosis_year',  sa.SmallInteger()),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("birth_year BETWEEN 1900 AND 2025",          name='ck_patient_birth_year'),
        sa.CheckConstraint("sex IN ('M','F','X')",                       name='ck_patient_sex'),
        sa.CheckConstraint("diabetes_type IN ('T1','T2','MODY','otro')", name='ck_patient_diabetes_type'),
    )
    op.create_index('idx_patients_org', 'patients', ['organization_id'])

    # ── foot_assessments ───────────────────────────────────────
    op.create_table('foot_assessments',
        sa.Column('id',                   postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('patient_id',           postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('assessed_by',          postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assessed_at',          sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('monofilament_right',   sa.SmallInteger()),
        sa.Column('monofilament_left',    sa.SmallInteger()),
        sa.Column('pulse_right_pedio',    sa.Boolean()),
        sa.Column('pulse_right_tibial',   sa.Boolean()),
        sa.Column('pulse_left_pedio',     sa.Boolean()),
        sa.Column('pulse_left_tibial',    sa.Boolean()),
        sa.Column('itb_right',            sa.Numeric(4, 2)),
        sa.Column('itb_left',             sa.Numeric(4, 2)),
        sa.Column('deformity_present',    sa.Boolean(), server_default='false'),
        sa.Column('deformity_notes',      sa.Text()),
        sa.Column('prev_ulcer',           sa.Boolean(), server_default='false'),
        sa.Column('prev_amputation',      sa.Boolean(), server_default='false'),
        sa.Column('charcot_active',       sa.Boolean(), server_default='false'),
        sa.Column('hba1c',                sa.Numeric(4, 1)),
        sa.Column('creatinine',           sa.Numeric(5, 2)),
        sa.Column('egfr',                 sa.Numeric(6, 1)),
        sa.Column('iwgdf_risk_group',     sa.SmallInteger()),
        sa.Column('iwgdf_followup_months',sa.SmallInteger()),
        sa.Column('notes',                sa.Text()),
        sa.Column('created_at',           sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("monofilament_right BETWEEN 0 AND 10", name='ck_mono_right'),
        sa.CheckConstraint("monofilament_left BETWEEN 0 AND 10",  name='ck_mono_left'),
        sa.CheckConstraint("iwgdf_risk_group BETWEEN 0 AND 3",    name='ck_iwgdf_group'),
    )
    op.create_index('idx_assessments_patient', 'foot_assessments', ['patient_id'])
    op.create_index('idx_assessments_date',    'foot_assessments', ['assessed_at'])

    # ── wounds ─────────────────────────────────────────────────
    op.create_table('wounds',
        sa.Column('id',            postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('patient_id',    postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('created_by',    postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('foot_side',     sa.String(1),  nullable=False),
        sa.Column('location',      sa.String(50), nullable=False),
        sa.Column('location_notes',sa.Text()),
        sa.Column('etiology',      sa.String(30)),
        sa.Column('status',        sa.String(20), nullable=False, server_default='activa'),
        sa.Column('first_seen_at', sa.Date(), server_default=sa.func.current_date()),
        sa.Column('closed_at',     sa.Date()),
        sa.Column('wagner_grade',  sa.SmallInteger()),
        sa.Column('texas_grade',   sa.String(4)),
        sa.Column('notes',         sa.Text()),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("foot_side IN ('D','I')",                                        name='ck_wound_foot_side'),
        sa.CheckConstraint("status IN ('activa','cicatrizada','amputada','cerrada_alta')",  name='ck_wound_status'),
        sa.CheckConstraint("wagner_grade BETWEEN 0 AND 5",                                 name='ck_wagner_grade'),
    )
    op.create_index('idx_wounds_patient', 'wounds', ['patient_id'])
    op.create_index('idx_wounds_status',  'wounds', ['status'])

    # ── wound_evaluations ──────────────────────────────────────
    op.create_table('wound_evaluations',
        sa.Column('id',                         postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('wound_id',                   postgresql.UUID(as_uuid=True), sa.ForeignKey('wounds.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('evaluated_by',               postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('evaluated_at',               sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('tissue_necrotic',            sa.Boolean(), server_default='false'),
        sa.Column('tissue_notes',               sa.Text()),
        sa.Column('infection_present',          sa.Boolean(), server_default='false'),
        sa.Column('infection_signs',            sa.Text()),
        sa.Column('moisture_high',              sa.Boolean(), server_default='false'),
        sa.Column('exudate_amount',             sa.String(10)),
        sa.Column('exudate_type',               sa.String(20)),
        sa.Column('edge_stalled',               sa.Boolean(), server_default='false'),
        sa.Column('edge_notes',                 sa.Text()),
        sa.Column('timers_dressing_suggestion', sa.Text()),
        sa.Column('timers_debridement',         sa.Text()),
        sa.Column('timers_frequency',           sa.String(100)),
        sa.Column('timers_disclaimer',          sa.Text(), nullable=False,
                  server_default="'Sugerencia educativa basada en guías TIMERS. No reemplaza el criterio clínico del profesional.'"),
        sa.Column('clinical_notes',             sa.Text()),
        sa.Column('created_at',                 sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("exudate_amount IN ('ninguno','escaso','moderado','abundante')",           name='ck_exudate_amount'),
        sa.CheckConstraint("exudate_type IN ('seroso','serosanguinolento','purulento','necrotico')", name='ck_exudate_type'),
    )
    op.create_index('idx_wound_evals_wound', 'wound_evaluations', ['wound_id'])
    op.create_index('idx_wound_evals_date',  'wound_evaluations', ['evaluated_at'])

    # ── wound_images ───────────────────────────────────────────
    op.create_table('wound_images',
        sa.Column('id',                  postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('wound_id',            postgresql.UUID(as_uuid=True), sa.ForeignKey('wounds.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('wound_evaluation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('wound_evaluations.id')),
        sa.Column('uploaded_by',         postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('storage_bucket',      sa.String(100), nullable=False),
        sa.Column('storage_key',         sa.String(500), nullable=False),
        sa.Column('file_hash_sha256',    sa.String(64),  nullable=False),
        sa.Column('file_size_bytes',     sa.Integer()),
        sa.Column('mime_type',           sa.String(50),  server_default='image/jpeg'),
        sa.Column('device_type',         sa.String(50)),
        sa.Column('capture_method',      sa.String(20),  server_default='camera'),
        sa.Column('qc_blur_score',       sa.Numeric(5, 3)),
        sa.Column('qc_exposure_ok',      sa.Boolean()),
        sa.Column('qc_scale_detected',   sa.Boolean(), server_default='false'),
        sa.Column('qc_scale_px_per_mm',  sa.Numeric(8, 4)),
        sa.Column('qc_passed',           sa.Boolean(), server_default='false'),
        sa.Column('qc_rejection_reason', sa.String(100)),
        sa.Column('foot_side',           sa.String(1)),
        sa.Column('capture_angle',       sa.String(20)),
        sa.Column('is_primary',          sa.Boolean(), server_default='false'),
        sa.Column('taken_at',            sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at',          sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("capture_method IN ('camera','gallery','upload')", name='ck_capture_method'),
        sa.CheckConstraint("foot_side IN ('D','I')",                          name='ck_image_foot_side'),
    )
    op.create_index('idx_images_wound', 'wound_images', ['wound_id'])
    op.create_index('idx_images_eval',  'wound_images', ['wound_evaluation_id'])
    op.create_index('idx_images_date',  'wound_images', ['taken_at'])

    # ── model_versions ─────────────────────────────────────────
    op.create_table('model_versions',
        sa.Column('id',              postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name',            sa.String(100), nullable=False),
        sa.Column('version',         sa.String(30),  nullable=False),
        sa.Column('model_type',      sa.String(30),  nullable=False),
        sa.Column('architecture',    sa.String(100)),
        sa.Column('dataset_trained', sa.String(200)),
        sa.Column('dice_score',      sa.Numeric(5, 4)),
        sa.Column('iou_score',       sa.Numeric(5, 4)),
        sa.Column('weights_path',    sa.String(500)),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deployed_at',     sa.DateTime(timezone=True)),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "model_type IN ('segmentacion','clasificacion_tisular','clasificacion_ulcera','explicabilidad','triage_multimodal')",
            name='ck_model_type'
        ),
    )

    # ── inference_runs ─────────────────────────────────────────
    op.create_table('inference_runs',
        sa.Column('id',                 postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('image_id',           postgresql.UUID(as_uuid=True), sa.ForeignKey('wound_images.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('model_version_id',   postgresql.UUID(as_uuid=True), sa.ForeignKey('model_versions.id'), nullable=False),
        sa.Column('mask_storage_key',   sa.String(500)),
        sa.Column('area_cm2',           sa.Numeric(8, 4)),
        sa.Column('area_px',            sa.Integer()),
        sa.Column('granulation_pct',    sa.Numeric(5, 2)),
        sa.Column('fibrin_pct',         sa.Numeric(5, 2)),
        sa.Column('necrosis_pct',       sa.Numeric(5, 2)),
        sa.Column('triage_severity',    sa.SmallInteger()),
        sa.Column('triage_color',       sa.String(10)),
        sa.Column('triage_narrative',   sa.Text()),
        sa.Column('triage_disclaimer',  sa.Text(), nullable=False,
                  server_default="'Análisis asistido por IA. Requiere validación del profesional de salud.'"),
        sa.Column('questionnaire_data', postgresql.JSONB()),
        sa.Column('inference_ms',       sa.Integer()),
        sa.Column('error_message',      sa.Text()),
        sa.Column('status',             sa.String(20), nullable=False, server_default='pending'),
        sa.Column('reviewed_by',        postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at',        sa.DateTime(timezone=True)),
        sa.Column('review_action',      sa.String(20)),
        sa.Column('correction_notes',   sa.Text()),
        sa.Column('corrected_area_cm2', sa.Numeric(8, 4)),
        sa.Column('created_at',         sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("triage_severity BETWEEN 0 AND 10",                       name='ck_triage_severity'),
        sa.CheckConstraint("triage_color IN ('verde','amarillo','rojo')",             name='ck_triage_color'),
        sa.CheckConstraint("status IN ('pending','success','failed','rejected')",     name='ck_inference_status'),
        sa.CheckConstraint("review_action IN ('aceptado','corregido','rechazado')",   name='ck_review_action'),
    )
    op.create_index('idx_inferences_image',  'inference_runs', ['image_id'])
    op.create_index('idx_inferences_status', 'inference_runs', ['status'])
    op.create_index('idx_inferences_model',  'inference_runs', ['model_version_id'])

    # ── generated_reports ──────────────────────────────────────
    op.create_table('generated_reports',
        sa.Column('id',                  postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('patient_id',          postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id'), nullable=False),
        sa.Column('generated_by',        postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('report_type',         sa.String(30), nullable=False),
        sa.Column('title',               sa.String(300)),
        sa.Column('period_start',        sa.Date()),
        sa.Column('period_end',          sa.Date()),
        sa.Column('storage_key',         sa.String(500)),
        sa.Column('file_hash_sha256',    sa.String(64)),
        sa.Column('version',             sa.SmallInteger(), nullable=False, server_default='1'),
        sa.Column('supersedes_id',       postgresql.UUID(as_uuid=True), sa.ForeignKey('generated_reports.id')),
        sa.Column('clinical_disclaimer', sa.Text(), nullable=False,
                  server_default="'Este informe es una herramienta de apoyo clínico. No reemplaza el diagnóstico ni el tratamiento médico.'"),
        sa.Column('created_at',          sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "report_type IN ('evolucion_herida','evaluacion_clinica','resumen_cientifico_semanal')",
            name='ck_report_type'
        ),
    )
    op.create_index('idx_reports_patient', 'generated_reports', ['patient_id'])

    # ── scientific_articles ────────────────────────────────────
    op.create_table('scientific_articles',
        sa.Column('id',           postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('pmid',         sa.String(20), unique=True),
        sa.Column('doi',          sa.String(200)),
        sa.Column('title',        sa.Text(), nullable=False),
        sa.Column('journal',      sa.String(300)),
        sa.Column('pub_date',     sa.Date()),
        sa.Column('abstract',     sa.Text()),
        sa.Column('url',          sa.String(500)),
        sa.Column('fetched_at',   sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('is_duplicate', sa.Boolean(), server_default='false'),
        sa.Column('source',       sa.String(50), server_default='pubmed'),
    )

    # ── scientific_summaries ───────────────────────────────────
    op.create_table('scientific_summaries',
        sa.Column('id',           postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('article_id',   postgresql.UUID(as_uuid=True), sa.ForeignKey('scientific_articles.id'), nullable=False),
        sa.Column('audience',     sa.String(20), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('generated_by', sa.String(50), server_default='claude-sonnet-4-6'),
        sa.Column('reviewed',     sa.Boolean(), server_default='false'),
        sa.Column('created_at',   sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("audience IN ('medico','paciente','general')", name='ck_summary_audience'),
    )
    op.create_index('idx_summaries_article', 'scientific_summaries', ['article_id'])
    # Nota: el índice de embedding (pgvector) se agrega manualmente después del CREATE TABLE
    # op.execute("CREATE INDEX ON scientific_summaries USING ivfflat (embedding vector_cosine_ops)")

    # ── audit_events ───────────────────────────────────────────
    op.create_table('audit_events',
        sa.Column('id',              sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id',         postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id')),
        sa.Column('event_type',      sa.String(50), nullable=False),
        sa.Column('entity_type',     sa.String(50)),
        sa.Column('entity_id',       postgresql.UUID(as_uuid=True)),
        sa.Column('ip_address',      sa.String(45)),
        sa.Column('user_agent',      sa.Text()),
        sa.Column('extra_data',      postgresql.JSONB()),
        sa.Column('occurred_at',     sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.CheckConstraint("""
            event_type IN (
                'login','logout',
                'patient_create','patient_view','patient_update',
                'image_upload','image_view',
                'inference_run','inference_review',
                'report_generate','report_download',
                'data_export','user_create','user_update','config_change'
            )
        """, name='ck_audit_event_type'),
    )
    op.create_index('idx_audit_user',   'audit_events', ['user_id'])
    op.create_index('idx_audit_org',    'audit_events', ['organization_id'])
    op.create_index('idx_audit_type',   'audit_events', ['event_type'])
    op.create_index('idx_audit_entity', 'audit_events', ['entity_type', 'entity_id'])

    # ── Datos iniciales (seeds) ─────────────────────────────────
    op.execute("""
        INSERT INTO organizations (name, slug, country, plan)
        VALUES ('Organización Demo', 'demo', 'AR', 'pro')
    """)
    op.execute("""
        INSERT INTO model_versions (name, version, model_type, architecture, dataset_trained, dice_score, iou_score)
        VALUES
            ('FUSegNet',      '1.0', 'segmentacion', 'EfficientNet-b7 + scSE', 'FUSeg 2021',  0.9270, 0.8630),
            ('HarDNet-DFUS',  '1.0', 'segmentacion', 'HarDNet-85',             'DFUC2022',    0.0000, 0.0000)
    """)


def downgrade() -> None:
    """Elimina todas las tablas en orden inverso (respetando FK)."""
    tables = [
        'audit_events',
        'scientific_summaries',
        'scientific_articles',
        'generated_reports',
        'inference_runs',
        'model_versions',
        'wound_images',
        'wound_evaluations',
        'wounds',
        'foot_assessments',
        'patients',
        'users',
        'organizations',
    ]
    for table in tables:
        op.drop_table(table)
