"""Integridad de Runtime IA y Estados Granulares (Pilot v0.1)

Revision ID: 007_pilot_ai_runtime_integrity
Revises: 006_pilot_remote_followup
Create Date: 2026-08-29

Para ejecutar:
    alembic upgrade head

Para revertir:
    alembic downgrade 006_pilot_remote_followup
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '007_pilot_ai_runtime_integrity'
down_revision = '006_pilot_remote_followup'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Agregar estados granulares de IA a pilot_analyses ───────────
    op.add_column(
        'pilot_analyses',
        sa.Column('classification_status', sa.String(50), nullable=True, server_default='SKIPPED')
    )
    op.add_column(
        'pilot_analyses',
        sa.Column('segmentation_status', sa.String(50), nullable=True, server_default='SKIPPED')
    )


def downgrade() -> None:
    op.drop_column('pilot_analyses', 'segmentation_status')
    op.drop_column('pilot_analyses', 'classification_status')
