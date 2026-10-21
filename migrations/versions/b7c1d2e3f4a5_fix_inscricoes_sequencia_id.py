"""fix_inscricoes_sequencia_id

Garante que a coluna `inscricoes.id` possua sequência e default no PostgreSQL.

Contexto:
    A migration `26e459a7e00a_inscricao_pk_propria` já previa criar a sequência
    `inscricoes_id_seq` e o default `nextval(...)`. Porém, o banco em uso ficou
    sem a sequência (schema restaurado a partir de dump antigo, que não a
    incluía). Sem default, todo INSERT de nova matrícula falha com
    `NotNullViolation: valor nulo na coluna "id" de "inscricoes"`, quebrando a
    inscrição de alunos pela interface.

    Esta migration corrige o drift de forma idempotente (só PostgreSQL; SQLite
    usa AUTOINCREMENT e não precisa de nada aqui).
"""

from __future__ import annotations

from alembic import op


revision: str = "b7c1d2e3f4a5"
down_revision: str | None = "5a676f37b9a3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Cria a sequência se não existir e a vincula à coluna.
    op.execute("CREATE SEQUENCE IF NOT EXISTS inscricoes_id_seq")
    op.execute("ALTER SEQUENCE inscricoes_id_seq OWNED BY inscricoes.id")
    op.execute(
        "ALTER TABLE inscricoes ALTER COLUMN id "
        "SET DEFAULT nextval('inscricoes_id_seq')"
    )

    # Alinha a sequência com o maior id já presente, garantindo que o próximo
    # nextval devolva max(id) + 1 (evita colisão com registros existentes).
    op.execute(
        "SELECT setval('inscricoes_id_seq', "
        "(SELECT COALESCE(MAX(id), 0) + 1 FROM inscricoes), false)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE inscricoes ALTER COLUMN id DROP DEFAULT")
    op.execute("DROP SEQUENCE IF EXISTS inscricoes_id_seq")
