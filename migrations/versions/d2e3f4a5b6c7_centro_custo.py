"""CentroCusto: catalogo de centros de custo por unidade

Revision ID: d2e3f4a5b6c7
Revises: e7f3a1b9c4d5
Create Date: 2026-10-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd2e3f4a5b6c7'
down_revision = 'e7f3a1b9c4d5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'centro_custo',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(length=150), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('unidade_id', sa.Integer(), sa.ForeignKey('unidade.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('nome', 'unidade_id', name='uq_centro_custo_nome_unidade'),
    )
    # Backfill por unidade a partir das colunas string existentes.
    bind = op.get_bind()
    nomes_por_unidade = {}
    for tabela in ('periodo_letivo', 'turma', 'turma_curso'):
        try:
            rows = bind.execute(sa.text('SELECT unidade_id, centro_custo FROM ' + tabela + ' WHERE centro_custo IS NOT NULL'))
        except Exception:
            continue
        for unidade_id, centro_custo in rows:
            if unidade_id is None or not centro_custo:
                continue
            for parte in str(centro_custo).split(','):
                nome = parte.strip()
                if not nome:
                    continue
                nomes_por_unidade.setdefault(unidade_id, set()).add(nome)
    for unidade_id, nomes in nomes_por_unidade.items():
        for nome in sorted(nomes):
            existe = bind.execute(
                sa.text('SELECT 1 FROM centro_custo WHERE unidade_id = :u AND nome = :n'),
                {'u': unidade_id, 'n': nome},
            ).first()
            if existe:
                continue
            bind.execute(
                sa.text('INSERT INTO centro_custo (nome, ativo, unidade_id, created_at) VALUES (:n, :a, :u, :c)'),
                {'n': nome, 'a': True, 'u': unidade_id, 'c': None},
            )


def downgrade():
    op.drop_table('centro_custo')
