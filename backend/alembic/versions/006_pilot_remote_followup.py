"""Soporte para Remote Follow-up y PilotUploadToken

Revision ID: 006_pilot_remote_followup
Revises: 005_pilot_timeline
Create Date: 2026-08-29

Para ejecutar:
    alembic upgrade head

Para revertir:
    alembic downgrade 005_pilot_timeline
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '006_pilot_remote_followup'
down_revision = '005_pilot_timeline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('pilot_upload_tokens',
        sa.Column('id',             postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('token_hash',     sa.String(64), nullable=False),
        sa.Column('pilot_case_id',  postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pilot_wound_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pilot_wounds.id', ondelete='CASCADE'), nullable=False),
        sa.Column('physician_id',   postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at',     sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('due_at',         sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at',     sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at',        sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at',     sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('token_hash', name='uq_pilot_tokens_hash')
    )
    op.create_index('idx_pilot_tokens_hash',      'pilot_upload_tokens', ['token_hash'])
    op.create_index('idx_pilot_tokens_case',      'pilot_upload_tokens', ['pilot_case_id'])
    op.create_index('idx_pilot_tokens_wound',     'pilot_upload_tokens', ['pilot_wound_id'])
    op.create_index('idx_pilot_tokens_physician', 'pilot_upload_tokens', ['physician_id'])


def downgrade() -> None:
    op.drop_table('pilot_upload_tokens')
