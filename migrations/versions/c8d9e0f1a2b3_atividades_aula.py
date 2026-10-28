"""A1 — "Atividades da aula" no diário (`registro_aula.atividades`).

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-10-28

Contexto: a tela de lançamento de frequência ganha um segundo campo de texto,
ao lado das Observações/Descrição da Aula. O conteúdo é gravado no diário
(`registro_aula`), é independente das observações e NÃO participa de
frequência, pauta impressa, BI, relatórios ou exportações.

Upgrade: adiciona `registro_aula.atividades` (TEXT, nullable, sem backfill —
os registros antigos ficam NULL).
Downgrade: remove a coluna; nenhuma linha de `registro_aula` é apagada.

Portabilidade: `ALTER TABLE ... ADD/DROP COLUMN` funciona no PostgreSQL e no
SQLite usado nos testes (3.35+).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "registro_aula"
COLUNA = "atividades"


def _adicionar_coluna(bind) -> None:
    """Cria a coluna nullable no diário (idempotente por DDL)."""
    bind.execute(sa.text(
        f"ALTER TABLE {TABELA} ADD COLUMN {COLUNA} TEXT"
    ))


def _dropar_coluna(bind) -> None:
    """Remove a coluna — sem tocar nas demais da tabela nem nas linhas."""
    bind.execute(sa.text(
        f"ALTER TABLE {TABELA} DROP COLUMN {COLUNA}"
    ))


def upgrade() -> None:
    bind = op.get_bind()
    _adicionar_coluna(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _dropar_coluna(bind)
