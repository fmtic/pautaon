"""H5b-A — aperta o CHECK `ck_tch_dia` de 0–6 para 0–5.

Revision ID: 7c1d2e3f4a5b
Revises: 5730d7c594ba
Create Date: 2026-10-26

Contexto (H5b): o serviço `definir_grade` sempre recusou domingo (0–5), mas o
CHECK do banco ainda admitia 0–6 por tolerância ao legado do H1. Com as colunas
escalares sem uso desde o H5a, o domingo deixa de ser um estado tolerável e o
schema passa a refletir a regra do serviço.

Upgrade:
    1. checagem SOMENTE LEITURA: qualquer linha de `turma_curso_horario` com
       `dia_semana = 6` aborta com RuntimeError listando os ids (nada é
       corrigido pela migration);
    2. DROP CONSTRAINT `ck_tch_dia` e recriação com `dia_semana BETWEEN 0 AND 5`.

Downgrade: volta a aceitar 0–6 (o CHECK anterior). Nenhum dado é alterado.

Portabilidade: PostgreSQL usa DROP/ADD CONSTRAINT; SQLite usa batch (recriação
da tabela). O modelo `TurmaCursoHorario` declara o mesmo CHECK 0–5.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "7c1d2e3f4a5b"
down_revision: str | None = "5730d7c594ba"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "turma_curso_horario"
NOME_CHECK = "ck_tch_dia"
CHECK_NOVO = "dia_semana >= 0 AND dia_semana <= 5"
CHECK_ANTIGO = "dia_semana >= 0 AND dia_semana <= 6"


def _eh_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _linhas_dia_6(bind) -> list[tuple[int, int, int]]:
    """Ids das linhas com dia 6 (domingo), para a mensagem de recusa."""
    if not sa.inspect(bind).has_table(TABELA):
        return []
    return [
        (int(r[0]), int(r[1]), int(r[2]))
        for r in bind.execute(
            sa.text(
                f"SELECT id, turma_curso_id, dia_semana FROM {TABELA} "
                "WHERE dia_semana = 6 ORDER BY id"
            )
        )
    ]


def _checar_dia_6(bind) -> None:
    ruins = _linhas_dia_6(bind)
    if ruins:
        detalhes = ", ".join(
            f"id={linha_id} (oferta {oferta_id})" for linha_id, oferta_id, _ in ruins[:20]
        )
        raise RuntimeError(
            "Upgrade de 7c1d2e3f4a5b (H5b-A) recusado: a grade tem linha(s) com "
            f"dia_semana = 6 (domingo): {detalhes}. O domínio passou a ser 0–5; "
            "corrija/remova essas linhas (ou restaure de backup) antes de aplicar. "
            "Nada foi alterado."
        )


def _aplicar_check(bind, *, novo: bool) -> None:
    """Troca `ck_tch_dia` para 0–5 (novo=True) ou 0–6 (novo=False)."""
    if not sa.inspect(bind).has_table(TABELA):
        return
    if _eh_postgres(bind):
        op.drop_constraint(NOME_CHECK, TABELA, type_="check")
        op.create_check_constraint(
            NOME_CHECK, TABELA, CHECK_NOVO if novo else CHECK_ANTIGO
        )
        return

    # SQLite: recria a tabela pelo batch. `drop_constraint` por nome pode não
    # refletir no SQLite; o batch reflete a tabela e recria com o CHECK novo.
    with op.batch_alter_table(TABELA, recreate="always") as batch_op:
        try:
            batch_op.drop_constraint(NOME_CHECK, type_="check")
        except Exception:
            # O CHECK antigo pode não estar nomeado na reflexão do SQLite; a
            # recriação abaixo já aplica o CHECK novo no metadata.
            pass
        batch_op.create_check_constraint(
            NOME_CHECK, CHECK_NOVO if novo else CHECK_ANTIGO
        )


def upgrade() -> None:
    bind = op.get_bind()
    _checar_dia_6(bind)
    _aplicar_check(bind, novo=True)


def downgrade() -> None:
    bind = op.get_bind()
    _aplicar_check(bind, novo=False)
