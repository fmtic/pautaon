"""Onda 4 — D5.1: esquema aditivo do conselho por oferta.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-25 12:00:00.000000

Adiciona `conselho_classe.turma_curso_id` (nullable FK) e troca a UNIQUE
legada por dois índices ÚNICOS PARCIAIS (padrão uix_freq_legado/uix_freq_oferta
da Fase 4, migration e7f3a1b9c4d5):

    - uix_conselho_legado: (turma_id, aluno_id, etapa) WHERE turma_curso_id IS NULL
    - uix_conselho_oferta: (turma_curso_id, aluno_id, etapa) WHERE turma_curso_id IS NOT NULL

A UNIQUE antiga `uix_conselho_turma_aluno_etapa` (constraint criada por
73f922fd358f; em PG vive como constraint + índice de apoio de mesmo nome) é
REMOVIDA já nesta etapa — é o que permite ao mesmo aluno ter um conselho por
oferta na mesma turma/etapa (decisão D5 do responsável, 24/10/2026).

`turma_curso` ganha `conselho_concluido` (bool NOT NULL default false) e os
pareceres coletivos `avaliacao_inicial/percurso/final` (Text nullable),
espelhando os campos legados de `Turma`, que permanece intacta.

Backfill SOMENTE inequívoco (correção do responsável sobre o desenho D5.0):
    (d) `conselho_classe.turma_curso_id` é preenchido a partir das INSCRIÇÕES
        do aluno na mesma turma: somente quando o conjunto de
        `turma_curso_id` distintos (ativas E inativas) tem exatamente 1 valor.
        Aluno em 2+ ofertas, turma sem oferta e conselho sem inscrição
        permanecem NULL (a coluna é nullable e a migration NÃO aborta).
    (e) `turma.conselho_concluido`/`avaliacao_*` são copiados para a oferta
        APENAS quando a turma tem exatamente 1 oferta ativa; nada é atribuído
        por padrão nos demais casos.

Idempotência por inspeção (padrões 5a676f37b9a3 / e7f3a1b9c4d5).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: str | None = 'd4e5f6a7b8c9'
branch_labels: str | None = None
depends_on: str | None = None


UNIQUE_LEGADA = 'uix_conselho_turma_aluno_etapa'


# ---------------------------------------------------------------------------
# Helpers de inspeção (padrão e7f3a1b9c4d5)
# ---------------------------------------------------------------------------

def _colunas(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {c["name"] for c in insp.get_columns(tabela)}


def _indices(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {idx["name"] for idx in insp.get_indexes(tabela) if idx.get("name")}


def _constraints(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {uc["name"] for uc in insp.get_unique_constraints(tabela) if uc.get("name")}


def _fks(tabela: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    return {fk["name"] for fk in insp.get_foreign_keys(tabela) if fk.get("name")}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    is_pg = _is_postgres()
    bind = op.get_bind()

    # ==================================================================
    # 1. Coluna conselho_classe.turma_curso_id (nullable) + índice de apoio
    # ==================================================================
    if 'turma_curso_id' not in _colunas('conselho_classe'):
        op.add_column(
            'conselho_classe',
            sa.Column(
                'turma_curso_id', sa.Integer(), nullable=True,
                comment='FK → turma_curso (D5.1; NULL = conselho legado pré-oferta)',
            ),
        )

    if is_pg and 'fk_conselho_classe_turma_curso' not in _fks('conselho_classe'):
        op.create_foreign_key(
            'fk_conselho_classe_turma_curso', 'conselho_classe', 'turma_curso',
            ['turma_curso_id'], ['id'],
            ondelete='RESTRICT',
        )

    if 'ix_conselho_turma_curso' not in _indices('conselho_classe'):
        op.create_index(
            'ix_conselho_turma_curso', 'conselho_classe',
            ['turma_curso_id'], unique=False,
        )

    # ==================================================================
    # 2. Colunas de conselho em turma_curso (espelho dos campos de Turma)
    # ==================================================================
    cols_tc = _colunas('turma_curso')
    if 'conselho_concluido' not in cols_tc:
        op.add_column(
            'turma_curso',
            sa.Column(
                'conselho_concluido', sa.Boolean(),
                nullable=False, server_default=sa.text('false'),
                comment='Encerramento do conselho da OFERTA (D5.1); legado vive em Turma',
            ),
        )
    for nome in ('avaliacao_inicial', 'avaliacao_percurso', 'avaliacao_final'):
        if nome not in cols_tc:
            op.add_column('turma_curso', sa.Column(nome, sa.Text(), nullable=True))

    # ==================================================================
    # 3. Remover a UNIQUE antiga (constraint e/ou índice — o ensaio do
    #    Passo 1 confirmou: em PG vive como CONSTRAINT 'u' + índice de
    #    apoio homônimo criado por 73f922fd358f via create_unique_constraint).
    # ==================================================================
    if is_pg:
        if UNIQUE_LEGADA in _constraints('conselho_classe'):
            op.drop_constraint(UNIQUE_LEGADA, 'conselho_classe', type_='unique')
        elif UNIQUE_LEGADA in _indices('conselho_classe'):
            op.drop_index(UNIQUE_LEGADA, table_name='conselho_classe')
    else:
        if UNIQUE_LEGADA in _constraints('conselho_classe'):
            with op.batch_alter_table('conselho_classe', schema=None) as batch_op:
                batch_op.drop_constraint(UNIQUE_LEGADA, type_='unique')

    # ==================================================================
    # 4. Índices únicos parciais (padrão uix_freq_legado/uix_freq_oferta)
    # ==================================================================
    idx_cc = _indices('conselho_classe')
    if 'uix_conselho_legado' not in idx_cc:
        op.create_index(
            'uix_conselho_legado', 'conselho_classe',
            ['turma_id', 'aluno_id', 'etapa'],
            unique=True,
            postgresql_where=sa.text('turma_curso_id IS NULL'),
            sqlite_where=sa.text('turma_curso_id IS NULL'),
        )
    if 'uix_conselho_oferta' not in idx_cc:
        op.create_index(
            'uix_conselho_oferta', 'conselho_classe',
            ['turma_curso_id', 'aluno_id', 'etapa'],
            unique=True,
            postgresql_where=sa.text('turma_curso_id IS NOT NULL'),
            sqlite_where=sa.text('turma_curso_id IS NOT NULL'),
        )

    # ==================================================================
    # 5. Backfill (d): a partir das INSCRIÇÕES do aluno na mesma turma.
    #    Víncula somente quando o conjunto de turma_curso_id distintos
    #    (ativas E inativas) do aluno na turma tem EXATAMENTE 1 valor.
    #    MIN() dá a oferta estável; sem valor único o HAVING zera a
    #    subconsulta e a linha permanece NULL. Não aborta em ambiguidade.
    # ==================================================================
    bind.execute(sa.text("""
        UPDATE conselho_classe
        SET turma_curso_id = (
            SELECT MIN(i.turma_curso_id)
            FROM inscricoes i
            WHERE i.aluno_id = conselho_classe.aluno_id
              AND i.turma_id = conselho_classe.turma_id
              AND i.turma_curso_id IS NOT NULL
            HAVING COUNT(DISTINCT i.turma_curso_id) = 1
        )
        WHERE conselho_classe.turma_curso_id IS NULL
    """))

    # ==================================================================
    # 6. Cópia (e): flag e pareceres de Turma → oferta, SOMENTE quando a
    #    turma tem exatamente 1 oferta ativa. Nada é atribuído por padrão
    #    nos demais casos (2+ ofertas, 0 ofertas, sem valor legado).
    # ==================================================================
    uma_oferta_ativa = (
        "(SELECT COUNT(*) FROM turma_curso x "
        " WHERE x.turma_id = turma_curso.turma_id AND x.ativo {IS_TRUE}) = 1"
    )
    if is_pg:
        oferta_where = uma_oferta_ativa.format(IS_TRUE="IS TRUE")
        bind.execute(sa.text(f"""
            UPDATE turma_curso
            SET conselho_concluido = TRUE
            WHERE ativo IS TRUE
              AND {oferta_where}
              AND (SELECT t.conselho_concluido FROM turma t
                   WHERE t.id = turma_curso.turma_id) IS TRUE
        """))
        bind.execute(sa.text(f"""
            UPDATE turma_curso
            SET avaliacao_inicial  = (SELECT t.avaliacao_inicial
                                      FROM turma t WHERE t.id = turma_curso.turma_id),
                avaliacao_percurso = (SELECT t.avaliacao_percurso
                                      FROM turma t WHERE t.id = turma_curso.turma_id),
                avaliacao_final    = (SELECT t.avaliacao_final
                                      FROM turma t WHERE t.id = turma_curso.turma_id)
            WHERE ativo IS TRUE
              AND {oferta_where}
              AND EXISTS (
                  SELECT 1 FROM turma t
                  WHERE t.id = turma_curso.turma_id
                    AND (t.avaliacao_inicial IS NOT NULL
                         OR t.avaliacao_percurso IS NOT NULL
                         OR t.avaliacao_final IS NOT NULL)
              )
        """))
    else:
        # SQLite: booleanos como 0/1; caminho mantido por compatibilidade
        # (produção é PostgreSQL; testes usam create_all, não migrations).
        oferta_where = uma_oferta_ativa.format(IS_TRUE="= 1")
        bind.execute(sa.text(f"""
            UPDATE turma_curso
            SET conselho_concluido = 1
            WHERE ativo = 1
              AND {oferta_where}
              AND (SELECT t.conselho_concluido FROM turma t
                   WHERE t.id = turma_curso.turma_id) = 1
        """))
        bind.execute(sa.text(f"""
            UPDATE turma_curso
            SET avaliacao_inicial  = (SELECT t.avaliacao_inicial
                                      FROM turma t WHERE t.id = turma_curso.turma_id),
                avaliacao_percurso = (SELECT t.avaliacao_percurso
                                      FROM turma t WHERE t.id = turma_curso.turma_id),
                avaliacao_final    = (SELECT t.avaliacao_final
                                      FROM turma t WHERE t.id = turma_curso.turma_id)
            WHERE ativo = 1
              AND {oferta_where}
              AND EXISTS (
                  SELECT 1 FROM turma t
                  WHERE t.id = turma_curso.turma_id
                    AND (t.avaliacao_inicial IS NOT NULL
                         OR t.avaliacao_percurso IS NOT NULL
                         OR t.avaliacao_final IS NOT NULL)
              )
        """))


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    is_pg = _is_postgres()
    bind = op.get_bind()

    # ==================================================================
    # 0. Guarda: a UNIQUE antiga (turma_id, aluno_id, etapa) não sobrevive
    #    se existirem conselhos do mesmo aluno/turma/etapa em ofertas
    #    diferentes (padrão downgrade de e7f3a1b9c4d5).
    # ==================================================================
    dupes = bind.execute(sa.text("""
        SELECT COUNT(*) FROM (
            SELECT turma_id, aluno_id, etapa
            FROM conselho_classe
            GROUP BY turma_id, aluno_id, etapa
            HAVING COUNT(*) > 1
        ) d
    """)).scalar() or 0
    if dupes:
        raise RuntimeError(
            f"Downgrade impossível: {dupes} grupo(s) de conselho com "
            "(turma_id, aluno_id, etapa) duplicados — existem conselhos de "
            "ofertas diferentes para o mesmo aluno/turma/etapa. Resolva as "
            "duplicatas antes de reverter esta migration."
        )

    # ==================================================================
    # 1. Remove índices únicos parciais e de apoio
    # ==================================================================
    idx_cc = _indices('conselho_classe')
    for idx in ('uix_conselho_oferta', 'uix_conselho_legado', 'ix_conselho_turma_curso'):
        if idx in idx_cc:
            op.drop_index(idx, table_name='conselho_classe')

    # ==================================================================
    # 2. Recria a UNIQUE legada (turma_id, aluno_id, etapa)
    # ==================================================================
    if is_pg:
        if UNIQUE_LEGADA not in _constraints('conselho_classe'):
            op.create_unique_constraint(
                UNIQUE_LEGADA, 'conselho_classe',
                ['turma_id', 'aluno_id', 'etapa'],
            )
    else:
        if UNIQUE_LEGADA not in _constraints('conselho_classe'):
            with op.batch_alter_table('conselho_classe', schema=None) as batch_op:
                batch_op.create_unique_constraint(
                    UNIQUE_LEGADA, ['turma_id', 'aluno_id', 'etapa'],
                )

    # ==================================================================
    # 3. Remove FK (PG) e colunas novas
    # ==================================================================
    if is_pg and 'fk_conselho_classe_turma_curso' in _fks('conselho_classe'):
        op.drop_constraint(
            'fk_conselho_classe_turma_curso', 'conselho_classe',
            type_='foreignkey',
        )

    if 'turma_curso_id' in _colunas('conselho_classe'):
        op.drop_column('conselho_classe', 'turma_curso_id')

    for nome in ('avaliacao_final', 'avaliacao_percurso', 'avaliacao_inicial',
                 'conselho_concluido'):
        if nome in _colunas('turma_curso'):
            op.drop_column('turma_curso', nome)
