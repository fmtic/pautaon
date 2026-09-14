"""Adiciona campo ordem ao modelo TemaAula.

O campo ``ordem`` permite controlar a sequência de exibição dos temas
no planejamento pedagógico. Cada tema pode ter uma ordem numérica
para facilitar a organização cronológica dos conteúdos.

Revision ID: b2c3d4e5
Revises: a1b2c3d4
Create Date: 2026-09-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Identificadores desta revisão
# ---------------------------------------------------------------------------
revision: str = "b2c3d4e5"
down_revision: str | None = "7aa724d05691"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Aplica as alterações ao banco — adiciona o campo ordem."""
    with op.batch_alter_table("tema_aula", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "ordem",
                sa.Integer(),
                nullable=False,
                server_default="0"
            )
        )


def downgrade() -> None:
    """Reverte as alterações — remove o campo ordem."""
    with op.batch_alter_table("tema_aula", schema=None) as batch_op:
        batch_op.drop_column("ordem")
