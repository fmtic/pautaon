"""adiciona renda mensal e tipo de deficiência

Revision ID: 3b7c9d1e4f20
Revises: 29a29fdbc2aa
Create Date: 2026-09-22

Substitui as faixas textuais de renda por um valor monetário e adiciona o
catálogo de tipo de deficiência ao perfil estruturado.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '3b7c9d1e4f20'
down_revision: str | None = '29a29fdbc2aa'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Faixas antigas não têm valor exato; são descartadas em vez de estimadas.
    op.alter_column(
        'perfil_socioeconomico',
        'renda_familiar',
        existing_type=sa.String(length=50),
        type_=sa.Numeric(12, 2),
        existing_nullable=True,
        postgresql_using='NULL::numeric',
    )
    op.add_column(
        'perfil_diversidade',
        sa.Column('tipo_deficiencia', sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('perfil_diversidade', 'tipo_deficiencia')
    op.alter_column(
        'perfil_socioeconomico',
        'renda_familiar',
        existing_type=sa.Numeric(12, 2),
        type_=sa.String(length=50),
        existing_nullable=True,
        postgresql_using='NULL::text',
    )
