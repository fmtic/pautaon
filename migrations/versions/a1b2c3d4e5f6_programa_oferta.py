"""Adiciona coluna programa em turma_curso

Revision ID: a1b2c3d4e5f6
Revises: d2e3f4a5b6c7
Create Date: 2026-10-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('turma_curso', sa.Column('programa', sa.String(length=50), nullable=True))
    op.execute("UPDATE turma_curso SET programa = (SELECT turma.programa FROM turma WHERE turma.id = turma_curso.turma_id)")


def downgrade():
    op.drop_column('turma_curso', 'programa')
