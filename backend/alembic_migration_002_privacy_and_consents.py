"""Agregar consentimientos separados, categorias de imagen y privacy gate

Revision ID: 002_privacy_and_consents
Revises: 001_inicial
Create Date: 2026-08-29

Para ejecutar:
    alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002_privacy_and_consents'
down_revision = '001_inicial'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # ── 1. patient_consents (Consentimientos separados) ──────────────────
    op.create_table('patient_consents',
        sa.Column('id',            postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('patient_id',    postgresql.UUID(as_uuid=True), sa.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('consent_type',  sa.String(30), nullable=False), # 'clinico' | 'investigacion_ia'
        sa.Column('version',       sa.String(20), nullable=False, server_default='2026.1'),
        sa.Column('accepted',      sa.Boolean(), nullable=False),
        sa.Column('accepted_at',   sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('accepted_by_role', sa.String(30), nullable=False, server_default='paciente'), # 'paciente' | 'cuidador' | 'profesional'
        sa.Column('document_hash', sa.String(64)),
        sa.Column('created_at',    sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("consent_type IN ('clinico', 'investigacion_ia')", name='ck_consent_type'),
    )
    op.create_index('idx_consents_patient', 'patient_consents', ['patient_id'])
    op.create_index('idx_consents_type',    'patient_consents', ['consent_type'])

    # ── 2. Extender wound_images con niveles y privacy gate ──────────────
    op.add_column('wound_images', sa.Column('image_category', sa.String(30), nullable=False, server_default='clinical_processed'))
    op.add_column('wound_images', sa.Column('photo_uuid', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()')))
    op.add_column('wound_images', sa.Column('source_photo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('wound_images.id')))
    op.add_column('wound_images', sa.Column('processing_version', sa.String(20), server_default='v1.0'))
    op.add_column('wound_images', sa.Column('exif_sanitized', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('wound_images', sa.Column('privacy_gate_accepted', sa.Boolean(), nullable=False, server_default='true'))

    op.create_check_constraint(
        'ck_image_category',
        'wound_images',
        "image_category IN ('original_clinical', 'clinical_processed', 'research_anonymized')"
    )
    op.create_index('idx_images_category', 'wound_images', ['image_category'])
    op.create_index('idx_images_uuid',     'wound_images', ['photo_uuid'])

def downgrade() -> None:
    op.drop_index('idx_images_uuid', table_name='wound_images')
    op.drop_index('idx_images_category', table_name='wound_images')
    op.drop_constraint('ck_image_category', 'wound_images', type_='check')
    op.drop_column('wound_images', 'privacy_gate_accepted')
    op.drop_column('wound_images', 'exif_sanitized')
    op.drop_column('wound_images', 'processing_version')
    op.drop_column('wound_images', 'source_photo_id')
    op.drop_column('wound_images', 'photo_uuid')
    op.drop_column('wound_images', 'image_category')
    op.drop_table('patient_consents')
