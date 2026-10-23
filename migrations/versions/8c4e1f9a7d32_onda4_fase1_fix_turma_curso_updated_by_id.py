"""Onda4 Fase1 fix: colunas de auditoria em turma_curso (AuditoriaMixin)

Revision ID: 8c4e1f9a7d32
Revises: 311d554dfd6e
Create Date: 2026-10-22 20:35:00.000000

A revision `311d554dfd6e` criou `turma_curso` SEM as três colunas do
AuditoriaMixin (`updated_by_id`, `updated_by_name`, `updated_at`). O SQLite
dos testes não expõe o problema porque `create_all()` deriva o schema do
modelo; no PostgreSQL, qualquer consulta ORM (o `updated_by` usa
`lazy='joined'`) falha com "coluna turma_curso.updated_by_* não existe".

Correção como revision nova (a original já foi aplicada no banco local):
    - add `updated_by_id` (integer, nullable) com FK
      `fk_turma_curso_updated_by_id` → user.id `ON DELETE SET NULL` (PG),
      `updated_by_name` (varchar(100)) e `updated_at` (timestamp), todas
      nullable e sem server_default — mesmo padrão de `a9f3c8e2d1b7`.
    - Guards de idempotência por inspeção: coluna/FK que já existir é pulada.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '8c4e1f9a7d32'
down_revision: str | None = '311d554dfd6e'
branch_labels: str | None = None
depends_on: str | None = None


def _colunas(tabela: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {c["name"] for c in insp.get_columns(tabela)}


def _fks(tabela: str) -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return {fk["name"] for fk in insp.get_foreign_keys(tabela) if fk.get("name")}


def upgrade() -> None:
    cols = _colunas('turma_curso')
    if 'updated_by_id' not in cols:
        op.add_column(
            'turma_curso',
            sa.Column(
                'updated_by_id', sa.Integer(), nullable=True,
                comment='ID do usuário que fez a última alteração',
            ),
        )
    if 'updated_by_name' not in cols:
        op.add_column(
            'turma_curso',
            sa.Column(
                'updated_by_name', sa.String(length=100), nullable=True,
                comment='Snapshot do nome do editor no momento da edição',
            ),
        )
    if 'updated_at' not in cols:
        op.add_column(
            'turma_curso',
            sa.Column(
                'updated_at', sa.DateTime(), nullable=True,
                comment='Data/hora da última modificação (fuso local)',
            ),
        )

    # A FK formal só no PostgreSQL (padrão f1a2b3c4d5e6/e1e3a5b2c333);
    # no SQLite a coluna existe sem constraint — os testes usam create_all.
    if op.get_bind().dialect.name == 'postgresql':
        if 'fk_turma_curso_updated_by_id' not in _fks('turma_curso'):
            op.create_foreign_key(
                'fk_turma_curso_updated_by_id',
                'turma_curso',
                'user',
                ['updated_by_id'],
                ['id'],
                ondelete='SET NULL',
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        if 'fk_turma_curso_updated_by_id' in _fks('turma_curso'):
            op.drop_constraint(
                'fk_turma_curso_updated_by_id', 'turma_curso', type_='foreignkey',
            )

    cols = _colunas('turma_curso')
    for coluna in ('updated_at', 'updated_by_name', 'updated_by_id'):
        if coluna in cols:
            op.drop_column('turma_curso', coluna)
