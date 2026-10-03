"""Onda 3B-ter: auditoria de edição em aluno

Revision ID: f1a2b3c4d5e6
Revises: 4c8e2f7a1b30
Create Date: 2026-09-27

Adiciona três colunas de auditoria de edição à tabela `aluno`:

    updated_by_id   (integer, FK → user.id, nullable, ON DELETE SET NULL)
        Identificação do usuário que realizou a última edição. Anulado
        automaticamente se o usuário for excluído do sistema.

    updated_by_name (varchar(100), nullable)
        Snapshot do nome do editor no momento da edição. Preserva a
        identidade mesmo após exclusão ou renomeação do usuário.

    updated_at      (timestamp, nullable, sem default)
        Data e hora da última edição. Permanece NULL para alunos que
        nunca foram editados desde o cadastro, distinguindo-os dos
        editados. Não usa `server_default` — o valor é gravado
        explicitamente pela rota `registros.editar_aluno`.

NOTAS
-----
- A FK `fk_aluno_updated_by_id` é criada apenas no PostgreSQL (produção).
  O SQLite não suporta `ADD CONSTRAINT` via ALTER TABLE, mas aceita a
  coluna sem a constraint formal.
- Não há backfill: registros existentes ficam com NULL nos três campos,
  o que é semanticamente correto ("nunca editado após esta migration").
- O `downgrade` remove a FK antes de dropar as colunas para evitar erro
  de integridade referencial no PostgreSQL.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "4c8e2f7a1b30"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("aluno", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("aluno", sa.Column("updated_by_name", sa.String(100), nullable=True))
    op.add_column("aluno", sa.Column("updated_at", sa.DateTime(), nullable=True))

    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        op.create_foreign_key(
            "fk_aluno_updated_by_id",
            "aluno",
            "user",
            ["updated_by_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        op.drop_constraint("fk_aluno_updated_by_id", "aluno", type_="foreignkey")

    op.drop_column("aluno", "updated_at")
    op.drop_column("aluno", "updated_by_name")
    op.drop_column("aluno", "updated_by_id")
