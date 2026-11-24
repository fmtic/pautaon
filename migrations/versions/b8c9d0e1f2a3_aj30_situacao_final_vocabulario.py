"""AJ30 — vocabulário único de situação final do conselho.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-23

Fecha o conselho com um único vocabulário gravado em
``conselho_classe.situacao_final``:

    Aprovado, Participante, Reprovado por faltas, Desistente, Evadido, Empregado

"Não definido" NÃO é valor: é ``NULL`` (a CHECK continua permitindo NULL).
A migração renomeia, em uma única transição atômica:

    Concluído            -> Aprovado
    Participação         -> Participante
    Reprovado por Falta  -> Reprovado por faltas

"Concluído vale como Aprovado" — por isso a fusão é sem perda de regra de
negócio (certificado/ficha), embora o rótulo histórico desapareça.

Segurança
---------
1. PRÉ-CHECAGEM SOMENTE LEITURA: qualquer valor fora do mapa conhecido
   (antigo ou novo) aborta com mensagem clara, antes de qualquer escrita.
2. CHECK transitório aceita o conjunto antigo E o novo (necessário porque o
   PostgreSQL valida cada UPDATE e o SQLite reconstrói a tabela no batch).
3. UPDATEs de rename.
4. CHECK final com os 6 valores canônicos + NULL.

Downgrade
---------
Reverte os três renomes e recria a CHECK antiga. Guardas:
- recusa se houver ``Empregado`` (valor que não existia no vocabulário
  antigo), listando os ids;
- recusa qualquer outro valor fora do mapa conhecido.
A conversão ``Concluído -> Aprovado`` é IRREVERSÍVEL: o downgrade volta para
``Aprovado`` e não consegue distinguir os alunos que antes estavam como
"Concluído". Isso é documentado no relatório da AJ30.

Portabilidade/idempotência: inspeção do bind antes de cada DDL; rodar duas
vezes não falha nem duplica. No SQLite a troca da CHECK usa
``batch_alter_table(recreate='always')`` (o dialeto não tem DROP CONSTRAINT).
Os literals abaixo são um snapshot congelado da fonte única em
``app/models/enums.py`` — migrations não importam código da aplicação.
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "conselho_classe"
CHECK = "ck_conselho_situacao_final"

RENOMEAR_UP = {
    "Concluído": "Aprovado",
    "Participação": "Participante",
    "Reprovado por Falta": "Reprovado por faltas",
}
RENOMEAR_DOWN = {novo: antigo for antigo, novo in RENOMEAR_UP.items()}

VALORES_FINAIS_UP = (
    "Aprovado", "Participante", "Reprovado por faltas",
    "Desistente", "Evadido", "Empregado",
)
VALORES_FINAIS_DOWN = (
    "Aprovado", "Reprovado por Falta", "Desistente",
    "Evadido", "Participação", "Concluído",
)
VALORES_ANTIGOS = tuple(RENOMEAR_UP)
PERMITIDOS_UP = set(VALORES_FINAIS_UP) | set(VALORES_ANTIGOS)
PERMITIDOS_DOWN = set(VALORES_FINAIS_DOWN) | set(RENOMEAR_DOWN)

# Palavras que o reflection do PostgreSQL devolve entre aspas (`'text'::text`).
_RUIDO_REFLECTION = {"text", "character varying", "varchar", "bpchar"}


def _expressao(valores) -> str:
    return (
        "situacao_final IS NULL OR situacao_final IN ("
        + ", ".join("'" + valor + "'" for valor in valores)
        + ")"
    )


def _valores_da_check(bind) -> set[str] | None:
    """Valores hoje presentes na CHECK, ou None se ela não existe."""
    for restricao in sa.inspect(bind).get_check_constraints(TABELA):
        if restricao["name"] == CHECK:
            return {
                valor
                for valor in re.findall(r"'([^']*)'", restricao["sqltext"] or "")
                if valor not in _RUIDO_REFLECTION
            }
    return None


def _garantir_check(bind, valores) -> None:
    """Deixa a CHECK exatamente com ``valores`` (+ NULL), seja qual for o
    estado atual (ausente, antiga, transitória ou final)."""
    desejados = set(valores)
    if _valores_da_check(bind) == desejados:
        return
    expressao = _expressao(valores)
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(TABELA, recreate="always") as lote:
            if _valores_da_check(bind) is not None:
                lote.drop_constraint(CHECK, type_="check")
            lote.create_check_constraint(CHECK, expressao)
    else:
        if _valores_da_check(bind) is not None:
            op.drop_constraint(CHECK, TABELA, type_="check")
        op.create_check_constraint(CHECK, TABELA, expressao)


def _fora_do_mapa(bind, permitidos):
    """Varredura em lote, SOMENTE LEITURA."""
    lista = ", ".join("'" + valor + "'" for valor in sorted(permitidos))
    return bind.execute(sa.text(
        f"SELECT situacao_final, COUNT(*) AS qtd, MIN(id) AS primeiro_id "
        f"FROM {TABELA} "
        f"WHERE situacao_final IS NOT NULL AND situacao_final NOT IN ({lista}) "
        f"GROUP BY situacao_final ORDER BY situacao_final"
    )).all()


def _abortar_se_fora_do_mapa(bind, permitidos, direcao: str) -> None:
    improprios = _fora_do_mapa(bind, permitidos)
    if not improprios:
        return
    detalhes = "; ".join(
        f"{linha.situacao_final!r}: {linha.qtd} linha(s), primeiro id={linha.primeiro_id}"
        for linha in improprios
    )
    raise RuntimeError(
        f"Migration AJ30 ({direcao}) ABORTADA antes de qualquer escrita: "
        f"existe(m) situação(ões) final(is) fora do mapa conhecido em "
        f"{TABELA}. {detalhes}. Regularize esses valores antes de executar a "
        f"migration."
    )


def _renomear(bind, mapa) -> None:
    for antigo, novo in mapa.items():
        bind.execute(
            sa.text(
                f"UPDATE {TABELA} SET situacao_final = :novo "
                f"WHERE situacao_final = :antigo"
            ),
            {"novo": novo, "antigo": antigo},
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABELA):
        return

    _abortar_se_fora_do_mapa(bind, PERMITIDOS_UP, "upgrade")

    # CHECK transitória: aceita antigos e novos para que os UPDATEs sejam
    # válidos no PostgreSQL e a reconstrução do SQLite não rejeite linhas.
    if _valores_da_check(bind) != set(VALORES_FINAIS_UP):
        transitorios = tuple(sorted(set(VALORES_FINAIS_UP) | set(VALORES_ANTIGOS)))
        _garantir_check(bind, transitorios)
        _renomear(bind, RENOMEAR_UP)
    _garantir_check(bind, VALORES_FINAIS_UP)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABELA):
        return

    # Guarda específica: "Empregado" não existia no vocabulário antigo.
    # IDs dos ALUNOS (não a PK da tabela) — é o que o gestor consegue localizar
    # no sistema para reenquadrar antes de reverter.
    empregados = bind.execute(sa.text(
        f"SELECT aluno_id FROM {TABELA} WHERE situacao_final = 'Empregado' "
        f"ORDER BY aluno_id"
    )).scalars().all()
    if empregados:
        amostra = ", ".join(str(i) for i in empregados[:20])
        sufixo = " ..." if len(empregados) > 20 else ""
        raise RuntimeError(
            f"Downgrade AJ30 recusado: há {len(empregados)} aluno(s) com "
            f"situacao_final='Empregado' (ids: {amostra}{sufixo}), valor que "
            f"não existe no vocabulário anterior. Reenquadre esses registros "
            f"antes de reverter."
        )

    _abortar_se_fora_do_mapa(bind, PERMITIDOS_DOWN, "downgrade")

    if _valores_da_check(bind) != set(VALORES_FINAIS_DOWN):
        transitorios = tuple(sorted(set(VALORES_FINAIS_DOWN) | set(RENOMEAR_DOWN)))
        _garantir_check(bind, transitorios)
        _renomear(bind, RENOMEAR_DOWN)
    _garantir_check(bind, VALORES_FINAIS_DOWN)
