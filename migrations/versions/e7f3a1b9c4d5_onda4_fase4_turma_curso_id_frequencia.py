"""Onda 4 Fase 4: turma_curso_id em frequencia e registro_aula

Revision ID: e7f3a1b9c4d5
Revises: 8c4e1f9a7d32
Create Date: 2026-10-22 22:15:00.000000

Adiciona `turma_curso_id` (nullable FK) às tabelas `frequencia` e
`registro_aula`, substituindo o UNIQUE composto legado de `frequencia`
por dois índices únicos parciais:

    - uix_freq_legado: (aluno_id, turma_id, data) WHERE turma_curso_id IS NULL
    - uix_freq_oferta: (aluno_id, turma_curso_id, data) WHERE turma_curso_id IS NOT NULL

Backfill seguro: preenche turma_curso_id somente em linhas cuja turma possui
EXATAMENTE UMA oferta (contando ativas E desativadas — UNIQUE pleno). Turmas
sem oferta ou com 2+ ofertas permanecem com NULL (o leitor legado ainda usa
turma_id). Não falha nem deleta nada.

Guards de idempotência via sa.inspect(bind) seguem o padrão de 5a676f37b9a3.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'e7f3a1b9c4d5'
down_revision: str | None = '8c4e1f9a7d32'
branch_labels: str | None = None
depends_on: str | None = None


# ---------------------------------------------------------------------------
# Helpers de inspeção
# ---------------------------------------------------------------------------

def _colunas(tabela: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {c["name"] for c in insp.get_columns(tabela)}


def _indices(tabela: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {idx["name"] for idx in insp.get_indexes(tabela) if idx.get("name")}


def _constraints(tabela: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {
        uc["name"]
        for uc in insp.get_unique_constraints(tabela)
        if uc.get("name")
    }


def _fks(tabela: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {fk["name"] for fk in insp.get_foreign_keys(tabela) if fk.get("name")}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    is_pg = _is_postgres()

    # ==================================================================
    # 1. Drop do UNIQUE legado em frequencia
    #    Etapa A confirmou: em PG vive como CONSTRAINT (73f922fd358f
    #    usou create_unique_constraint). Em SQLite, batch_alter_table.
    # ==================================================================
    if is_pg:
        if 'uix_frequencia_aluno_turma_data' in _constraints('frequencia'):
            op.drop_constraint(
                'uix_frequencia_aluno_turma_data', 'frequencia', type_='unique',
            )
        else:
            if 'uix_frequencia_aluno_turma_data' in _indices('frequencia'):
                op.drop_index(
                    'uix_frequencia_aluno_turma_data', table_name='frequencia',
                )
    else:
        if 'uix_frequencia_aluno_turma_data' in _constraints('frequencia'):
            with op.batch_alter_table('frequencia', schema=None) as batch_op:
                batch_op.drop_constraint(
                    'uix_frequencia_aluno_turma_data', type_='unique',
                )

    # ==================================================================
    # 2. add_column turma_curso_id em frequencia e registro_aula
    # ==================================================================
    cols_freq = _colunas('frequencia')
    if 'turma_curso_id' not in cols_freq:
        op.add_column(
            'frequencia',
            sa.Column(
                'turma_curso_id', sa.Integer(), nullable=True,
                comment='FK → turma_curso (Onda 4 Fase 4; NULL = registro legado)',
            ),
        )

    cols_reg = _colunas('registro_aula')
    if 'turma_curso_id' not in cols_reg:
        op.add_column(
            'registro_aula',
            sa.Column(
                'turma_curso_id', sa.Integer(), nullable=True,
                comment='FK → turma_curso (Onda 4 Fase 4; NULL = registro legado)',
            ),
        )

    # FKs (somente PG; SQLite não adiciona constraint via ALTER TABLE)
    if is_pg:
        if 'fk_frequencia_turma_curso' not in _fks('frequencia'):
            op.create_foreign_key(
                'fk_frequencia_turma_curso', 'frequencia', 'turma_curso',
                ['turma_curso_id'], ['id'],
            )

        if 'fk_registro_aula_turma_curso' not in _fks('registro_aula'):
            op.create_foreign_key(
                'fk_registro_aula_turma_curso', 'registro_aula', 'turma_curso',
                ['turma_curso_id'], ['id'],
            )

    # ==================================================================
    # 3. Índices únicos parciais em frequencia
    # ==================================================================
    idx_freq = _indices('frequencia')

    if 'uix_freq_legado' not in idx_freq:
        op.create_index(
            'uix_freq_legado', 'frequencia',
            ['aluno_id', 'turma_id', 'data'],
            unique=True,
            postgresql_where=sa.text('turma_curso_id IS NULL'),
            sqlite_where=sa.text('turma_curso_id IS NULL'),
        )

    if 'uix_freq_oferta' not in idx_freq:
        op.create_index(
            'uix_freq_oferta', 'frequencia',
            ['aluno_id', 'turma_curso_id', 'data'],
            unique=True,
            postgresql_where=sa.text('turma_curso_id IS NOT NULL'),
            sqlite_where=sa.text('turma_curso_id IS NOT NULL'),
        )

    if 'ix_frequencia_turma_curso_data' not in idx_freq:
        op.create_index(
            'ix_frequencia_turma_curso_data', 'frequencia',
            ['turma_curso_id', 'data'], unique=False,
        )

    idx_reg = _indices('registro_aula')
    if 'ix_registro_aula_turma_curso_data' not in idx_reg:
        op.create_index(
            'ix_registro_aula_turma_curso_data', 'registro_aula',
            ['turma_curso_id', 'data'], unique=False,
        )

    # ==================================================================
    # 4. Backfill seguro
    #    Preenche turma_curso_id somente se a turma da linha possui
    #    EXATAMENTE 1 oferta (contando ativas E desativadas). Turmas
    #    sem oferta ou com 2+ ofertas permanecem NULL.
    # ==================================================================
    bind = op.get_bind()

    count_freq = bind.execute(sa.text("SELECT COUNT(*) FROM frequencia")).scalar() or 0
    count_reg = bind.execute(sa.text("SELECT COUNT(*) FROM registro_aula")).scalar() or 0

    if count_freq == 0 and count_reg == 0:
        return

    bind.execute(sa.text("""
        UPDATE frequencia
        SET turma_curso_id = (
            SELECT tc.id
            FROM turma_curso tc
            WHERE tc.turma_id = frequencia.turma_id
            LIMIT 1
        )
        WHERE frequencia.turma_curso_id IS NULL
          AND (
            SELECT COUNT(*)
            FROM turma_curso tc2
            WHERE tc2.turma_id = frequencia.turma_id
          ) = 1
    """))

    bind.execute(sa.text("""
        UPDATE registro_aula
        SET turma_curso_id = (
            SELECT tc.id
            FROM turma_curso tc
            WHERE tc.turma_id = registro_aula.turma_id
            LIMIT 1
        )
        WHERE registro_aula.turma_curso_id IS NULL
          AND (
            SELECT COUNT(*)
            FROM turma_curso tc2
            WHERE tc2.turma_id = registro_aula.turma_id
          ) = 1
    """))


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    is_pg = _is_postgres()
    bind = op.get_bind()

    # ==================================================================
    # 0. Guarda de duplicatas — verifica ANTES de qualquer alteração.
    #    Se existem frequências com (aluno_id, turma_id, data) repetidos
    #    (situação possível com ofertas distintas no mesmo dia), o
    #    downgrade é impossível sem perder dados.
    # ==================================================================
    dupes = bind.execute(sa.text("""
        SELECT COUNT(*) FROM (
            SELECT aluno_id, turma_id, data
            FROM frequencia
            GROUP BY aluno_id, turma_id, data
            HAVING COUNT(*) > 1
        ) d
    """)).scalar() or 0

    if dupes > 0:
        raise RuntimeError(
            f"Downgrade impossível: {dupes} grupo(s) de frequência com "
            "(aluno_id, turma_id, data) duplicados. Existem lançamentos de "
            "ofertas diferentes no mesmo dia para o mesmo aluno/turma. "
            "Resolva as duplicatas antes de reverter esta migration."
        )

    # ==================================================================
    # 1. Remove índices parciais e de apoio
    # ==================================================================
    if 'ix_registro_aula_turma_curso_data' in _indices('registro_aula'):
        op.drop_index('ix_registro_aula_turma_curso_data', table_name='registro_aula')

    for idx in ('uix_freq_oferta', 'uix_freq_legado', 'ix_frequencia_turma_curso_data'):
        if idx in _indices('frequencia'):
            op.drop_index(idx, table_name='frequencia')

    # ==================================================================
    # 2. Recria o UNIQUE legado (aluno_id, turma_id, data)
    # ==================================================================
    if is_pg:
        if 'uix_frequencia_aluno_turma_data' not in _constraints('frequencia'):
            op.create_unique_constraint(
                'uix_frequencia_aluno_turma_data', 'frequencia',
                ['aluno_id', 'turma_id', 'data'],
            )
    else:
        if 'uix_frequencia_aluno_turma_data' not in _constraints('frequencia'):
            with op.batch_alter_table('frequencia', schema=None) as batch_op:
                batch_op.create_unique_constraint(
                    'uix_frequencia_aluno_turma_data',
                    ['aluno_id', 'turma_id', 'data'],
                )

    # ==================================================================
    # 3. Remove FKs (PG)
    # ==================================================================
    if is_pg:
        if 'fk_frequencia_turma_curso' in _fks('frequencia'):
            op.drop_constraint('fk_frequencia_turma_curso', 'frequencia', type_='foreignkey')

        if 'fk_registro_aula_turma_curso' in _fks('registro_aula'):
            op.drop_constraint('fk_registro_aula_turma_curso', 'registro_aula', type_='foreignkey')

    # ==================================================================
    # 4. Remove colunas
    # ==================================================================
    if 'turma_curso_id' in _colunas('frequencia'):
        op.drop_column('frequencia', 'turma_curso_id')

    if 'turma_curso_id' in _colunas('registro_aula'):
        op.drop_column('registro_aula', 'turma_curso_id')
