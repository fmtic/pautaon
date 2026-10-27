"""H5b-B — remove as 6 colunas escalares de agenda (Turma e TurmaCurso).

Revision ID: 8d2e3f4a5b6c
Revises: 7c1d2e3f4a5b
Create Date: 2026-10-26

Contexto (H5b): desde o H5a nenhum código de `app/`/`scripts/` lê ou escreve
`turma.dias_semana/hora_inicio/hora_fim` nem
`turma_curso.dias_semana/hora_inicio/hora_fim`; a grade
`turma_curso_horario` é a única fonte. Esta revisão remove fisicamente as seis
colunas (schema) e o modelo perde as declarações no mesmo commit.

Upgrade:
    1. checagem SOMENTE LEITURA: toda oferta (qualquer status) precisa ter ao
       menos uma linha de grade; caso contrário RuntimeError listando os ids
       (nada é alterado);
    2. DROP COLUMN das 3 colunas de `turma_curso` e das 3 de `turma`
       (idempotente: só dropa se a coluna existir).

Downgrade REVERSÍVEL (com perda documentada):
    - recria as colunas nullable: `dias_semana VARCHAR(80)`, `hora_inicio TIME`,
      `hora_fim TIME` nas duas tabelas;
    - repopula a projeção a partir da grade:
        * oferta com grade UNIFORME (mesmo par em todos os dias, com hora) →
          CSV canônico dos dias + o par;
        * oferta com grade NÃO uniforme (ou dias sem hora) → CSV dos dias +
          `hora_inicio`/`hora_fim` NULL (não existe par único);
        * oferta sem grade → tudo NULL;
        * turma com EXATAMENTE UMA oferta ativa → espelha a projeção dessa
          oferta (mesma regra do antigo `_sincronizar_legado`);
        * turma com 0 ou 2+ ofertas ativas → tudo NULL.
    - PERDA DE INFORMAÇÃO: a grade continua intacta, mas as colunas escalares
      não representam horários diferentes por dia — no downgrade esses horários
      viram NULL. Reaplicar o upgrade (drop) não perde a grade.

O teste da migration H1 (`5730d7c594ba`) recria as colunas legadas por DDL
manual no SQLite; esta migration não importa código da aplicação.
"""
from __future__ import annotations

from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision: str = "8d2e3f4a5b6c"
down_revision: str | None = "7c1d2e3f4a5b"
branch_labels: str | None = None
depends_on: str | None = None

TABELAS = ("turma", "turma_curso")
COLUNAS = ("dias_semana", "hora_inicio", "hora_fim")
TABELA_GRADE = "turma_curso_horario"
_CANON = (
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
)


def _eh_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _colunas(bind, tabela: str) -> set[str]:
    insp = sa.inspect(bind)
    if not insp.has_table(tabela):
        return set()
    return {c["name"] for c in insp.get_columns(tabela)}


def _ofertas_sem_grade(bind) -> list[tuple[int, int, bool | None]]:
    if not sa.inspect(bind).has_table(TABELA_GRADE):
        return []
    return [
        (int(r[0]), int(r[1]), r[2])
        for r in bind.execute(
            sa.text(
                "SELECT tc.id, tc.turma_id, tc.ativo FROM turma_curso tc "
                "WHERE NOT EXISTS (SELECT 1 FROM turma_curso_horario h "
                "                  WHERE h.turma_curso_id = tc.id) "
                "ORDER BY tc.id"
            )
        )
    ]


def _checar_ofertas_sem_grade(bind) -> None:
    ruins = _ofertas_sem_grade(bind)
    if ruins:
        detalhes = ", ".join(
            f"id={oferta_id} (turma {turma_id}, ativo={ativo})"
            for oferta_id, turma_id, ativo in ruins[:20]
        )
        raise RuntimeError(
            "Upgrade de 8d2e3f4a5b6c (H5b-B) recusado: há oferta(s) sem nenhuma "
            f"linha em turma_curso_horario: {detalhes}. A grade é a única fonte "
            "de agenda; preencha a grade (ou restaure de backup) antes de dropar "
            "as colunas. Nada foi alterado."
        )


