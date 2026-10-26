"""H1 — Grade de horário por dia de aula na oferta (aditiva, backfill).

Revision ID: 5730d7c594ba
Revises: a8b9c0d1e2f3
Create Date: 2026-10-26 12:28:49.872901

O que esta revisão faz (etapa H1 do plano "Horário por dia na oferta"):

    1. Amplia `turma.dias_semana` e `turma_curso.dias_semana` para
       ``VARCHAR(80)`` (o CSV canônico dos sete dias não cabe em 20).
    2. Cria a tabela `turma_curso_horario` (grade por dia da oferta) com as
       constraints portáveis (UNIQUE, CHECK de domínio 0-6, CHECK de par,
       CHECK de ``fim > início``) e FK ``ON DELETE CASCADE`` para `turma_curso`.
    3. Backfill: para cada oferta (ativa ou inativa) SEM linhas na grade,
       materializa um dia por weekday resolvido com herança campo a campo
       (oferta -> turma) via COALESCE, exatamente como ``carga_horaria_aula``
       já faz hoje (decisão 6).

NÃO muda nenhum comportamento visível: as colunas escalares
(``dias_semana``/``hora_inicio``/``hora_fim`` de ``turma_curso``) NÃO são
tocadas — continuam a fonte de leitura até o H3. A grade nasce populada,
mas ninguém a lê ainda. O ponto único que passa a escrever a projeção é o
serviço do H2/H4 (`sincronizar_projecao_horario`).

Antes de QUALQUER DDL, checagens SOMENTE LEITURA reunidas num ÚNICO
``RuntimeError`` em português (padrão f6a7b8c9d0e1 / D5.5) — nada é corrigido
pela migration. Cada item lista os ids das ofertas e os valores envolvidos:

    (i)  token de dia desconhecido no CSV efetivo (da oferta, ou da turma
         quando a oferta herda);
    (ii) dia duplicado após normalização;
    (iii) par de horas incompleto APÓS o COALESCE campo a campo;
    (iv) ``hora_fim <= hora_inicio`` após o COALESCE;
    (v)  oferta com horário efetivo COMPLETO e nenhum dia efetivo (o horário
         se perderia no backfill).

    (vi) informativo (não bloqueante): ofertas ativas com dias e sem horário.

Idempotência: DDL por inspeção (só cria/altera se ausente) e backfill que só
insere em ofertas ainda sem linhas na grade — rodar duas vezes não duplica.

Downgrade: recusa com mensagem clara se alguma oferta tiver grade NÃO uniforme
(dias com pares de horário diferentes, ou dias com horário misturados a dias
sem horário); caso contrário recompõe as colunas escalares de ``turma_curso`` a
partir da grade e dropa a tabela. NÃO reduz o ``VARCHAR(80)`` de volta (evita
truncar dados já alargados) — documentado adiante.
"""
from __future__ import annotations

import logging
import unicodedata
from collections import defaultdict

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.env")

revision: str = "5730d7c594ba"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | None = None
depends_on: str | None = None


TABELA = "turma_curso_horario"

# Mapa de tokens embutido (NÃO importa código da aplicação). Espelha o
# conversor `app/utils/dias_semana.py` (H1-P1), que ainda não pode ser
# importado aqui (a aplicação não está no contexto da migration).
_CANON = (
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
)
_ABREV = ("Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom")


