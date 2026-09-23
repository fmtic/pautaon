"""amplia campo de programas sociais

Revision ID: 4c8e2f7a1b30
Revises: 3b7c9d1e4f20
Create Date: 2026-09-22

Permite armazenar vários nomes de programas sociais no mesmo perfil.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '4c8e2f7a1b30'
down_revision: str | None = '3b7c9d1e4f20'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        'perfil_socioeconomico',
        'beneficio_social_nome',
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'perfil_socioeconomico',
        'beneficio_social_nome',
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
