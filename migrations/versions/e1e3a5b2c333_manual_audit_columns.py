"""Add auditoria de edição columns to aluno table

Revision ID: e1e3a5b2c333
Revises: f1a2b3c4d5e6
Create Date: 2026-10-03 00:31:06.234247
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e1e3a5b2c333"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add columns regardless of DB engine
    op.add_column("aluno", sa.Column("updated_by_id", sa.Integer(), nullable=True))
    op.add_column("aluno", sa.Column("updated_by_name", sa.String(100), nullable=True))
    op.add_column("aluno", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Create foreign key only on PostgreSQL
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
    # Drop foreign key first on PostgreSQL
    bind = op.get_bind()
    if bind.engine.name == "postgresql":
        op.drop_constraint("fk_aluno_updated_by_id", "aluno", type_="foreignkey")

    # Then drop the columns
    op.drop_column("aluno", "updated_at")
    op.drop_column("aluno", "updated_by_name")
    op.drop_column("aluno", "updated_by_id")
