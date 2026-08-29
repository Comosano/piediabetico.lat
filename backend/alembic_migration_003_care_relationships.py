"""Crear tabla persistente care_relationships y sincronizar roles en PostgreSQL

Revision ID: 003_care_relationships
Revises: 002_privacy_and_consents
Create Date: 2026-08-29

Para ejecutar:
    alembic upgrade head

Para revertir:
    alembic downgrade 002_privacy_and_consents
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '003_care_relationships'
down_revision = '002_privacy_and_consents'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Sincronizar check constraint de roles en users ──────────────
    op.drop_constraint('ck_user_role', 'users', type_='check')
    op.create_check_constraint(
        'ck_user_role',
        'users',
        "role IN ('admin','medico_general','infectologo','diabetologo','cirujano_vascular','podologo','enfermero','profesional','universitario','investigador','paciente','cuidador')"
    )

    # ── 2. Crear tabla care_relationships ─────────────────────────────
    op.create_table('care_relationships',
        sa.Column('id',                postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('organization_id',   postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('patient_id',        postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id',           postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(30), nullable=False, server_default='medico_tratante'),
        sa.Column('is_active',         sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at',        sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('revoked_at',        sa.DateTime(timezone=True)),
        sa.CheckConstraint("relationship_type IN ('medico_tratante','cuidador','interconsultor','familiar')", name='ck_care_rel_type'),
        sa.UniqueConstraint('patient_id', 'user_id', name='uq_patient_user_rel'),
    )

    op.create_index('idx_care_rel_patient', 'care_relationships', ['patient_id'])
    op.create_index('idx_care_rel_user',    'care_relationships', ['user_id'])
    op.create_index('idx_care_rel_active',  'care_relationships', ['is_active'])


def downgrade() -> None:
    op.drop_index('idx_care_rel_active',  table_name='care_relationships')
    op.drop_index('idx_care_rel_user',    table_name='care_relationships')
    op.drop_index('idx_care_rel_patient', table_name='care_relationships')
    op.drop_table('care_relationships')

    op.drop_constraint('ck_user_role', 'users', type_='check')
    op.create_check_constraint(
        'ck_user_role',
        'users',
        "role IN ('admin','podologo','enfermero','infectologo','diabetologo','medico_general','universitario')"
    )
