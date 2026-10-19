"""Torna o nome do nível único dentro de cada unidade.

Revision ID: c4d5e6f7a8b9
Revises: a9f3c8e2d1b7
"""

from alembic import op


revision = "c4d5e6f7a8b9"
down_revision = "a9f3c8e2d1b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nivel") as batch_op:
        batch_op.drop_constraint("nivel_nome_key", type_="unique")
        batch_op.create_unique_constraint(
            "uq_nivel_nome_unidade",
            ["nome", "unidade_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("nivel") as batch_op:
        batch_op.drop_constraint("uq_nivel_nome_unidade", type_="unique")
        batch_op.create_unique_constraint("nivel_nome_key", ["nome"])