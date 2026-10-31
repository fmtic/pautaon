"""S1-11/S1-12 — tabela login_controle (rate limit por conta e por IP).

Revision ID: c1d2e3f4a5b6
Revises: b5c6d7e8f9a0
Create Date: 2026-10-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b5c6d7e8f9a0"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "login_controle"


def _tabelas() -> set[str]:
    insp = sa.inspect(op.get_bind())
    try:
        return set(insp.get_table_names())
    except Exception:
        return set()


def upgrade() -> None:
    if TABELA in _tabelas():
        return
    op.create_table(
        TABELA,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("escopo", sa.String(10), nullable=False),
        sa.Column("chave_hash", sa.String(64), nullable=False),
        sa.Column("falhas", sa.Integer, nullable=False, server_default="0"),
        sa.Column("janela_inicio", sa.DateTime, nullable=True),
        sa.Column("bloqueado_ate", sa.DateTime, nullable=True),
        sa.Column("nivel", sa.Integer, nullable=False, server_default="0"),
        sa.Column("atualizado_em", sa.DateTime, nullable=True),
    )
    op.create_unique_constraint(
        "uq_login_controle_escopo_chave", TABELA, ["escopo", "chave_hash"]
    )


def downgrade() -> None:
    if TABELA not in _tabelas():
        return
    op.drop_table(TABELA)
