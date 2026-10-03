# -*- coding: utf-8 -*-
"""Adiciona colunas de auditoria às tabelas principais

Revision ID: a9f3c8e2d1b7
Revises: e1e3a5b2c333
Create Date: 2026-10-03

Contexto
--------
Parte da estratégia de auditoria global do pautaON (Onda 3C-audit).
Adiciona as colunas ``updated_by_id``, ``updated_by_name`` e ``updated_at``
às tabelas que passaram a herdar ``AuditoriaMixin``:

    - turma
    - tema_aula
    - registro_aula
    - curso
    - conselho_classe
    - inscricoes

Essas colunas são preenchidas automaticamente pelo listener SQLAlchemy
registrado em ``app.models.auditoria_listener``.

Decisões de projeto
-------------------
- ``nullable=True``: garante compatibilidade com registros anteriores à
  implantação da auditoria.
- Sem ``server_default``: ``updated_at`` fica NULL para registros antigos,
  distinguindo-os dos que passaram pela auditoria.
- ``on delete set null`` na FK ``updated_by_id``: impede que a exclusão de
  um usuário cause erro de integridade referencial.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Identificadores da revisão
# ---------------------------------------------------------------------------
revision = "a9f3c8e2d1b7"
down_revision = "e1e3a5b2c333"
branch_labels = None
depends_on = None

# Tabelas que receberão as colunas de auditoria
_TABELAS_AUDITADAS = [
    "turma",
    "tema_aula",
    "registro_aula",
    "curso",
    "conselho_classe",
    "inscricoes",
]


def upgrade() -> None:
    """Adiciona as colunas de auditoria em todas as tabelas alvo.

    As colunas são adicionadas em ordem para garantir que o banco as
    receba na sequência correta (id → nome → timestamp).
    """
    for tabela in _TABELAS_AUDITADAS:
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "updated_by_id",
                    sa.Integer,
                    sa.ForeignKey("user.id", ondelete="SET NULL"),
                    nullable=True,
                    comment="ID do usuário que realizou a última alteração",
                )
            )
            batch_op.add_column(
                sa.Column(
                    "updated_by_name",
                    sa.String(100),
                    nullable=True,
                    comment=(
                        "Snapshot do nome do editor no momento da edição; "
                        "preserva a identidade mesmo após renomeação/exclusão do usuário"
                    ),
                )
            )
            batch_op.add_column(
                sa.Column(
                    "updated_at",
                    sa.DateTime,
                    nullable=True,
                    comment=(
                        "Data/hora da última modificação (fuso local da aplicação); "
                        "NULL indica que o registro nunca foi editado desde o cadastro"
                    ),
                )
            )


def downgrade() -> None:
    """Remove as colunas de auditoria de todas as tabelas alvo.

    A ordem de remoção é inversa à adição: timestamp → nome → id.
    """
    for tabela in _TABELAS_AUDITADAS:
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.drop_column("updated_at")
            batch_op.drop_column("updated_by_name")
            batch_op.drop_column("updated_by_id")
