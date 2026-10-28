"""A1 — Valores do Esportista: catálogo + FK opcional em `frequencia`.

Revision ID: b7c8d9e0f1a2
Revises: 8d2e3f4a5b6c
Create Date: 2026-10-28

Contexto: o lançamento de frequência ganha um dado ADICIONAL por aluno/aula —
o valor/postura do esportista. Ele NÃO participa de nenhuma conta de
presença, falta, justificada, total de aulas ou percentual, nem de pauta,
diário, relatório ou exportação (`app/utils/logica.py`).

Upgrade:
    1. cria `valor_esportista` (nome até 100, ativo, unidade_id NOT NULL,
       created_at/updated_at) com FK para `unidade` e índice único FUNCIONAL
       `uix_valor_esportista_nome_unidade` em `(lower(nome), unidade_id)` —
       a unicidade é por unidade e sem diferenciar maiúsculas de minúsculas;
    2. adiciona `frequencia.valor_esportista_id` NULL (nenhum backfill: os
       registros antigos ficam NULL) com FK `fk_frequencia_valor_esportista`
       ON DELETE SET NULL e índice `ix_frequencia_valor_esportista`.

Downgrade: remove índice, FK e coluna de `frequencia` e depois a tabela.
Nenhuma linha de `frequencia` é apagada ou alterada além da coluna nova.

Portabilidade: o SQLite (só testes) não aceita `ALTER TABLE ... ADD
CONSTRAINT`; nele a coluna é criada sem a FK declarada e o índice é criado
normalmente. O PostgreSQL recebe a FK e o índice. O modelo `Frequencia`
declara a FK, então `db.create_all()` (testes) já nasce com ela.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "8d2e3f4a5b6c"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "valor_esportista"
TABELA_FREQUENCIA = "frequencia"
COLUNA = "valor_esportista_id"
FK = "fk_frequencia_valor_esportista"
FK_UNIDADE = "fk_valor_esportista_unidade"
INDICE_FREQ = "ix_frequencia_valor_esportista"
UNICO_NOME = "uix_valor_esportista_nome_unidade"


def _criar_tabela(bind) -> None:
    """Cria `valor_esportista` + índice único funcional (idempotente por DDL)."""
    metadata = sa.MetaData()
    # Stub para o compilador resolver a FK: o `MetaData` da migration é
    # descartável e não conhece a tabela `unidade` existente no banco.
    sa.Table("unidade", metadata, sa.Column("id", sa.Integer(), primary_key=True))
    tabela = sa.Table(
        TABELA,
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column(
            "ativo", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("unidade_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["unidade_id"], ["unidade.id"], name=FK_UNIDADE,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    tabela.create(bind)
    sa.Index(
        UNICO_NOME, sa.text("lower(nome)"), tabela.c.unidade_id, unique=True,
    ).create(bind)


def _adicionar_coluna_frequencia(bind) -> None:
    """Adiciona a coluna NULL, a FK (Postgres) e o índice."""
    eh_postgres = bind.dialect.name == "postgresql"
    if eh_postgres:
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQUENCIA} ADD COLUMN {COLUNA} INTEGER"
        ))
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQUENCIA} ADD CONSTRAINT {FK} "
            f"FOREIGN KEY ({COLUNA}) REFERENCES {TABELA}(id) ON DELETE SET NULL"
        ))
    else:
        # SQLite: ADD COLUMN aceita REFERENCES, mas não CONSTRAINT nomeada.
        # A integridade referencial é garantida pelo modelo/create_all.
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQUENCIA} ADD COLUMN {COLUNA} INTEGER "
            f"REFERENCES {TABELA}(id) ON DELETE SET NULL"
        ))
    bind.execute(sa.text(
        f"CREATE INDEX {INDICE_FREQ} ON {TABELA_FREQUENCIA} ({COLUNA})"
    ))


def _dropar_coluna_frequencia(bind) -> None:
    """Remove índice, FK (Postgres) e a coluna — sem tocar nas demais linhas."""
    bind.execute(sa.text(f"DROP INDEX IF EXISTS {INDICE_FREQ}"))
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQUENCIA} DROP CONSTRAINT IF EXISTS {FK}"
        ))
    bind.execute(sa.text(
        f"ALTER TABLE {TABELA_FREQUENCIA} DROP COLUMN {COLUNA}"
    ))


def _dropar_tabela(bind) -> None:
    bind.execute(sa.text(f"DROP INDEX IF EXISTS {UNICO_NOME}"))
    bind.execute(sa.text(f"DROP TABLE {TABELA}"))


def upgrade() -> None:
    bind = op.get_bind()
    _criar_tabela(bind)
    _adicionar_coluna_frequencia(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _dropar_coluna_frequencia(bind)
    _dropar_tabela(bind)
