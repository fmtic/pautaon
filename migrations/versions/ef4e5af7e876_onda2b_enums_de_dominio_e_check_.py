"""onda2b: enums de dominio e check constraints

Revision ID: ef4e5af7e876
Revises: a1bbf3c29231
Create Date: 2026-09-17
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ef4e5af7e876"
down_revision: str | None = "a1bbf3c29231"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        return

    op.execute(
        "CREATE TYPE conceito_frequencia_enum AS ENUM "
        "('A', 'B', 'C', 'D', 'F', 'J')"
    )
    op.execute(
        "CREATE TYPE tipo_dia_bloqueado_enum AS ENUM "
        "('FERIADO', 'ATIVIDADE_PEDAGOGICA', 'REUNIAO_PAIS', "
        "'ATIVIDADE_INTERNA', 'MANUTENCAO')"
    )
    op.execute(
        "CREATE TYPE etapa_conselho_enum AS ENUM "
        "('INICIAL', 'PERCURSO', 'FINAL')"
    )
    op.execute(
        "CREATE TYPE tipo_pergunta_enum AS ENUM "
        "('TURMA', 'ALUNO')"
    )

    op.alter_column(
        "frequencia",
        "conceito",
        type_=postgresql.ENUM(
            "A", "B", "C", "D", "F", "J",
            name="conceito_frequencia_enum",
            create_type=False,
        ),
        postgresql_using="conceito::conceito_frequencia_enum",
        existing_nullable=True,
    )

    op.alter_column(
        "dia_bloqueado",
        "tipo",
        type_=postgresql.ENUM(
            "FERIADO", "ATIVIDADE_PEDAGOGICA", "REUNIAO_PAIS",
            "ATIVIDADE_INTERNA", "MANUTENCAO",
            name="tipo_dia_bloqueado_enum",
            create_type=False,
        ),
        postgresql_using="tipo::tipo_dia_bloqueado_enum",
        existing_nullable=False,
    )

    op.alter_column(
        "conselho_classe",
        "etapa",
        type_=postgresql.ENUM(
            "INICIAL", "PERCURSO", "FINAL",
            name="etapa_conselho_enum",
            create_type=False,
        ),
        postgresql_using="etapa::etapa_conselho_enum",
        existing_nullable=False,
    )

    op.alter_column(
        "conselho_pergunta",
        "etapa",
        type_=postgresql.ENUM(
            "INICIAL", "PERCURSO", "FINAL",
            name="etapa_conselho_enum",
            create_type=False,
        ),
        postgresql_using="etapa::etapa_conselho_enum",
        existing_nullable=True,
    )

    op.alter_column(
        "conselho_pergunta",
        "tipo",
        type_=postgresql.ENUM(
            "TURMA", "ALUNO",
            name="tipo_pergunta_enum",
            create_type=False,
        ),
        postgresql_using="tipo::tipo_pergunta_enum",
        existing_nullable=True,
    )

    op.create_check_constraint(
        "ck_user_role",
        "user",
        "role IN ('admin', 'pedagogico', 'professor', 'secretaria', "
        "'servico_social', 'gerencia', 'pendente')",
    )

    op.create_check_constraint(
        "ck_conselho_situacao_final",
        "conselho_classe",
        "situacao_final IS NULL OR situacao_final IN "
        "('Aprovado', 'Reprovado por Falta', 'Desistente', 'Evadido', "
        "'Participação', 'Concluído')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_conselho_situacao_final",
        "conselho_classe",
        type_="check",
    )
    op.drop_constraint(
        "ck_user_role",
        "user",
        type_="check",
    )

    op.alter_column(
        "conselho_pergunta",
        "tipo",
        type_=sa.String(length=20),
        postgresql_using="tipo::text",
        existing_nullable=True,
    )

    op.alter_column(
        "conselho_pergunta",
        "etapa",
        type_=sa.String(length=20),
        postgresql_using="etapa::text",
        existing_nullable=True,
    )

    op.alter_column(
        "conselho_classe",
        "etapa",
        type_=sa.String(length=20),
        postgresql_using="etapa::text",
        existing_nullable=False,
    )

    op.alter_column(
        "dia_bloqueado",
        "tipo",
        type_=sa.String(length=50),
        postgresql_using="tipo::text",
        existing_nullable=False,
    )

    op.alter_column(
        "frequencia",
        "conceito",
        type_=sa.String(length=1),
        postgresql_using="conceito::text",
        existing_nullable=True,
    )

    op.execute("DROP TYPE IF EXISTS tipo_pergunta_enum")
    op.execute("DROP TYPE IF EXISTS etapa_conselho_enum")
    op.execute("DROP TYPE IF EXISTS tipo_dia_bloqueado_enum")
    op.execute("DROP TYPE IF EXISTS conceito_frequencia_enum")
