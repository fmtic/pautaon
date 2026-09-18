"""onda2a: converte datas e horas string para DATE/TIME

Revision ID: a1bbf3c29231
Revises: 73f922fd358f
Create Date: 2026-09-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# Identificadores desta revisão
revision: str = "a1bbf3c29231"
down_revision: str | None = "73f922fd358f"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # =========================================================================
    # TURMA - datas e horas
    #
    # Turma.data_inicio/data_fim/hora_* são nullable=True no modelo, mas como
    # vinham de VARCHAR podem conter '' (string vazia). NULLIF transforma ''
    # em NULL antes do cast, evitando "invalid input syntax for type date".
    # =========================================================================
    with op.batch_alter_table("turma", schema=None) as batch_op:
        batch_op.alter_column(
            "data_inicio",
            existing_type=sa.VARCHAR(length=10),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using="NULLIF(data_inicio, '')::date",
        )
        batch_op.alter_column(
            "data_fim",
            existing_type=sa.VARCHAR(length=10),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using="NULLIF(data_fim, '')::date",
        )
        batch_op.alter_column(
            "hora_inicio",
            existing_type=sa.VARCHAR(length=5),
            type_=sa.Time(),
            existing_nullable=True,
            postgresql_using="NULLIF(hora_inicio, '')::time",
        )
        batch_op.alter_column(
            "hora_fim",
            existing_type=sa.VARCHAR(length=5),
            type_=sa.Time(),
            existing_nullable=True,
            postgresql_using="NULLIF(hora_fim, '')::time",
        )

    # =========================================================================
    # TEMA_AULA - data (nullable)
    # =========================================================================
    with op.batch_alter_table("tema_aula", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.VARCHAR(length=20),
            type_=sa.Date(),
            existing_nullable=True,
            postgresql_using="NULLIF(data, '')::date",
        )

    # =========================================================================
    # FREQUENCIA - data (NOT NULL)
    # =========================================================================
    with op.batch_alter_table("frequencia", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.VARCHAR(length=20),
            type_=sa.Date(),
            existing_nullable=False,
            postgresql_using="data::date",
        )

    # =========================================================================
    # REGISTRO_AULA - data (NOT NULL)
    # =========================================================================
    with op.batch_alter_table("registro_aula", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.VARCHAR(length=20),
            type_=sa.Date(),
            existing_nullable=False,
            postgresql_using="data::date",
        )

    # =========================================================================
    # DIA_BLOQUEADO_TURMA - data (NOT NULL)
    # =========================================================================
    with op.batch_alter_table("dia_bloqueado_turma", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.VARCHAR(length=10),
            type_=sa.Date(),
            existing_nullable=False,
            postgresql_using="data::date",
        )


def downgrade() -> None:
    # =========================================================================
    # Ordem inversa do upgrade.
    # =========================================================================
    with op.batch_alter_table("dia_bloqueado_turma", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=10),
            existing_nullable=False,
            postgresql_using="data::text",
        )

    with op.batch_alter_table("registro_aula", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=20),
            existing_nullable=False,
            postgresql_using="data::text",
        )

    with op.batch_alter_table("frequencia", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=20),
            existing_nullable=False,
            postgresql_using="data::text",
        )

    with op.batch_alter_table("tema_aula", schema=None) as batch_op:
        batch_op.alter_column(
            "data",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=20),
            existing_nullable=True,
            postgresql_using="data::text",
        )

    with op.batch_alter_table("turma", schema=None) as batch_op:
        batch_op.alter_column(
            "hora_fim",
            existing_type=sa.Time(),
            type_=sa.VARCHAR(length=5),
            existing_nullable=True,
            postgresql_using="hora_fim::text",
        )
        batch_op.alter_column(
            "hora_inicio",
            existing_type=sa.Time(),
            type_=sa.VARCHAR(length=5),
            existing_nullable=True,
            postgresql_using="hora_inicio::text",
        )
        batch_op.alter_column(
            "data_fim",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=10),
            existing_nullable=True,
            postgresql_using="data_fim::text",
        )
        batch_op.alter_column(
            "data_inicio",
            existing_type=sa.Date(),
            type_=sa.VARCHAR(length=10),
            existing_nullable=True,
            postgresql_using="data_inicio::text",
        )
