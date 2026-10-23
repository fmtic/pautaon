"""Onda4 Fase1: TurmaCurso + Inscricao.turma_curso_id

Revision ID: 311d554dfd6e
Revises: b02f2051bc1e
Create Date: 2026-10-22 19:59:53.749529

ESCOPO DESTA REVISION (múltiplos cursos por turma — Fase 1)
    1. Criar a tabela `turma_curso` (oferta concreta de um curso em uma turma)
       com UNIQUE(turma_id, curso_id) e índice único parcial do `principal`.
    2. Adicionar `inscricoes.turma_curso_id` (FK, nullable durante a transição)
       com índice de apoio.
    3. Backfill: criar uma oferta por turma legada que tenha `curso_id`,
       copiando os atributos de horário/professor/turno/datas/centro de custo
       da própria turma. Nenhum curso fictício é criado para turmas sem curso.
    4. Backfill: vincular cada `inscricao` à oferta da sua turma.

NOTA SOBRE AUTOGENERATE
    O autogenerate também propôs ALTERs de comment/nullable em ~10 tabelas e o
    DROP das colunas de auditoria de `curso`. Tudo isso é DRIFT PRÉ-EXISTENTE
    (colunas que existem no banco mas não no modelo, e vice-versa) e está
    FORA DO ESCOPO desta onda. Foi removido manualmente para não destruir
    dados nem tocar em tabelas não relacionadas. Fica registrado no backlog
    para uma revision de sincronia dedicada.

NOTA SOBRE A SEQUÊNCIA (PostgreSQL)
    A PK `id` é criada como inteiro simples com PrimaryKeyConstraint. No
    dialeto PostgreSQL o SQLAlchemy/psycopg2 renderiza a coluna SERIAL na
    criação da tabela, gerando `turma_curso_id_seq` automaticamente. Por
    segurança (lição da `inscricoes.id` sem sequência), a criação do default
    é reafirmada de forma idempotente em `upgrade()`, apenas no PostgreSQL.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# Identificadores desta revisão
revision: str = '311d554dfd6e'
down_revision: str | None = 'b02f2051bc1e'
branch_labels: str | None = None
depends_on: str | None = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Tabela turma_curso (oferta curso↔turma)
    # ------------------------------------------------------------------
    op.create_table(
        'turma_curso',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('turma_id', sa.Integer(), nullable=False),
        sa.Column('curso_id', sa.Integer(), nullable=False),
        sa.Column(
            'principal', sa.Boolean(), nullable=False,
            comment='Curso principal da turma (vínculo, não atributo do aluno/curso)',
        ),
        sa.Column(
            'professor_id', sa.Integer(), nullable=True,
            comment='Professor responsável pela oferta do curso na turma',
        ),
        sa.Column('turno', sa.String(length=20), nullable=True),
        sa.Column('dias_semana', sa.String(length=20), nullable=True),
        sa.Column('hora_inicio', sa.Time(), nullable=True),
        sa.Column('hora_fim', sa.Time(), nullable=True),
        sa.Column('data_inicio', sa.Date(), nullable=True),
        sa.Column('data_fim', sa.Date(), nullable=True),
        sa.Column(
            'centro_custo', sa.String(length=150), nullable=True,
            comment='Centro de custo individual; NULL = usa o compartilhado da turma',
        ),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column(
            'ativo', sa.Boolean(), nullable=False,
            comment='Flag de registro ativo (soft delete)',
        ),
        sa.Column(
            'unidade_id', sa.Integer(), nullable=True,
            comment='ID da unidade (tenant)',
        ),
        sa.ForeignKeyConstraint(['curso_id'], ['curso.id'], ),
        sa.ForeignKeyConstraint(['professor_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['turma_id'], ['turma.id'], ),
        sa.ForeignKeyConstraint(['unidade_id'], ['unidade.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('turma_id', 'curso_id', name='uix_turma_curso_oferta'),
    )

    with op.batch_alter_table('turma_curso', schema=None) as batch_op:
        batch_op.create_index(
            'ix_turma_curso_curso_id', ['curso_id'], unique=False,
        )
        batch_op.create_index(
            'ix_turma_curso_professor_id', ['professor_id'], unique=False,
        )
        # No máximo um principal por turma ativa (índice único parcial).
        batch_op.create_index(
            'uix_turma_curso_principal', ['turma_id'], unique=True,
            postgresql_where=sa.text('principal AND ativo'),
            sqlite_where=sa.text('principal = 1 AND ativo = 1'),
        )

    # Reafirma o default da sequência da PK (somente PostgreSQL, idempotente).
    if _is_postgres():
        op.execute("CREATE SEQUENCE IF NOT EXISTS turma_curso_id_seq")
        op.execute("ALTER SEQUENCE turma_curso_id_seq OWNED BY turma_curso.id")
        op.execute(
            "ALTER TABLE turma_curso ALTER COLUMN id "
            "SET DEFAULT nextval('turma_curso_id_seq')"
        )

    # ------------------------------------------------------------------
    # 2. inscricoes.turma_curso_id (FK nullable na transição) + índice
    # ------------------------------------------------------------------
    with op.batch_alter_table('inscricoes', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('turma_curso_id', sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            'fk_inscricoes_turma_curso', 'turma_curso',
            ['turma_curso_id'], ['id'],
        )
        batch_op.create_index(
            'ix_inscricoes_turma_curso_id', ['turma_curso_id'], unique=False,
        )

    # ------------------------------------------------------------------
    # 3. Backfill de ofertas: uma por turma legada com curso_id.
    #    Copia os atributos de oferta da própria turma; principal=FALSE
    #    (turma com oferta única não exige marcação de principal).
    #    Idempotente: só insere se ainda não existe oferta para o par.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO turma_curso (
            turma_id, curso_id, principal, professor_id, turno, dias_semana,
            hora_inicio, hora_fim, data_inicio, data_fim, centro_custo,
            ativo, unidade_id, created_at
        )
        SELECT
            t.id, t.curso_id, FALSE, t.professor_id, t.turno, t.dias_semana,
            t.hora_inicio, t.hora_fim, t.data_inicio, t.data_fim, t.centro_custo,
            COALESCE(t.ativo, TRUE), t.unidade_id, CURRENT_TIMESTAMP
        FROM turma t
        WHERE t.curso_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM turma_curso tc
              WHERE tc.turma_id = t.id AND tc.curso_id = t.curso_id
          )
        """
    )

    # ------------------------------------------------------------------
    # 4. Backfill do vínculo de matrícula: cada inscrição aponta para a
    #    oferta da sua turma. Subconsulta correlacionada (portável PG+SQLite).
    #    UNIQUE(turma_id, curso_id) garante no máximo uma oferta por turma
    #    legada, logo o LIMIT 1 é determinístico.
    # ------------------------------------------------------------------
    op.execute(
        """
        UPDATE inscricoes
        SET turma_curso_id = (
            SELECT tc.id FROM turma_curso tc
            WHERE tc.turma_id = inscricoes.turma_id
            LIMIT 1
        )
        WHERE inscricoes.turma_curso_id IS NULL
          AND EXISTS (
              SELECT 1 FROM turma_curso tc
              WHERE tc.turma_id = inscricoes.turma_id
          )
        """
    )


def downgrade() -> None:
    # Remove o vínculo, depois a coluna/índice, depois a tabela.
    op.execute("UPDATE inscricoes SET turma_curso_id = NULL WHERE turma_curso_id IS NOT NULL")

    with op.batch_alter_table('inscricoes', schema=None) as batch_op:
        batch_op.drop_index('ix_inscricoes_turma_curso_id')
        batch_op.drop_constraint('fk_inscricoes_turma_curso', type_='foreignkey')
        batch_op.drop_column('turma_curso_id')

    with op.batch_alter_table('turma_curso', schema=None) as batch_op:
        batch_op.drop_index('uix_turma_curso_principal')
        batch_op.drop_index('ix_turma_curso_professor_id')
        batch_op.drop_index('ix_turma_curso_curso_id')

    op.drop_table('turma_curso')

    if _is_postgres():
        op.execute("DROP SEQUENCE IF EXISTS turma_curso_id_seq")