def _dropar_colunas(bind) -> None:
    for tabela in TABELAS:
        existentes = _colunas(bind, tabela)
        for coluna in COLUNAS:
            if coluna not in existentes:
                continue
            if _eh_postgres(bind):
                bind.execute(
                    sa.text(f"ALTER TABLE {tabela} DROP COLUMN IF EXISTS {coluna}")
                )
            else:
                bind.execute(sa.text(f"ALTER TABLE {tabela} DROP COLUMN {coluna}"))


def _adicionar_colunas(bind) -> None:
    for tabela in TABELAS:
        existentes = _colunas(bind, tabela)
        for coluna, tipo in (
            ("dias_semana", "VARCHAR(80)"),
            ("hora_inicio", "TIME"),
            ("hora_fim", "TIME"),
        ):
            if coluna in existentes:
                continue
            if _eh_postgres(bind):
                bind.execute(
                    sa.text(
                        f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS "
                        f"{coluna} {tipo}"
                    )
                )
            else:
                bind.execute(
                    sa.text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
                )


def _projecao_ofertas(bind) -> dict[int, tuple[str | None, object, object]]:
    """(CSV dos dias, início, fim) por oferta, a partir da grade."""
    if not sa.inspect(bind).has_table(TABELA_GRADE):
        return {}
    por_oferta: dict[int, list[tuple[int, object, object]]] = defaultdict(list)
    for r in bind.execute(
        sa.text(
            f"SELECT turma_curso_id, dia_semana, hora_inicio, hora_fim "
            f"FROM {TABELA_GRADE} ORDER BY turma_curso_id, dia_semana"
        )
    ):
        por_oferta[int(r[0])].append((int(r[1]), r[2], r[3]))

    projecao: dict[int, tuple[str | None, object, object]] = {}
    for oferta_id, linhas in por_oferta.items():
        dias = sorted({dia for dia, _, _ in linhas})
        csv = ", ".join(_CANON[dia] for dia in dias) if dias else None
        pares = {(ini, fim) for _, ini, fim in linhas}
        if len(pares) == 1:
            ini, fim = next(iter(pares))
            if ini is None or fim is None:
                ini = fim = None
        else:
            ini = fim = None
        projecao[oferta_id] = (csv, ini, fim)
    return projecao


def _repopular_projecao(bind) -> None:
    """Recompõe as 6 colunas a partir da grade (ver docstring do módulo)."""
    projecao = _projecao_ofertas(bind)
    atualiza_oferta = sa.text(
        "UPDATE turma_curso SET dias_semana = :d, hora_inicio = :hi, "
        "hora_fim = :hf WHERE id = :o"
    )
    for oferta_id, (csv, ini, fim) in projecao.items():
        bind.execute(
            atualiza_oferta, {"d": csv, "hi": ini, "hf": fim, "o": oferta_id}
        )

    # Ofertas sem grade (estado inválido) e ofertas fora da projeção: NULL.
    ofertas_sem = {oferta_id for oferta_id, _, _ in _ofertas_sem_grade(bind)}
    for oferta_id in ofertas_sem:
        bind.execute(
            atualiza_oferta, {"d": None, "hi": None, "hf": None, "o": oferta_id}
        )

    ativas_por_turma: dict[int, list[int]] = defaultdict(list)
    for r in bind.execute(
        sa.text("SELECT id, turma_id FROM turma_curso WHERE ativo ORDER BY id")
    ):
        ativas_por_turma[int(r[1])].append(int(r[0]))

    atualiza_turma = sa.text(
        "UPDATE turma SET dias_semana = :d, hora_inicio = :hi, "
        "hora_fim = :hf WHERE id = :t"
    )
    for r in bind.execute(sa.text("SELECT id FROM turma ORDER BY id")):
        turma_id = int(r[0])
        ativas = ativas_por_turma.get(turma_id, [])
        if len(ativas) == 1 and ativas[0] in projecao:
            csv, ini, fim = projecao[ativas[0]]
        else:
            csv = ini = fim = None
        bind.execute(
            atualiza_turma, {"d": csv, "hi": ini, "hf": fim, "t": turma_id}
        )


def upgrade() -> None:
    bind = op.get_bind()
    _checar_ofertas_sem_grade(bind)
    _dropar_colunas(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _adicionar_colunas(bind)
    _repopular_projecao(bind)
