"""Onda 4 — D5.5: endurecimento do conselho por oferta.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-25 18:00:00.000000

Decisões do responsável (D5.5):
    - `conselho_classe.turma_curso_id` passa a NOT NULL: o conselho legado
      sem oferta deixa de existir.
    - `uix_conselho_legado` (turma_id, aluno_id, etapa) WHERE NULL é removido;
      `uix_conselho_oferta` (turma_curso_id, aluno_id, etapa) passa a ser a
      UNIQUE plena por oferta (o índice parcial existente já garante isso).
    - `turma.conselho_concluido` é REMOVIDA: o encerramento é o da OFERTA
      (`turma_curso.conselho_concluido`), a turma é derivada em leitura.
    - `turma.avaliacao_inicial/percurso/final` NÃO são removidas nesta etapa
      (só após conferir o dump autêntico) — apenas documentadas como legado.

Antes de qualquer DDL, checagens SOMENTE LEITURA reunidas em UM único
RuntimeError em português (nada é corrigido nem atribuído por esta migration):
    (i) conselhos com turma_curso_id NULL (total, quantos concluídos/com
        situação final, primeiros 20 ids, remissão a
        `scripts/verificar_onda4_d5.py`);
    (ii) duplicatas (turma_curso_id, aluno_id, etapa);
    (iii) conselho.turma_id diferente da turma da oferta;
    (iv) turmas com `turma.conselho_concluido = true` cujas ofertas ativas não
        estão todas concluídas (flag legado sem equivalente por oferta).

Idempotência por inspeção (padrão 5a676f37b9a3 / e7f3a1b9c4d5).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: str | None = 'e5f6a7b8c9d0'
branch_labels: str | None = None
depends_on: str | None = None


UNIQUE_LEGADA_IDX = 'uix_conselho_legado'
COLUNA_TURMA = 'conselho_concluido'


# ---------------------------------------------------------------------------
# Helpers de inspeção (padrão e5f6a7b8c9d0)
# ---------------------------------------------------------------------------

def _colunas(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    try:
        return {c["name"] for c in insp.get_columns(tabela)}
    except Exception:
        return set()


def _indices(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    try:
        return {idx["name"] for idx in insp.get_indexes(tabela) if idx.get("name")}
    except Exception:
        return set()


def _nullable(tabela: str, coluna: str) -> bool | None:
    insp = sa.inspect(op.get_bind())
    for c in insp.get_columns(tabela):
        if c["name"] == coluna:
            return bool(c.get("nullable"))
    return None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


# ---------------------------------------------------------------------------
# Pré-checagens (somente leitura)
# ---------------------------------------------------------------------------

def _checar_antes_de_alterar(bind) -> None:
    """Reúne (i)-(iv) em UM RuntimeError; não altera nada."""
    partes: list[str] = []

    # (i) conselhos sem oferta
    total_null = bind.execute(sa.text(
        "SELECT count(*) FROM conselho_classe WHERE turma_curso_id IS NULL"
    )).scalar() or 0
    if total_null:
        concl_null = bind.execute(sa.text(
            "SELECT count(*) FROM conselho_classe WHERE turma_curso_id IS NULL "
            "AND (concluido IS TRUE OR situacao_final IS NOT NULL)"
        )).scalar() or 0
        ids_null = [
            str(row[0]) for row in bind.execute(sa.text(
                "SELECT id FROM conselho_classe WHERE turma_curso_id IS NULL "
                "ORDER BY id LIMIT 20"
            ))
        ]
        partes.append(
            f"(i) {total_null} conselho(s) com turma_curso_id NULL "
            f"({concl_null} concluído(s) ou com situação final); ids das "
            f"primeiras 20 linhas: {', '.join(ids_null)} — diagnóstico "
            "detalhado em scripts/verificar_onda4_d5.py"
        )

    # (ii) duplicatas por (oferta, aluno, etapa)
    dup = bind.execute(sa.text(
        "SELECT turma_curso_id, aluno_id, etapa, count(*) AS n "
        "FROM conselho_classe WHERE turma_curso_id IS NOT NULL "
        "GROUP BY turma_curso_id, aluno_id, etapa HAVING count(*) > 1 "
        "ORDER BY turma_curso_id, aluno_id, etapa"
    )).mappings().all()
    if dup:
        chaves = "; ".join(
            f"(oferta={r['turma_curso_id']}, aluno={r['aluno_id']}, "
            f"etapa={r['etapa']}) x{r['n']}"
            for r in dup[:20]
        )
        partes.append(
            f"(ii) {len(dup)} grupo(s) (turma_curso_id, aluno_id, etapa) com "
            f"conselhos duplicados; primeiros 20: {chaves}"
        )

    # (iii) turma do conselho ≠ turma da oferta
    cruz = bind.execute(sa.text(
        "SELECT cc.id, cc.aluno_id, cc.turma_id, cc.turma_curso_id, "
        "  tc.turma_id AS turma_da_oferta "
        "FROM conselho_classe cc JOIN turma_curso tc ON tc.id = cc.turma_curso_id "
        "WHERE tc.turma_id <> cc.turma_id ORDER BY cc.id"
    )).mappings().all()
    if cruz:
        chaves = "; ".join(
            f"conselho={r['id']} (turma={r['turma_id']}, oferta="
            f"{r['turma_curso_id']} da turma {r['turma_da_oferta']})"
            for r in cruz[:20]
        )
        partes.append(
            f"(iii) {len(cruz)} conselho(s) com turma_id divergente da turma "
            f"da oferta: {chaves}"
        )

    # (iv) flag legado da turma sem equivalente por oferta
    if COLUNA_TURMA in _colunas('turma'):
        div = bind.execute(sa.text(
            "SELECT t.id, t.nome, "
            "  (SELECT count(*) FROM turma_curso tc "
            "     WHERE tc.turma_id = t.id AND tc.ativo) AS ativas, "
            "  (SELECT count(*) FROM turma_curso tc "
            "     WHERE tc.turma_id = t.id AND tc.ativo AND tc.conselho_concluido) "
            "     AS concluidas "
            "FROM turma t "
            "WHERE t.conselho_concluido IS TRUE "
            "  AND EXISTS (SELECT 1 FROM turma_curso tc "
            "              WHERE tc.turma_id = t.id AND tc.ativo) "
            "  AND EXISTS (SELECT 1 FROM turma_curso tc "
            "              WHERE tc.turma_id = t.id AND tc.ativo "
            "                AND NOT tc.conselho_concluido) "
            "ORDER BY t.id"
        )).mappings().all()
        if div:
            chaves = "; ".join(
                f"turma={r['id']} ({r['nome']}: {r['concluidas']} de "
                f"{r['ativas']} ofertas ativas concluídas)"
                for r in div[:20]
            )
            partes.append(
                f"(iv) {len(div)} turma(s) com turma.conselho_concluido = true "
                f"e ofertas ativas pendentes: {chaves}"
            )

    if partes:
        raise RuntimeError(
            "Não é possível aplicar f6a7b8c9d0e1 (endurecimento do conselho "
            "por oferta): " + " | ".join(partes)
            + ". Nenhum dado foi alterado por esta migration. Resolva as "
            "pendências acima (ver scripts/verificar_onda4_d5.py e "
            "scripts/preparar_deploy_onda4.py) e rode o upgrade novamente."
        )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    is_pg = _is_postgres()
    bind = op.get_bind()

    if 'turma_curso_id' not in _colunas('conselho_classe'):
        raise RuntimeError(
            "Não é possível aplicar f6a7b8c9d0e1: a coluna "
            "conselho_classe.turma_curso_id não existe (a migration "
            "e5f6a7b8c9d0, que a cria, não foi aplicada). Rode o upgrade "
            "completo (`flask db upgrade`) antes."
        )

    _checar_antes_de_alterar(bind)

    # 1. turma_curso_id NOT NULL (o conselho legado sem oferta deixa de existir)
    if _nullable('conselho_classe', 'turma_curso_id') is True:
        with op.batch_alter_table('conselho_classe', schema=None) as batch_op:
            batch_op.alter_column(
                'turma_curso_id',
                existing_type=sa.Integer(),
                existing_nullable=True,
                nullable=False,
            )

    # 2. uix_conselho_oferta permanece (UNIQUE plena por oferta); se por algum
    #    motivo estiver ausente, é recriado.
    if 'uix_conselho_oferta' not in _indices('conselho_classe'):
        op.create_index(
            'uix_conselho_oferta', 'conselho_classe',
            ['turma_curso_id', 'aluno_id', 'etapa'],
            unique=True,
            postgresql_where=sa.text('turma_curso_id IS NOT NULL'),
            sqlite_where=sa.text('turma_curso_id IS NOT NULL'),
        )

    # 3. Remove o índice parcial do ramo legado
    if UNIQUE_LEGADA_IDX in _indices('conselho_classe'):
        op.drop_index(UNIQUE_LEGADA_IDX, table_name='conselho_classe')

    # 4. Remove turma.conselho_concluido (derivada das ofertas)
    if COLUNA_TURMA in _colunas('turma'):
        if is_pg:
            op.drop_column('turma', COLUNA_TURMA)
        else:
            with op.batch_alter_table('turma', schema=None) as batch_op:
                batch_op.drop_column(COLUNA_TURMA)


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    is_pg = _is_postgres()
    bind = op.get_bind()

    # 0. Guarda contra duplicatas no ramo legado que será reaberto: com
    #    turma_curso_id de volta a nullable, o índice parcial
    #    (turma_id, aluno_id, etapa) WHERE turma_curso_id IS NULL não pode
    #    nascer sobre grupos repetidos. Hoje não existem linhas NULL; a guarda
    #    protege o caso de dados inseridos por scripts/conferência manual.
    dup_null = bind.execute(sa.text(
        "SELECT turma_id, aluno_id, etapa, count(*) AS n "
        "FROM conselho_classe WHERE turma_curso_id IS NULL "
        "GROUP BY turma_id, aluno_id, etapa HAVING count(*) > 1"
    )).mappings().all()
    if dup_null:
        chaves = "; ".join(
            f"(turma={r['turma_id']}, aluno={r['aluno_id']}, etapa={r['etapa']}) "
            f"x{r['n']}"
            for r in dup_null[:20]
        )
        raise RuntimeError(
            "Downgrade impossível de f6a7b8c9d0e1: existem "
            f"{len(dup_null)} grupo(s) de conselho com turma_curso_id NULL e "
            f"(turma_id, aluno_id, etapa) duplicados: {chaves}. Resolva as "
            "duplicatas antes de reverter esta migration."
        )

    # 1. Recria turma.conselho_concluido (default false) e repopula com o
    #    estado DERIVADO das ofertas ativas.
    if COLUNA_TURMA not in _colunas('turma'):
        if is_pg:
            op.add_column(
                'turma',
                sa.Column(
                    COLUNA_TURMA, sa.Boolean(), nullable=False,
                    server_default=sa.text('false'),
                ),
            )
        else:
            with op.batch_alter_table('turma', schema=None) as batch_op:
                batch_op.add_column(
                    sa.Column(
                        COLUNA_TURMA, sa.Boolean(), nullable=False,
                        server_default=sa.text('false'),
                    )
                )
        bind.execute(sa.text(
            "UPDATE turma SET conselho_concluido = "
            "  (CASE WHEN EXISTS (SELECT 1 FROM turma_curso tc "
            "                      WHERE tc.turma_id = turma.id AND tc.ativo) "
            "        AND NOT EXISTS (SELECT 1 FROM turma_curso tc "
            "                        WHERE tc.turma_id = turma.id AND tc.ativo "
            "                          AND tc.conselho_concluido IS NOT TRUE) "
            "   THEN TRUE ELSE FALSE END)"
        ))

    # 2. Recria o índice parcial do ramo legado
    if UNIQUE_LEGADA_IDX not in _indices('conselho_classe'):
        op.create_index(
            UNIQUE_LEGADA_IDX, 'conselho_classe',
            ['turma_id', 'aluno_id', 'etapa'],
            unique=True,
            postgresql_where=sa.text('turma_curso_id IS NULL'),
            sqlite_where=sa.text('turma_curso_id IS NULL'),
        )

    # 3. turma_curso_id volta a aceitar NULL
    if _nullable('conselho_classe', 'turma_curso_id') is False:
        with op.batch_alter_table('conselho_classe', schema=None) as batch_op:
            batch_op.alter_column(
                'turma_curso_id',
                existing_type=sa.Integer(),
                existing_nullable=False,
                nullable=True,
            )
