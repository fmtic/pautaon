"""G1/P2 (E2) — `turma_curso.professor_id` passa a NOT NULL.

Revision ID: d6e7f8a9b0c1
Revises: e1f2a3b4c5d6
Create Date: 2026-10-29

Contexto: a obrigatoriedade de **escrita** vale desde a E2 da rodada
G1/P2+I1 (serviço `_validar_professor` + formulários `required`, MER §8.21).
Esta migration fecha o G1/P2 com a obrigatoriedade de **schema**. O saneamento
removeu as ofertas de teste sem professor: 19 (1ª rodada, commit `ee922c5`) e
16/17/18 com seus lançamentos (2ª rodada, `--remover-lancamentos`) — conferido
por SELECT nos dois bancos antes de criar esta revision (zero NULLs, ativos ou
inativos).

Pré-checagem (somente leitura, padrão `f6a7b8c9d0e1`): qualquer linha com
`turma_curso.professor_id IS NULL` derruba a upgrade com UM RuntimeError em
português listando os ids — nada é corrigido ou atribuído por esta migration.

Upgrade: `ALTER COLUMN professor_id SET NOT NULL` (batch no SQLite; direto no
PostgreSQL). Idempotência por inspeção do `nullable`.
Downgrade: volta a nullable; nenhuma linha é tocada.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "turma_curso"
COLUNA = "professor_id"


def _colunas() -> set[str]:
    insp = sa.inspect(op.get_bind())
    try:
        return {c["name"] for c in insp.get_columns(TABELA)}
    except Exception:
        return set()


def _nullable() -> bool | None:
    insp = sa.inspect(op.get_bind())
    for c in insp.get_columns(TABELA):
        if c["name"] == COLUNA:
            return bool(c.get("nullable"))
    return None


def upgrade() -> None:
    bind = op.get_bind()
    if COLUNA not in _colunas():
        raise RuntimeError(
            f"Não é possível aplicar d6e7f8a9b0c1: a coluna "
            f"{TABELA}.{COLUNA} não existe no banco alvo."
        )

    # Pré-checagem: nenhuma oferta (ativa ou inativa) pode ficar sem professor.
    nulls = [
        str(row[0])
        for row in bind.execute(sa.text(
            f"SELECT id FROM {TABELA} WHERE {COLUNA} IS NULL ORDER BY id LIMIT 20"
        ))
    ]
    if nulls:
        total = bind.execute(sa.text(
            f"SELECT count(*) FROM {TABELA} WHERE {COLUNA} IS NULL"
        )).scalar()
        raise RuntimeError(
            f"Migration d6e7f8a9b0c1 recusada: {total} oferta(s) em "
            f"{TABELA} seguem sem professor (ids até 20: {', '.join(nulls)}). "
            "Reatribua o professor responsável (rotas de edição da oferta, "
            "com confirmação e log desde a E2) ou remova a oferta de teste "
            "(scripts/remover_ofertas_sem_lancamento.py) antes de aplicar."
        )

    # Idempotente: só altera se ainda for nullable.
    if _nullable() is True:
        with op.batch_alter_table(TABELA, schema=None) as batch_op:
            batch_op.alter_column(
                COLUNA,
                existing_type=sa.Integer(),
                existing_nullable=True,
                nullable=False,
            )


def downgrade() -> None:
    # Volta a nullable; nenhuma linha é tocada (não há dados para reconstruir).
    if _nullable() is False:
        with op.batch_alter_table(TABELA, schema=None) as batch_op:
            batch_op.alter_column(
                COLUNA,
                existing_type=sa.Integer(),
                existing_nullable=False,
                nullable=True,
            )
