"""Cria tabela de atendimentos individuais de alunos.

Cada linha representa um atendimento realizado por um usuário (pedagógico,
serviço social, secretaria ou admin) para um aluno específico. O campo
``dados`` (JSON) acomoda o conteúdo detalhado do formulário de forma flexível,
sem exigir novas colunas para cada campo futuro.

Revision ID: a1b2c3d4
Revises: 6a8df39d
Create Date: 2026-09-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4"
down_revision: str | None = "6a8df39d"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "atendimento",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("aluno_id", sa.Integer, sa.ForeignKey("aluno.id"), nullable=False),
        sa.Column("setor", sa.String(30), nullable=False),
        sa.Column("data_atendimento", sa.Date, nullable=False),
        sa.Column("resumo", sa.String(255), nullable=True),
        sa.Column("dados", sa.JSON, nullable=True),
        sa.Column("atendido_por_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("atendido_por_nome", sa.String(100), nullable=True),
        sa.Column("unidade_id", sa.Integer, sa.ForeignKey("unidade.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_atendimento_aluno_id", "atendimento", ["aluno_id"])
    op.create_index("ix_atendimento_data", "atendimento", ["data_atendimento"])


def downgrade() -> None:
    op.drop_index("ix_atendimento_data", table_name="atendimento")
    op.drop_index("ix_atendimento_aluno_id", table_name="atendimento")
    op.drop_table("atendimento")
