"""Require every course offer to have a program.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # (a) Projeção oferta ativa principal -> turma SEM nunca zerar o programa.
    #     COALESCE com o valor atual: se não houver oferta ativa (ou a oferta
    #     ativa estiver com programa NULL), turma.programa é PRESERVADO.
    #     (Defeito P-1 do ensaio E: sem COALESCE o UPDATE apagava programa de
    #     turma sem oferta ativa.)
    op.execute(sa.text("""
        UPDATE turma
        SET programa = COALESCE(
            (
                SELECT tc.programa
                FROM turma_curso AS tc
                WHERE tc.turma_id = turma.id AND tc.ativo IS TRUE
                    AND tc.programa IS NOT NULL
                ORDER BY tc.principal DESC, tc.id ASC
                LIMIT 1
            ),
            turma.programa
        )
    """))

    # (b) Antes do SET NOT NULL, recusar se sobrou oferta com programa NULL.
    #     Não atribui programa padrão (decisão de negócio, P-5 do P1).
    null_total = conn.execute(
        sa.text("SELECT count(*) FROM turma_curso WHERE programa IS NULL")
    ).scalar() or 0
    if null_total:
        ids_null = [
            str(row[0])
            for row in conn.execute(
                sa.text(
                    "SELECT id FROM turma_curso WHERE programa IS NULL "
                    "ORDER BY id LIMIT 20"
                )
            )
        ]
        raise RuntimeError(
            "Não é possível aplicar d4e5f6a7b8c9 (programa obrigatório na "
            f"oferta): {null_total} oferta(s) ainda com turma_curso.programa "
            f"NULL. Ids das primeiras 20: {', '.join(ids_null)}. "
            "Defina o programa dessas ofertas/turmas e rode "
            "scripts/preparar_deploy_onda4.py para revalidar; nenhum "
            "programa padrão foi atribuído."
        )

    with op.batch_alter_table("turma_curso") as batch_op:
        batch_op.alter_column(
            "programa",
            existing_type=sa.String(length=50),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("turma_curso") as batch_op:
        batch_op.alter_column(
            "programa",
            existing_type=sa.String(length=50),
            nullable=True,
        )
