"""ModeloCertificado: modelo do certificado por centro de custo do periodo

Revision ID: e1f2a3b4c5d6
Revises: c8d9e0f1a2b3
Create Date: 2026-10-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2a3b4c5d6'
down_revision = 'c8d9e0f1a2b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'modelo_certificado',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('periodo_letivo_id', sa.Integer(),
                  sa.ForeignKey('periodo_letivo.id'), nullable=False),
        sa.Column('centro_custo_id', sa.Integer(),
                  sa.ForeignKey('centro_custo.id'), nullable=False),
        sa.Column('arquivo', sa.String(length=255), nullable=False),
        sa.Column('nome_original', sa.String(length=255), nullable=True),
        sa.Column('tipo', sa.String(length=60), nullable=True),
        sa.Column('tamanho', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            'periodo_letivo_id',
            'centro_custo_id',
            name='uq_modelo_certificado_periodo_centro',
        ),
    )


def downgrade():
    op.drop_table('modelo_certificado')
