"""Require every course offer to have a program.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("""
        UPDATE turma
        SET programa = (
            SELECT tc.programa
            FROM turma_curso AS tc
            WHERE tc.turma_id = turma.id AND tc.ativo IS TRUE
            ORDER BY tc.principal DESC, tc.id ASC
            LIMIT 1
        )
    """))
    with op.batch_alter_table("turma_curso") as batch_op:
        batch_op.alter_column(
            "programa",
            existing_type=sa.String(length=50),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("turma_curso") as batch_op:
        batch_op.alter_column(
            "programa",
            existing_type=sa.String(length=50),
            nullable=True,
        )
