"""F1 — autor do lançamento em `frequencia` e `conselho_resposta`.

Revision ID: c9d0e1f2a3b4
Revises: d6e7f8a9b0c1
Create Date: 2026-10-30

Contexto: as duas tabelas de lançamento pedagógico não tinham nenhum rastro de
autor (`registro_aula.instrutor_id` e `conselho_classe.instrutor_id` existiam só
para o diário e nunca foram preenchidos pelo conselho). A F1 acrescenta
`autor_id` + `autor_nome` nas duas tabelas:

    - `autor_id` : FK → user, ON DELETE SET NULL — a linha do lançamento
      sobrevive à exclusão do usuário.
    - `autor_nome`: snapshot do nome no momento do salvamento (mesmo padrão de
      `AuditoriaMixin.updated_by_name` e `Aluno.created_by_name`), para manter o
      rastro quando o usuário for excluído (o id vira NULL).

Decisão do responsável: o autor é SEMPRE o último usuário que salvou a linha —
não existe autor original. Histórico anterior à F1 permanece NULL (sem
backfill) e gravações sem usuário (scripts/seeds) gravam NULL.

Sem índice em `autor_id`: nenhuma consulta filtra por autor hoje (sem tela, BI,
relatório ou impressão). Índice entra junto com a primeira consulta real.

Idempotência por inspeção das colunas; upgrade só adiciona, downgrade só remove
— nenhuma linha é tocada em nenhuma das direções.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | None = None
depends_on: str | None = None

#: (tabela, nome da FK, comentário da coluna)
ALVOS: tuple[tuple[str, str, str], ...] = (
    (
        "frequencia",
        "fk_frequencia_autor",
        "Último usuário que salvou a linha (NULL = legado/script)",
    ),
    (
        "conselho_resposta",
        "fk_conselho_resposta_autor",
        "Último usuário que salvou a resposta (NULL = legado/script)",
    ),
)


def _colunas(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    try:
        return {c["name"] for c in insp.get_columns(tabela)}
    except Exception:
        return set()


def upgrade() -> None:
    for tabela, nome_fk, comentario in ALVOS:
        existentes = _colunas(tabela)
        if not existentes:
            raise RuntimeError(
                f"Não é possível aplicar c9d0e1f2a3b4: a tabela '{tabela}' "
                "não existe no banco alvo."
            )
        if "autor_id" not in existentes:
            op.add_column(
                tabela,
                sa.Column(
                    "autor_id",
                    sa.Integer(),
                    sa.ForeignKey(
                        "user.id", name=nome_fk, ondelete="SET NULL",
                    ),
                    nullable=True,
                    comment=comentario,
                ),
            )
        if "autor_nome" not in existentes:
            op.add_column(
                tabela,
                sa.Column(
                    "autor_nome",
                    sa.String(length=100),
                    nullable=True,
                    comment="Snapshot do nome do autor no momento do salvamento",
                ),
            )


def downgrade() -> None:
    for tabela, _nome_fk, _comentario in ALVOS:
        existentes = _colunas(tabela)
        if "autor_nome" in existentes:
            op.drop_column(tabela, "autor_nome")
        if "autor_id" in existentes:
            op.drop_column(tabela, "autor_id")
