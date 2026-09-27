"""inscricao_pk_propria

Troca a PK composta (aluno_id, turma_id) da tabela inscricoes por uma PK
autoincrementada (id), permitindo múltiplos registros do mesmo par.

Compatível com SQLite e PostgreSQL.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "26e459a7e00a"
down_revision: str | None = "99f0996802e6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        # O banco SQLite já possui a coluna `id`, porém ela foi criada sem
        # PK durante uma tentativa anterior de aplicação desta migration.
        #
        # O rowid identifica unicamente cada registro existente. Usamos esse
        # valor apenas para preencher os IDs antes da reconstrução da tabela.

        op.execute(
            """
            UPDATE inscricoes
            SET id = rowid
            WHERE id IS NULL
            """
        )

        # Reconstrói a tabela porque SQLite não permite alterar diretamente
        # uma PK composta para uma PK simples.
        op.execute(
            """
            CREATE TABLE inscricoes_nova (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                aluno_id INTEGER NOT NULL,
                turma_id INTEGER NOT NULL,
                ativo BOOLEAN DEFAULT 1,
                data_desativacao DATETIME,
                motivo_desativacao VARCHAR(50),
                nivel VARCHAR(30),
                data_inicio DATE,
                FOREIGN KEY(aluno_id) REFERENCES aluno (id),
                FOREIGN KEY(turma_id) REFERENCES turma (id)
            )
            """
        )

        op.execute(
            """
            INSERT INTO inscricoes_nova (
                id,
                aluno_id,
                turma_id,
                ativo,
                data_desativacao,
                motivo_desativacao,
                nivel,
                data_inicio
            )
            SELECT
                id,
                aluno_id,
                turma_id,
                ativo,
                data_desativacao,
                motivo_desativacao,
                nivel,
                data_inicio
            FROM inscricoes
            """
        )

        op.drop_table("inscricoes")
        op.rename_table("inscricoes_nova", "inscricoes")

    else:
        # PostgreSQL.
        op.drop_constraint(
            "inscricoes_pkey",
            "inscricoes",
            type_="primary",
        )

        # A coluna pode já existir se esta migration tiver sido parcialmente
        # executada.
        inspector = sa.inspect(bind)
        colunas = {
            coluna["name"]
            for coluna in inspector.get_columns("inscricoes")
        }

        if "id" not in colunas:
            op.add_column(
                "inscricoes",
                sa.Column("id", sa.Integer(), nullable=True),
            )

        op.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS inscricoes_id_seq
            """
        )

        op.execute(
            """
            UPDATE inscricoes
            SET id = nextval('inscricoes_id_seq')
            WHERE id IS NULL
            """
        )

        op.execute(
            """
            ALTER SEQUENCE inscricoes_id_seq
            OWNED BY inscricoes.id
            """
        )

        op.execute(
            """
            ALTER TABLE inscricoes
            ALTER COLUMN id SET DEFAULT nextval('inscricoes_id_seq')
            """
        )

        op.execute(
            """
            ALTER TABLE inscricoes
            ALTER COLUMN id SET NOT NULL
            """
        )

        op.create_primary_key(
            "inscricoes_pkey",
            "inscricoes",
            ["id"],
        )

        op.alter_column(
            "inscricoes",
            "aluno_id",
            nullable=False,
        )

        op.alter_column(
            "inscricoes",
            "turma_id",
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        # Não é possível restaurar automaticamente a PK composta caso
        # existam múltiplos registros para o mesmo aluno/turma.
        raise RuntimeError(
            "Downgrade desta migration não é suportado automaticamente no SQLite."
        )

    op.drop_constraint(
        "inscricoes_pkey",
        "inscricoes",
        type_="primary",
    )

    op.drop_column("inscricoes", "id")

    op.execute(
        "DROP SEQUENCE IF EXISTS inscricoes_id_seq"
    )

    op.create_primary_key(
        "inscricoes_pkey",
        "inscricoes",
        ["aluno_id", "turma_id"],
    )