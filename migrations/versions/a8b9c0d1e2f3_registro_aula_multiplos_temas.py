"""Permite associar vários temas planejados a cada registro de aula.

Revision ID: a8b9c0d1e2f3
Revises: f6a7b8c9d0e1
Create Date: 2026-10-26
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'a8b9c0d1e2f3'
down_revision: str | None = 'f6a7b8c9d0e1'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'registro_aula_tema',
        sa.Column('registro_aula_id', sa.Integer(), nullable=False),
        sa.Column('tema_aula_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['registro_aula_id'], ['registro_aula.id'],
            name='fk_registro_aula_tema_registro', ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['tema_aula_id'], ['tema_aula.id'],
            name='fk_registro_aula_tema_tema', ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('registro_aula_id', 'tema_aula_id'),
    )
    op.create_index(
        'ix_registro_aula_tema_tema', 'registro_aula_tema', ['tema_aula_id'],
    )
    op.execute(sa.text(
        'INSERT INTO registro_aula_tema (registro_aula_id, tema_aula_id) '
        'SELECT id, tema_id FROM registro_aula WHERE tema_id IS NOT NULL'
    ))


def downgrade() -> None:
    op.drop_index('ix_registro_aula_tema_tema', table_name='registro_aula_tema')
    op.drop_table('registro_aula_tema')
