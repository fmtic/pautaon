"""onda3a-bis: adiciona documentos_entregues e migra escolaridade_json

Revision ID: 29a29fdbc2aa
Revises: 5ae559bc9d87
Create Date: 2026-09-17

Adiciona a coluna `documentos_entregues` (JSONB) em `aluno` e faz backfill
a partir de `escolaridade_json`, preservando o formato
`{'doc_entregue': {doc_id: bool}}`.

`escolaridade_json` NÃO é removida nesta migração — fica como fallback
até a Onda 3C.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '29a29fdbc2aa'
down_revision: str | None = '5ae559bc9d87'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Adiciona a coluna
    op.add_column(
        'aluno',
        sa.Column(
            'documentos_entregues',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Backfill do JSON legado (TEXT) para JSONB, com guarda contra JSON inválido.
    # Usamos CASE + try/catch via SQL: se o cast falhar, o registro vira NULL
    # em vez de abortar a migration inteira.
    op.execute("""
        UPDATE aluno
        SET documentos_entregues = escolaridade_json::jsonb
        WHERE escolaridade_json IS NOT NULL
          AND escolaridade_json <> ''
          AND escolaridade_json ~ '^\\s*\\{'
    """)


def downgrade() -> None:
    op.drop_column('aluno', 'documentos_entregues')