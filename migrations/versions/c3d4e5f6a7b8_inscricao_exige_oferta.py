"""Require every enrollment to point to an offer and prevent active duplicates.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Checagens SOMENTE LEITURA, reportadas juntas em um único RuntimeError.
    # Não se altera dado algum aqui: a limpeza é decisão de negócio (P1 §5).

    # (i) Inscrições sem oferta (turma_curso_id NULL): total, ativas, inativas.
    total_null = conn.execute(
        sa.text("SELECT count(*) FROM inscricoes WHERE turma_curso_id IS NULL")
    ).scalar() or 0
    ativas_null = conn.execute(
        sa.text(
            "SELECT count(*) FROM inscricoes "
            "WHERE turma_curso_id IS NULL AND ativo IS TRUE"
        )
    ).scalar() or 0
    ids_null = [
        str(row[0])
        for row in conn.execute(
            sa.text(
                "SELECT id FROM inscricoes WHERE turma_curso_id IS NULL "
                "ORDER BY id LIMIT 20"
            )
        )
    ]

    # (ii) Pares ativos duplicados por (aluno_id, turma_curso_id).
    dup_rows = conn.execute(
        sa.text(
            "SELECT aluno_id, turma_curso_id, count(*) AS n FROM inscricoes "
            "WHERE ativo IS TRUE AND turma_curso_id IS NOT NULL "
            "GROUP BY aluno_id, turma_curso_id HAVING count(*) > 1 "
            "ORDER BY aluno_id, turma_curso_id"
        )
    ).fetchall()

    if total_null or dup_rows:
        partes = []
        if total_null:
            partes.append(
                f"(i) {total_null} inscrição(ões) com turma_curso_id NULL "
                f"({ativas_null} ativa(s) / {total_null - ativas_null} "
                f"inativa(s)); ids das primeiras 20: {', '.join(ids_null)}"
            )
        if dup_rows:
            chaves = "; ".join(
                f"(aluno_id={a}, turma_curso_id={t}) x{n}" for a, t, n in dup_rows[:20]
            )
            partes.append(
                f"(ii) {len(dup_rows)} par(es) (aluno_id, turma_curso_id) com "
                f"inscrições ativas duplicadas; primeiras 20 chaves: {chaves}"
            )
        raise RuntimeError(
            "Não é possível aplicar c3d4e5f6a7b8 (inscrição exige oferta): "
            + " | ".join(partes)
            + ". Vincule as inscrições às suas ofertas e deduplique as ativas "
            "(nenhum dado foi alterado por esta migration) e rode "
            "scripts/preparar_deploy_onda4.py para revalidar."
        )

    with op.batch_alter_table("inscricoes") as batch_op:
        batch_op.alter_column(
            "turma_curso_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_index(
            "uix_inscricao_ativa_aluno_oferta",
            ["aluno_id", "turma_curso_id"],
            unique=True,
            postgresql_where=sa.text("ativo IS TRUE"),
            sqlite_where=sa.text("ativo = 1"),
        )


def downgrade():
    with op.batch_alter_table("inscricoes") as batch_op:
        batch_op.drop_index("uix_inscricao_ativa_aluno_oferta")
        batch_op.alter_column(
            "turma_curso_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
