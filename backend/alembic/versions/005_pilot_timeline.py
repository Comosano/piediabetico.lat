"""Soporte para Timeline Retrospectivo, PilotWound y PilotEvolutionFeedback

Revision ID: 005_pilot_timeline
Revises: 004_pilot_v01
Create Date: 2026-08-29

Para ejecutar:
    alembic upgrade head

Para revertir:
    alembic downgrade 004_pilot_v01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '005_pilot_timeline'
down_revision = '004_pilot_v01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Agregar case_alias a pilot_cases ────────────────────────────
    op.add_column('pilot_cases', sa.Column('case_alias', sa.String(50), nullable=True))
    op.create_index('idx_pilot_cases_alias', 'pilot_cases', ['case_alias'])

    # ── 2. Crear tabla pilot_wounds ────────────────────────────────────
    op.create_table('pilot_wounds',
        sa.Column('id',            postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('wound_uuid',    postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('pilot_case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('wound_label',   sa.String(100), nullable=False, server_default='Herida 1'),
        sa.Column('wound_location',sa.String(100), nullable=False, server_default='Plantar'),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('wound_uuid', name='uq_pilot_wound_uuid')
    )
    op.create_index('idx_pilot_wounds_case', 'pilot_wounds', ['pilot_case_id'])
    op.create_index('idx_pilot_wounds_uuid', 'pilot_wounds', ['wound_uuid'])

    # ── 3. Agregar columnas a pilot_analyses ───────────────────────────
    op.add_column('pilot_analyses', sa.Column('pilot_wound_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_wounds.id', ondelete='SET NULL'), nullable=True))
    op.add_column('pilot_analyses', sa.Column('taken_at_custom', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pilot_analyses', sa.Column('sequence_index', sa.Integer(), nullable=True))
    op.add_column('pilot_analyses', sa.Column('classification_status', sa.String(50), nullable=True, server_default='SKIPPED'))
    op.add_column('pilot_analyses', sa.Column('segmentation_status', sa.String(50), nullable=True, server_default='SKIPPED'))
    op.create_index('idx_pilot_analysis_wound', 'pilot_analyses', ['pilot_wound_id'])

    # ── 4. Crear tabla pilot_evolution_feedbacks ──────────────────────
    op.create_table('pilot_evolution_feedbacks',
        sa.Column('id',                              postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('baseline_analysis_id',            postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('followup_analysis_id',            postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_analyses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('physician_id',                    postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('clinical_evolution',              sa.String(20), nullable=False),
        sa.Column('system_representation_agreement', sa.String(20), nullable=False),
        sa.Column('comment',                         sa.String(250), nullable=True),
        sa.Column('created_at',                      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("clinical_evolution IN ('MEJOR','SIMILAR','PEOR')", name='ck_pilot_evol_rating'),
        sa.CheckConstraint("system_representation_agreement IN ('SI','PARCIAL','NO')", name='ck_pilot_evol_agree')
    )
    op.create_index('idx_pilot_evol_baseline',  'pilot_evolution_feedbacks', ['baseline_analysis_id'])
    op.create_index('idx_pilot_evol_followup',  'pilot_evolution_feedbacks', ['followup_analysis_id'])
    op.create_index('idx_pilot_evol_physician', 'pilot_evolution_feedbacks', ['physician_id'])


def downgrade() -> None:
    op.drop_table('pilot_evolution_feedbacks')
    op.drop_index('idx_pilot_analysis_wound', table_name='pilot_analyses')
    op.drop_column('pilot_analyses', 'sequence_index')
    op.drop_column('pilot_analyses', 'taken_at_custom')
    op.drop_column('pilot_analyses', 'pilot_wound_id')
    op.drop_table('pilot_wounds')
    op.drop_index('idx_pilot_cases_alias', table_name='pilot_cases')
    op.drop_column('pilot_cases', 'case_alias')