def _norm(token: str) -> str:
    s = (token or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().rstrip(".").strip()


_MAPA: dict[str, int] = {}
for _i, _nome in enumerate(_CANON):
    _MAPA[_norm(_nome)] = _i
    _MAPA[f"{_norm(_nome)}-feira"] = _i
    _MAPA[_norm(_ABREV[_i])] = _i


def _token_dia(token: str | None) -> int | None:
    if not token:
        return None
    s = _norm(token)
    if not s:
        return None
    if s in _MAPA:
        return _MAPA[s]
    base = s.replace("-feira", "").replace("feira", "").strip()
    return _MAPA.get(base)


# ---------------------------------------------------------------------------
# Inspeção de schema
# ---------------------------------------------------------------------------

def _tabela_existe(bind, nome: str) -> bool:
    return sa.inspect(bind).has_table(nome)


def _eh_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


# ---------------------------------------------------------------------------
# Resolução por oferta (usada por checagens e backfill — uma única fonte)
# ---------------------------------------------------------------------------

_SQL_OFERTAS = sa.text(
    "SELECT tc.id AS oferta_id, tc.ativo AS ativo, "
    "  tc.dias_semana AS oferta_dias, tc.hora_inicio AS oferta_ini, "
    "  tc.hora_fim AS oferta_fim, "
    "  t.dias_semana AS turma_dias, t.hora_inicio AS turma_ini, "
    "  t.hora_fim AS turma_fim "
    "FROM turma_curso tc JOIN turma t ON t.id = tc.turma_id "
    "ORDER BY tc.id"
)


def _resolver_oferta(linha) -> dict:
    """Resolve dias e par de horas efetivos de uma oferta (herança campo a
    campo oferta -> turma), com os tokens já classificados."""
    dias_csv = linha["oferta_dias"] or ""
    if not dias_csv.strip():
        dias_csv = linha["turma_dias"] or ""

    desconhecidos: list[str] = []
    duplicados: list[str] = []
    dias: list[int] = []
    for bruto in dias_csv.split(","):
        if not bruto.strip():
            continue
        wd = _token_dia(bruto)
        if wd is None:
            desconhecidos.append(bruto.strip())
        elif wd in dias:
            duplicados.append(_CANON[wd])
        else:
            dias.append(wd)

    # COALESCE campo a campo: início da oferta senão da turma; fim idem.
    ini = linha["oferta_ini"]
    if ini is None:
        ini = linha["turma_ini"]
    fim = linha["oferta_fim"]
    if fim is None:
        fim = linha["turma_fim"]

    return {
        "oferta_id": linha["oferta_id"],
        "ativo": bool(linha["ativo"]),
        "dias": dias,
        "desconhecidos": desconhecidos,
        "duplicados": duplicados,
        "ini": ini,
        "fim": fim,
    }


def _itens(bind) -> list[dict]:
    return [_resolver_oferta(r) for r in bind.execute(_SQL_OFERTAS).mappings()]


# ---------------------------------------------------------------------------
# Pré-checagens (somente leitura) — acumulado num único RuntimeError
# ---------------------------------------------------------------------------

def _checar_antes_de_alterar(bind) -> None:
    partes: list[str] = []
    info_vi: list[str] = []

    for it in _itens(bind):
        oid = it["oferta_id"]
        if it["desconhecidos"]:
            partes.append(
                f"(i) oferta {oid}: token(uns) de dia desconhecido(s): "
                f"{', '.join(repr(t) for t in it['desconhecidos'])}"
            )
        if it["duplicados"]:
            partes.append(
                f"(ii) oferta {oid}: dia(s) duplicado(s) após normalização: "
                f"{', '.join(it['duplicados'])}"
            )
        if (it["ini"] is None) != (it["fim"] is None):
            lado = "fim" if it["ini"] is not None else "início"
            partes.append(
                f"(iii) oferta {oid}: par de horas incompleto após COALESCE "
                f"(tem {lado}, falta o outro extremo)"
            )
        elif it["ini"] is not None and it["fim"] is not None and it["fim"] <= it["ini"]:
            partes.append(
                f"(iv) oferta {oid}: hora_fim <= hora_inicio "
                f"({it['ini']} <= {it['fim']})"
            )
        if it["ini"] is not None and it["fim"] is not None and not it["dias"]:
            partes.append(
                f"(v) oferta {oid}: tem horário efetivo completo "
                f"({it['ini']}-{it['fim']}) mas nenhum dia válido; o horário "
                "se perderia no backfill"
            )
        if it["ativo"] and it["dias"] and it["ini"] is None and it["fim"] is None:
            info_vi.append(str(oid))

    if info_vi:
        logger.warning(
            "[5730d7c594ba] (vi) informativo: ofertas ativas com dias mas sem "
            "horário (geram dias sem hora na grade): %s", ", ".join(info_vi),
        )

    if partes:
        raise RuntimeError(
            "Não é possível aplicar 5730d7c594ba (grade de horário por dia na "
            "oferta): " + " | ".join(partes) + ". Nenhum dado foi alterado por "
            "esta migration. Corrija os CSVs de `dias_semana` e os pares de "
            "hora (`turma_curso`/`turma`) e rode o upgrade novamente."
        )


# ---------------------------------------------------------------------------
# Backfill (idempotente)
# ---------------------------------------------------------------------------

def _executar_backfill(bind) -> int:
    """Insere a grade materializada para ofertas ainda sem linhas. Retorna o
    nº de linhas inseridas. Idempotente: pula ofertas que já têm grade."""
    ja_com_grade: set[int] = set()
    if _tabela_existe(bind, TABELA):
        for r in bind.execute(sa.text(
            f"SELECT DISTINCT turma_curso_id FROM {TABELA}"
        )):
            ja_com_grade.add(int(r[0]))

    ins = sa.text(
        f"INSERT INTO {TABELA} (turma_curso_id, dia_semana, hora_inicio, hora_fim) "
        "VALUES (:o, :d, :hi, :hf)"
    )
    inseridas = 0
    for it in _itens(bind):
        if it["oferta_id"] in ja_com_grade:
            continue
        for dia in sorted(it["dias"]):  # sem dias efetivos -> nenhuma linha
            bind.execute(
                ins,
                {
                    "o": it["oferta_id"],
                    "d": dia,
                    "hi": it["ini"],
                    "hf": it["fim"],
                },
            )
            inseridas += 1
    return inseridas


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    bind = op.get_bind()
    is_pg = _eh_postgres(bind)

    # 0. pré-checagens antes de qualquer DDL
    _checar_antes_de_alterar(bind)

    # 1. amplia dias_semana para VARCHAR(80) nas duas tabelas (antes de criar
    #    a tabela filha, para o batch do SQLite não ter FK apontando para cá).
    _alargar_dias_semana(bind, "turma", is_pg)
    _alargar_dias_semana(bind, "turma_curso", is_pg)

    # 2. cria a grade por dia (se ainda não existir — idempotência).
    if not _tabela_existe(bind, TABELA):
        op.create_table(
            TABELA,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "turma_curso_id", sa.Integer(),
                sa.ForeignKey(
                    "turma_curso.id",
                    name="fk_turma_curso_horario_oferta",
                    ondelete="CASCADE",
                ),
                nullable=False,
            ),
            sa.Column("dia_semana", sa.SmallInteger(), nullable=False),
            sa.Column("hora_inicio", sa.Time(), nullable=True),
            sa.Column("hora_fim", sa.Time(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "turma_curso_id", "dia_semana",
                name="uix_turma_curso_horario_dia",
            ),
            sa.CheckConstraint(
                "dia_semana >= 0 AND dia_semana <= 6", name="ck_tch_dia",
            ),
            sa.CheckConstraint(
                "(hora_inicio IS NULL AND hora_fim IS NULL) "
                "OR (hora_inicio IS NOT NULL AND hora_fim IS NOT NULL)",
                name="ck_tch_par",
            ),
            sa.CheckConstraint(
                "hora_inicio IS NULL OR hora_fim IS NULL "
                "OR hora_fim > hora_inicio",
                name="ck_tch_fim_maior",
            ),
        )
        # UNIQUE (turma_curso_id, dia_semana) já cobre o lookup da FK com
        # turma_curso_id como coluna líder -> índice adicional não é necessário.

    # 3. backfill materializado (herança campo a campo oferta -> turma).
    _executar_backfill(bind)


def _alargar_dias_semana(bind, tabela: str, is_pg: bool) -> None:
    insp = sa.inspect(bind)
    if not insp.has_table(tabela):
        return
    col = next(
        (c for c in insp.get_columns(tabela) if c["name"] == "dias_semana"),
        None,
    )
    if col is None:
        return
    # Se já é VARCHAR de capacidade >= 80, nada a fazer (idempotência).
    if getattr(col["type"], "length", None) and col["type"].length >= 80:
        return
    if is_pg:
        op.alter_column(
            tabela, "dias_semana",
            existing_type=sa.String(length=col["type"].length or 20),
            type_=sa.String(length=80),
            existing_nullable=True,
        )
    else:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.alter_column(
                "dias_semana",
                existing_type=sa.String(length=col["type"].length or 20),
                type_=sa.String(length=80),
                existing_nullable=True,
            )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def _ofertas_grade_nao_uniforme(bind) -> list[int]:
    """Ids de ofertas cuja grade não é uniforme (pares de hora distintos entre
    os dias, inclusive horário misturado com dia sem horário)."""
    if not _tabela_existe(bind, TABELA):
        return []
    linhas = defaultdict(set)
    for r in bind.execute(sa.text(
        f"SELECT turma_curso_id, hora_inicio, hora_fim FROM {TABELA}"
    )):
        linhas[int(r[0])].add((r[1], r[2]))
    return [oid for oid, pares in linhas.items() if len(pares) > 1]


def _guardar_downgrade(bind) -> None:
    ruins = _ofertas_grade_nao_uniforme(bind)
    if ruins:
        raise RuntimeError(
            "Downgrade impossível de 5730d7c594ba: a(s) oferta(s) "
            f"{', '.join(str(o) for o in ruins[:20])} tem grade NÃO uniforme "
            "(dias com horários diferentes entre si, ou dias com hora misturados "
            "a dias sem hora). As colunas escalares antigas só armazenam um "
            "único par de horários; não há para onde reapontar. Uniformize a "
            "grade (ou restaure de backup) antes de reverter esta migration."
        )


def downgrade() -> None:
    bind = op.get_bind()

    if not _tabela_existe(bind, TABELA):
        # Grade nunca criada: nada a recompor; apenas garantir o alargamento?
        # Não reduzimos o VARCHAR (documentado). Sem tabela, nada a fazer.
        return

    _guardar_downgrade(bind)

    # Recompõe as colunas escalares de turma_curso a partir da grade (que é
    # uniforme para todas as ofertas, garantido pela guarda acima).
    por_oferta: dict[int, list[tuple[int, object, object]]] = defaultdict(list)
    for r in bind.execute(sa.text(
        f"SELECT turma_curso_id, dia_semana, hora_inicio, hora_fim FROM {TABELA} "
        "ORDER BY turma_curso_id, dia_semana"
    )):
        por_oferta[int(r[0])].append((int(r[1]), r[2], r[3]))

    upd = sa.text(
        "UPDATE turma_curso SET dias_semana = :d, hora_inicio = :hi, "
        "hora_fim = :hf WHERE id = :o"
    )
    for oid, linhas in por_oferta.items():
        dias = sorted({d for d, _, _ in linhas})
        csv = ", ".join(_CANON[d] for d in dias) if dias else None
        # grade uniforme: qualquer linha traz o par único.
        _, hi, hf = linhas[0]
        bind.execute(upd, {"d": csv, "hi": hi, "hf": hf, "o": oid})

    # Dropa a grade (FK/UNIQUE/CHECKs caem junto nas duas dialectos).
    op.drop_table(TABELA)

    # NÃO reduz dias_semana de volta para VARCHAR(20): os CSVs recompostos dos
    # sete dias cabem em 80 mas não em 20; reduzir truncaria dados. Documentado
    # como limitação intencional do downgrade (H1).
