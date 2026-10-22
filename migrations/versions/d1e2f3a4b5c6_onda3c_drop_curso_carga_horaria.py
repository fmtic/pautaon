"""Onda 3C: remove curso.carga_horaria (C.H. calculada em Turma)

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-10-27

NOTAS
    - `carga_horaria` era a C.H. de aula (horas/dia) do curso.
    - A partir da Onda 3C, esse valor é derivado de Turma.hora_inicio/hora_fim
      e expresso em minutos via `Turma.carga_horaria_aula`.
    - Downgrade restaura a coluna como nullable sem backfill.
"""

from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('curso') as batch_op:
        batch_op.drop_column('carga_horaria')


def downgrade():
    with op.batch_alter_table('curso') as batch_op:
        batch_op.add_column(sa.Column('carga_horaria', sa.Integer(), nullable=True))
