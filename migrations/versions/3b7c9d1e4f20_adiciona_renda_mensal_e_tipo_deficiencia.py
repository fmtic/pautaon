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

revision: str = "3b7c9d1e4f20"
down_revision: str | None = "29a29fdbc2aa"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Faixas antigas não têm valor exato; são descartadas em vez de estimadas.
    with op.batch_alter_table("perfil_socioeconomico") as batch_op:
        batch_op.alter_column(
            "renda_familiar",
            existing_type=sa.String(length=50),
            type_=sa.Numeric(12, 2),
            existing_nullable=True,
            postgresql_using="NULL::numeric",
        )

    #with op.batch_alter_table("perfil_diversidade") as batch_op:
        #batch_op.add_column(
            #sa.Column("tipo_deficiencia", sa.String(length=30), nullable=True)
        #)


def downgrade() -> None:
    with op.batch_alter_table("perfil_diversidade") as batch_op:
        batch_op.drop_column("tipo_deficiencia")

    with op.batch_alter_table("perfil_socioeconomico") as batch_op:
        batch_op.alter_column(
            "renda_familiar",
            existing_type=sa.Numeric(12, 2),
            type_=sa.String(length=50),
            existing_nullable=True,
            postgresql_using="NULL::text",
        )
