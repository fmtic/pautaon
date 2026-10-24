"""Require every enrollment to point to an offer and prevent active duplicates.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inscricoes") as batch_op:
        batch_op.alter_column(
            "turma_curso_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_index(
            "uix_inscricao_ativa_aluno_oferta",
            ["aluno_id", "turma_curso_id"],
            unique=True,
            postgresql_where=sa.text("ativo IS TRUE"),
            sqlite_where=sa.text("ativo = 1"),
        )


def downgrade():
    with op.batch_alter_table("inscricoes") as batch_op:
        batch_op.drop_index("uix_inscricao_ativa_aluno_oferta")
        batch_op.alter_column(
            "turma_curso_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
