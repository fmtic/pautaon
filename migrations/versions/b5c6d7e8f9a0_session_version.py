"""S1-06 — versão de sessão por usuário em `user`.

Revision ID: b5c6d7e8f9a0
Revises: c9d0e1f2a3b4
Create Date: 2026-10-30

Contexto: o logout só apagava o cookie do navegador. Uma cópia do cookie
seguia autenticando até o `PERMANENT_SESSION_LIFETIME` (60 min deslizantes),
inclusive em outro dispositivo — provado no S1 §7.4.

A coluna `session_version` guarda um contador por usuário. O login grava o
valor atual em `session["sv"]` e o `user_loader` compara com o banco: qualquer
incremento (logout, troca de senha, reset, mudança de papel/unidade, exclusão)
invalida todas as sessões emitidas antes.

Migration aditiva e idempotente por inspeção: `upgrade` só adiciona a coluna
(com `DEFAULT 0`, então as linhas existentes ficam em 0 sem backfill) e
`downgrade` só remove. Nenhuma linha é tocada em nenhuma das direções.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b5c6d7e8f9a0"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "user"
COLUNA = "session_version"
COMENTARIO = "Versão da sessão; incrementar revoga as sessões ativas"


def _colunas(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    try:
        return {c["name"] for c in insp.get_columns(tabela)}
    except Exception:
        return set()


def upgrade() -> None:
    existentes = _colunas(TABELA)
    if not existentes:
        raise RuntimeError(
            f"Não é possível aplicar b5c6d7e8f9a0: a tabela '{TABELA}' "
            "não existe no banco alvo."
        )
    if COLUNA not in existentes:
        op.add_column(
            TABELA,
            sa.Column(
                COLUNA,
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment=COMENTARIO,
            ),
        )


def downgrade() -> None:
    if COLUNA in _colunas(TABELA):
        op.drop_column(TABELA, COLUNA)
