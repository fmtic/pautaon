"""Adiciona campos de identidade Google OAuth2 ao modelo User.

Os campos ``google_id`` e ``google_email`` permitem que usuários façam login
via conta Google e que o administrador visualize e gerencie o vínculo no
painel administrativo.

``google_id`` armazena o campo ``sub`` do ID Token retornado pelo Google —
identificador permanente e imutável da conta, mesmo que o e-mail mude.
Um índice único garante que cada conta Google só possa ser vinculada a um
único perfil local.

``google_email`` registra o e-mail Google no momento do último login,
servindo apenas para exibição informativa. Decisões de autenticação usam
sempre ``google_id``.

Ambos os campos são ``nullable`` para compatibilidade retroativa:
registros existentes (AD, locais) ficam com ``NULL`` e continuam
funcionando normalmente sem qualquer intervenção manual.

Revision ID: 6a8df39d
Revises: (nenhuma — primeira migration do repositório)
Create Date: 2026-08-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Identificadores desta revisão
# ---------------------------------------------------------------------------
revision: str = "6a8df39d"
down_revision: str | None = None   # primeira migration
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Aplica as alterações ao banco — adiciona os dois campos e o índice único."""
    with op.batch_alter_table("user", schema=None) as batch_op:
        # Identificador permanente da conta Google (campo ``sub`` do ID Token).
        # O índice único previne que a mesma conta Google seja vinculada a dois
        # perfis distintos, evitando duplicatas silenciosas.
        batch_op.add_column(
            sa.Column(
                "google_id",
                sa.String(length=120),
                nullable=True,
            )
        )

        # E-mail Google registrado no último login — apenas informativo.
        batch_op.add_column(
            sa.Column(
                "google_email",
                sa.String(length=120),
                nullable=True,
            )
        )

        # Índice único em google_id para garantir integridade do vínculo.
        batch_op.create_index(
            "ix_user_google_id",
            ["google_id"],
            unique=True,
        )


def downgrade() -> None:
    """Reverte as alterações — remove os campos e o índice."""
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_index("ix_user_google_id")
        batch_op.drop_column("google_email")
        batch_op.drop_column("google_id")
