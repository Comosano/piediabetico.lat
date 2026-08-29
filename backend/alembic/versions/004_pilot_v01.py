"""Crear tablas para Piloto Cerrado v0.1 y columna pilot_enabled en users

Revision ID: 004_pilot_v01
Revises: 003_care_relationships
Create Date: 2026-08-29

Para ejecutar:
    alembic upgrade head

Para revertir:
    alembic downgrade 003_care_relationships
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '004_pilot_v01'
down_revision = '003_care_relationships'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Agregar pilot_enabled a users ──────────────────────────────
    op.add_column('users', sa.Column('pilot_enabled', sa.Boolean(), nullable=False, server_default='false'))

    # ── 2. Crear tabla pilot_cases ────────────────────────────────────
    op.create_table('pilot_cases',
        sa.Column('id',              postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('pilot_case_uuid', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('physician_id',    postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_active',       sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at',      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('pilot_case_uuid', name='uq_pilot_case_uuid')
    )
    op.create_index('idx_pilot_cases_physician', 'pilot_cases', ['physician_id'])
    op.create_index('idx_pilot_cases_uuid',      'pilot_cases', ['pilot_case_uuid'])

    # ── 3. Crear tabla pilot_analyses ─────────────────────────────────
    op.create_table('pilot_analyses',
        sa.Column('id',                        postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('pilot_case_id',              postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('physician_id',               postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analysis_uuid',              postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('photo_uuid',                 postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('photo_storage_key',          sa.String(500), nullable=True),
        sa.Column('photo_mime_type',            sa.String(50), nullable=False, server_default='image/jpeg'),
        sa.Column('privacy_gate_confirmed',     sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('quality_gate_score',         sa.Integer(), nullable=True),
        sa.Column('quality_gate_status',        sa.String(50), nullable=True),
        sa.Column('ai_status',                  sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('model_name',                 sa.String(100), nullable=False, server_default='EfficientNet-B0 + U-Net'),
        sa.Column('model_version',              sa.String(50), nullable=False, server_default='1.0.0'),
        sa.Column('classification_label',       sa.String(100), nullable=True),
        sa.Column('classification_confidence',  sa.Numeric(5, 4), nullable=True),
        sa.Column('scale_detected',             sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('pixel_area',                 sa.Integer(), nullable=True),
        sa.Column('relative_area_percent',      sa.Numeric(5, 2), nullable=True),
        sa.Column('absolute_area_cm2',          sa.Numeric(8, 2), nullable=True),
        sa.Column('segmentation_mask_key',      sa.String(500), nullable=True),
        sa.Column('shadow_mode_assessment',     postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('processing_duration_ms',     sa.Integer(), nullable=True),
        sa.Column('created_at',                 sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at',                 sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at',                 sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('analysis_uuid', name='uq_pilot_analysis_uuid'),
        sa.UniqueConstraint('photo_uuid',    name='uq_pilot_photo_uuid')
    )
    op.create_index('idx_pilot_analysis_case',      'pilot_analyses', ['pilot_case_id'])
    op.create_index('idx_pilot_analysis_physician', 'pilot_analyses', ['physician_id'])
    op.create_index('idx_pilot_analysis_uuid',      'pilot_analyses', ['analysis_uuid'])
    op.create_index('idx_pilot_analysis_expires',   'pilot_analyses', ['expires_at'])

    # ── 4. Crear tabla pilot_feedbacks ────────────────────────────────
    op.create_table('pilot_feedbacks',
        sa.Column('id',                          postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('analysis_id',                 postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('physician_id',                postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_clinically_evaluable',     sa.Boolean(), nullable=False),
        sa.Column('segmentation_rating',         sa.String(50), nullable=False),
        sa.Column('concordance_rating',          sa.String(50), nullable=False),
        sa.Column('would_modify_classification', sa.Boolean(), nullable=False),
        sa.Column('utility_score',               sa.SmallInteger(), nullable=False),
        sa.Column('comment',                     sa.String(250), nullable=True),
        sa.Column('created_at',                  sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("segmentation_rating IN ('Correcta','Parcial','Incorrecta')", name='ck_pilot_fb_seg'),
        sa.CheckConstraint("concordance_rating IN ('Sí','Parcial','No')", name='ck_pilot_fb_conc'),
        sa.CheckConstraint("utility_score BETWEEN 1 AND 5", name='ck_pilot_fb_utility'),
        sa.UniqueConstraint('analysis_id', name='uq_pilot_feedback_analysis')
    )
    op.create_index('idx_pilot_fb_analysis',  'pilot_feedbacks', ['analysis_id'])
    op.create_index('idx_pilot_fb_physician', 'pilot_feedbacks', ['physician_id'])


def downgrade() -> None:
    op.drop_table('pilot_feedbacks')
    op.drop_table('pilot_analyses')
    op.drop_table('pilot_cases')
    op.drop_column('users', 'pilot_enabled')
