"""ajusta atendimento (setor, dados, atendido_por) e user.google_id

Revision ID: 7aa724d05691
Revises: a1b2c3d4
Create Date: 2026-09-11 17:22:18.318013

--------------------------------------------------------------------------------
NOTA HISTÓRICA
--------------------------------------------------------------------------------
Esta migration foi gerada pelo autogenerate com o nome "add google_id and
google_email to user", mas o conteúdo real é:

    - Ajustes de schema em `atendimento` (tamanhos, nullability e índices).
    - Ajuste de tamanho em `user.google_id`.

A coluna `user.google_email` NÃO é criada aqui, apesar do nome original.
Se ainda for necessária, deve ser adicionada por uma migration futura.

--------------------------------------------------------------------------------
MUDANÇAS APLICADAS
--------------------------------------------------------------------------------
[atendimento]
  1. setor             : VARCHAR(30)  -> VARCHAR(50)
  2. dados             : JSON nullable -> JSON NOT NULL
  3. atendido_por_id   : NOT NULL     -> nullable
  4. atendido_por_nome : VARCHAR(100) -> VARCHAR(150)
  5. drop idx          : ix_atendimento_aluno_id
  6. drop idx          : ix_atendimento_data

[user]
  7. google_id         : VARCHAR(120) -> VARCHAR(100)

--------------------------------------------------------------------------------
REVERSIBILIDADE
--------------------------------------------------------------------------------
O `downgrade()` recria os índices removidos e reverte os tipos. Mas atenção:

  - Se houver linhas em `atendimento` com `dados IS NULL`, o `downgrade`
    (que torna `dados` nullable de novo) NÃO é afetado. Já o `upgrade`
    (que torna NOT NULL) falha se houver NULLs — ver §2 em upgrade().
  - Se houver linhas com `setor` > 30 chars, o downgrade trunca silenciosamente
    ou falha, dependendo do SGBD. Em Postgres, ele rejeita (não trunca).
--------------------------------------------------------------------------------
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Identificadores desta revisão
revision: str = "7aa724d05691"
down_revision: str | None = "a1b2c3d4"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # =========================================================================
    # ATENDIMENTO
    # =========================================================================
    with op.batch_alter_table("atendimento", schema=None) as batch_op:
        # ---------------------------------------------------------------------
        # 1. setor: VARCHAR(30) -> VARCHAR(50)
        #    Motivo: o modelo permite 50 caracteres (String(50)); a coluna
        #    antiga tinha 30, gerando truncamento silencioso em alguns SGBDs.
        #    NOTA: `setor` está marcado como LEGADO no modelo, mas o
        #    alargamento é seguro e não muda comportamento do fluxo atual.
        # ---------------------------------------------------------------------
        batch_op.alter_column(
            "setor",
            existing_type=sa.VARCHAR(length=30),
            type_=sa.String(length=50),
            existing_nullable=False,
        )

        # ---------------------------------------------------------------------
        # 2. dados: JSON nullable -> JSON NOT NULL
        #    Motivo: o modelo define `dados: dict = db.Column(db.JSON,
        #    nullable=False, default=dict)`. A migration anterior havia
        #    deixado a coluna nullable.
        #
        #    ⚠️  IMPORTANTE: se existirem linhas com `dados IS NULL`, este
        #    ALTER falha no Postgres. Antes de aplicar em produção, rode:
        #
        #        SELECT COUNT(*) FROM atendimento WHERE dados IS NULL;
        #
        #    Se retornar > 0, faça o backfill primeiro:
        #
        #        UPDATE atendimento SET dados = '{}'::json WHERE dados IS NULL;
        # ---------------------------------------------------------------------
        batch_op.alter_column(
            "dados",
            existing_type=postgresql.JSON(astext_type=sa.Text()),
            nullable=False,
        )

        # ---------------------------------------------------------------------
        # 3. atendido_por_id: NOT NULL -> nullable
        #    Motivo: o modelo permite `atendido_por_id` nulo (relacionamento
        #    opcional com User). A migration anterior deixou como NOT NULL.
        # ---------------------------------------------------------------------
        batch_op.alter_column(
            "atendido_por_id",
            existing_type=sa.INTEGER(),
            nullable=True,
        )

        # ---------------------------------------------------------------------
        # 4. atendido_por_nome: VARCHAR(100) -> VARCHAR(150)
        #    Motivo: alinhar com o modelo (String(150)).
        # ---------------------------------------------------------------------
        batch_op.alter_column(
            "atendido_por_nome",
            existing_type=sa.VARCHAR(length=100),
            type_=sa.String(length=150),
            existing_nullable=True,
        )

        # ---------------------------------------------------------------------
        # 5 e 6. Drop dos índices `ix_atendimento_aluno_id` e
        #        `ix_atendimento_data`.
        #
        #    ⚠️  ATENÇÃO: o autogenerate removeu esses índices porque eles
        #    não estão declarados no modelo atual. Antes de aplicar em
        #    produção, confirme que:
        #
        #      a) Nenhuma query em produção depende deles (pouco provável,
        #         mas vale checar `pg_stat_user_indexes`).
        #      b) O ganho/perda de performance é aceitável.
        #
        #    Se forem realmente necessários, adicione-os de volta em uma
        #    migration futura (com índice composto, idealmente).
        # ---------------------------------------------------------------------
        batch_op.drop_index(batch_op.f("ix_atendimento_aluno_id"))
        batch_op.drop_index(batch_op.f("ix_atendimento_data"))

    # =========================================================================
    # USER
    # =========================================================================
    with op.batch_alter_table("user", schema=None) as batch_op:
        # ---------------------------------------------------------------------
        # 7. google_id: VARCHAR(120) -> VARCHAR(100)
        #    Motivo: alinhar com o modelo (String(100)). IDs do Google
        #    (sub claim) são numéricos com ~21 dígitos, mas o campo é
        #    varchar, não bigint, por compatibilidade com múltiplos providers.
        # ---------------------------------------------------------------------
        batch_op.alter_column(
            "google_id",
            existing_type=sa.VARCHAR(length=120),
            type_=sa.String(length=100),
            existing_nullable=True,
        )


def downgrade() -> None:
    # =========================================================================
    # Ordem inversa do upgrade.
    # =========================================================================

    # -------------------------------------------------------------------------
    # USER
    # -------------------------------------------------------------------------
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column(
            "google_id",
            existing_type=sa.String(length=100),
            type_=sa.VARCHAR(length=120),
            existing_nullable=True,
        )

    # -------------------------------------------------------------------------
    # ATENDIMENTO
    # -------------------------------------------------------------------------
    with op.batch_alter_table("atendimento", schema=None) as batch_op:
        # Recria os índices removidos no upgrade.
        # A ordem aqui importa pouco, mas mantemos a mesma ordem do upgrade
        # invertida para facilitar leitura.
        batch_op.create_index(
            batch_op.f("ix_atendimento_data"),
            ["data_atendimento"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_atendimento_aluno_id"),
            ["aluno_id"],
            unique=False,
        )

        # Reverte tamanhos e nullability.
        batch_op.alter_column(
            "atendido_por_nome",
            existing_type=sa.String(length=150),
            type_=sa.VARCHAR(length=100),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "atendido_por_id",
            existing_type=sa.INTEGER(),
            nullable=False,
        )
        batch_op.alter_column(
            "dados",
            existing_type=postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        )
        batch_op.alter_column(
            "setor",
            existing_type=sa.String(length=50),
            type_=sa.VARCHAR(length=30),
            existing_nullable=False,
        )
