"""AJ18-B — data de entrada do aluno na oferta (Inscricao.data_entrada_oferta).

Revision ID: 1fdc7c03bdc2
Revises: f2a3b4c5d6e7
Create Date: 2026-11-10

Coluna nova nullable em `inscricoes`: NULL = desde o início (sem corte).
Migration aditiva, sem backfill; downgrade remove a coluna.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "1fdc7c03bdc2"
down_revision: str | None = "f2a3b4c5d6e7"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "inscricoes"
COLUNA = "data_entrada_oferta"


def _tem_coluna(bind, tabela: str, coluna: str) -> bool:
    insp = sa.inspect(bind)
    try:
        return coluna in {c["name"] for c in insp.get_columns(tabela)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    if _tem_coluna(bind, TABELA, COLUNA):
        return
    op.add_column(TABELA, sa.Column(COLUNA, sa.Date(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if not _tem_coluna(bind, TABELA, COLUNA):
        return
    op.drop_column(TABELA, COLUNA)
