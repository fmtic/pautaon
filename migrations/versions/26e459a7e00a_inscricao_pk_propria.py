"""inscricao_pk_propria

Troca a PK composta (aluno_id, turma_id) da tabela inscricoes por uma PK
autoincrementada (id), permitindo múltiplos registros do mesmo par com
status ativo/inativo (re-enturmação após desenturmamento).

Revision ID: 26e459a7e00a
Revises: 99f0996802e6
Create Date: 2026-09-14 15:38:10.648269
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '26e459a7e00a'
down_revision: str | None = '99f0996802e6'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Remove a restrição de PK composta antiga
    op.drop_constraint('inscricoes_pkey', 'inscricoes', type_='primary')

    # 2. Adiciona a coluna id como SERIAL (sem NOT NULL ainda, para não quebrar rows existentes)
    op.add_column('inscricoes', sa.Column('id', sa.Integer(), nullable=True))

    # 3. Preenche id nos registros existentes usando uma sequência
    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS inscricoes_id_seq;
        UPDATE inscricoes SET id = nextval('inscricoes_id_seq');
        ALTER SEQUENCE inscricoes_id_seq OWNED BY inscricoes.id;
        ALTER TABLE inscricoes ALTER COLUMN id SET DEFAULT nextval('inscricoes_id_seq');
        ALTER TABLE inscricoes ALTER COLUMN id SET NOT NULL;
    """)

    # 4. Define id como nova PK
    op.create_primary_key('inscricoes_pkey', 'inscricoes', ['id'])

    # 5. Garante que aluno_id e turma_id continuam NOT NULL (FKs)
    op.alter_column('inscricoes', 'aluno_id', nullable=False)
    op.alter_column('inscricoes', 'turma_id', nullable=False)


def downgrade() -> None:
    # Reverte: remove id e restaura PK composta
    # ATENÇÃO: só funciona se não houver registros duplicados de (aluno_id, turma_id)
    op.drop_constraint('inscricoes_pkey', 'inscricoes', type_='primary')
    op.drop_column('inscricoes', 'id')
    op.execute("DROP SEQUENCE IF EXISTS inscricoes_id_seq")
    op.create_primary_key('inscricoes_pkey', 'inscricoes', ['aluno_id', 'turma_id'])
