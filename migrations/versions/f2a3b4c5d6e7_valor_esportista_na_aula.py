"""AJ16-B — Valor do Esportista passa a pertencer à AULA (N:N com `registro_aula`).

Revision ID: f2a3b4c5d6e7
Revises: c1d2e3f4a5b6
Create Date: 2026-11-09

Contexto: até a A1 o valor/postura do esportista era um FK opcional POR ALUNO
em `frequencia.valor_esportista_id`. A regra de negócio passou a tratá-lo como
dado da AULA (oferta + data), com 0..N valores, igual aos temas. Esta revisão
move o dado para a tabela associativa `registro_aula_valor_esportista`
(PK composta; FK `registro_aula` ON DELETE CASCADE; FK `valor_esportista`
ON DELETE RESTRICT; índice reverso) e remove a coluna antiga.

Upgrade (transação única, nesta ordem):
    1. cria `registro_aula_valor_esportista` e o índice reverso;
    2. GUARDAS (abortam antes de qualquer escrita e desfazem a transação):
       - linha de `frequencia` com valor e `turma_curso_id IS NULL`;
       - par (`turma_curso_id`, `data`) com valor e sem `registro_aula`;
    3. backfill: um vínculo por (diário canônico, valor distinto), escolhendo
       `MIN(registro_aula.id)` quando houver diário duplicado no mesmo par.
       O backfill é idempotente (não duplica vínculos já existentes);
    4. verificação interna: o conjunto (oferta, data, valor) antigo precisa ser
       IGUAL ao novo; qualquer diferença aborta;
    5. remove o índice, a FK (PostgreSQL) e a coluna
       `frequencia.valor_esportista_id`.

Downgrade: recria `frequencia.valor_esportista_id` NULL com FK
(`ON DELETE SET NULL`) e índice e remove a tabela nova. **NÃO restaura o
vínculo aluno↔valor**: o dado antigo era por aluno e o novo é por aula; o
downgrade devolve a coluna vazia (NULL) em todas as linhas. O conjunto de
valores por aula também é perdido ao dropar a tabela.

Portabilidade: PostgreSQL recebe as constraints nomeadas; o SQLite (usado
apenas nos testes) cria a tabela com as mesmas FKs via SQLAlchemy e usa
`ALTER TABLE ... ADD COLUMN` com `REFERENCES` para a coluna do downgrade.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | None = None
depends_on: str | None = None

TABELA = "registro_aula_valor_esportista"
TABELA_FREQ = "frequencia"
TABELA_REGISTRO = "registro_aula"
TABELA_VALOR = "valor_esportista"
COLUNA = "valor_esportista_id"
PK = "pk_registro_aula_valor_esportista"
FK_REGISTRO = "fk_registro_aula_valor_esportista_registro"
FK_VALOR = "fk_registro_aula_valor_esportista_valor"
INDICE_VALOR = "ix_registro_aula_valor_esportista_valor"
FK_ANTIGA = "fk_frequencia_valor_esportista"
INDICE_ANTIGO = "ix_frequencia_valor_esportista"


def _eh_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _colunas(bind, tabela: str) -> set[str]:
    insp = sa.inspect(bind)
    if not insp.has_table(tabela):
        return set()
    return {c["name"] for c in insp.get_columns(tabela)}


def _criar_tabela(bind) -> None:
    """Cria a associação e o índice reverso."""
    metadata = sa.MetaData()
    # Stubs para o compilador resolver as FKs; não são criados aqui.
    sa.Table(
        TABELA_REGISTRO, metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    sa.Table(
        TABELA_VALOR, metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    tabela = sa.Table(
        TABELA,
        metadata,
        sa.Column("registro_aula_id", sa.Integer(), nullable=False),
        sa.Column("valor_esportista_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["registro_aula_id"], [f"{TABELA_REGISTRO}.id"],
            name=FK_REGISTRO, ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["valor_esportista_id"], [f"{TABELA_VALOR}.id"],
            name=FK_VALOR, ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "registro_aula_id", "valor_esportista_id", name=PK,
        ),
    )
    tabela.create(bind)
    sa.Index(INDICE_VALOR, tabela.c.valor_esportista_id).create(bind)


def _checar_guardas(bind) -> None:
    """Aborta se o backfill não tiver como representar o dado antigo."""
    legado = bind.execute(sa.text(
        f"SELECT COUNT(*) FROM {TABELA_FREQ} "
        f"WHERE {COLUNA} IS NOT NULL AND turma_curso_id IS NULL"
    )).scalar()
    if legado:
        raise RuntimeError(
            "Upgrade de f2a3b4c5d6e7 (AJ16-B) recusado: há "
            f"{int(legado)} linha(s) de frequencia com valor e "
            "turma_curso_id NULL. O valor agora pertence à AULA (oferta + "
            "data) e não há oferta para associá-lo. Associe/corrija esses "
            "lançamentos ou restaure de backup. Nada foi alterado."
        )

    sem_diario = bind.execute(sa.text(
        f"SELECT COUNT(*) FROM {TABELA_FREQ} f "
        f"WHERE f.{COLUNA} IS NOT NULL AND f.turma_curso_id IS NOT NULL "
        "AND NOT EXISTS ("
        f"  SELECT 1 FROM {TABELA_REGISTRO} r "
        "  WHERE r.turma_curso_id = f.turma_curso_id AND r.data = f.data"
        ")"
    )).scalar()
    if sem_diario:
        raise RuntimeError(
            "Upgrade de f2a3b4c5d6e7 (AJ16-B) recusado: há "
            f"{int(sem_diario)} linha(s) de frequencia com valor em par "
            "(turma_curso_id, data) sem registro_aula correspondente. O "
            "backfill não tem diário canônico para receber o valor. Crie o "
            "diário (ou restaure de backup) antes de migrar. Nada foi alterado."
        )


def _backfill(bind) -> None:
    """Migra o conjunto (oferta, data, valor) para a associação, sem duplicar."""
    bind.execute(sa.text(
        f"INSERT INTO {TABELA} (registro_aula_id, valor_esportista_id) "
        "SELECT DISTINCT r.id, f.valor_esportista_id "
        f"FROM {TABELA_FREQ} f "
        f"JOIN {TABELA_REGISTRO} r ON r.id = ("
        f"  SELECT MIN(r2.id) FROM {TABELA_REGISTRO} r2 "
        "  WHERE r2.turma_curso_id = f.turma_curso_id AND r2.data = f.data"
        ") "
        f"WHERE f.{COLUNA} IS NOT NULL AND f.turma_curso_id IS NOT NULL "
        "EXCEPT "
        f"SELECT registro_aula_id, valor_esportista_id FROM {TABELA}"
    ))


def _verificar_conjuntos(bind) -> None:
    """Confere que o conjunto antigo (oferta, data, valor) = conjunto novo."""
    antigo = (
        f"SELECT DISTINCT f.turma_curso_id, f.data, f.{COLUNA} "
        f"FROM {TABELA_FREQ} f "
        f"WHERE f.{COLUNA} IS NOT NULL AND f.turma_curso_id IS NOT NULL"
    )
    novo = (
        "SELECT DISTINCT r.turma_curso_id, r.data, l.valor_esportista_id "
        f"FROM {TABELA} l "
        f"JOIN {TABELA_REGISTRO} r ON r.id = l.registro_aula_id"
    )
    so_antigo = bind.execute(sa.text(
        f"SELECT COUNT(*) FROM ({antigo} EXCEPT {novo}) sobra"
    )).scalar()
    so_novo = bind.execute(sa.text(
        f"SELECT COUNT(*) FROM ({novo} EXCEPT {antigo}) sobra"
    )).scalar()
    if so_antigo or so_novo:
        raise RuntimeError(
            "Upgrade de f2a3b4c5d6e7 (AJ16-B) abortado: a verificação "
            "interna encontrou diferença entre o conjunto antigo (oferta, "
            "data, valor) e o novo "
            f"({int(so_antigo)} só no antigo, {int(so_novo)} só no novo). "
            "Nada foi alterado."
        )


def _dropar_coluna_antiga(bind) -> None:
    """Remove índice, FK (PostgreSQL) e a coluna antiga de `frequencia`."""
    if _eh_postgres(bind):
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {INDICE_ANTIGO}"))
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQ} DROP CONSTRAINT IF EXISTS {FK_ANTIGA}"
        ))
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQ} DROP COLUMN IF EXISTS {COLUNA}"
        ))
        return

    if COLUNA not in _colunas(bind, TABELA_FREQ):
        return
    bind.execute(sa.text(f"DROP INDEX IF EXISTS {INDICE_ANTIGO}"))
    bind.execute(sa.text(
        f"ALTER TABLE {TABELA_FREQ} DROP COLUMN {COLUNA}"
    ))


def _dropar_tabela(bind) -> None:
    bind.execute(sa.text(f"DROP INDEX IF EXISTS {INDICE_VALOR}"))
    bind.execute(sa.text(f"DROP TABLE IF EXISTS {TABELA}"))


def _recriar_coluna_antiga(bind) -> None:
    """Downgrade: recria a coluna nullable + FK + índice (sem dados)."""
    if _eh_postgres(bind):
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQ} ADD COLUMN IF NOT EXISTS {COLUNA} INTEGER"
        ))
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQ} DROP CONSTRAINT IF EXISTS {FK_ANTIGA}"
        ))
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQ} ADD CONSTRAINT {FK_ANTIGA} "
            f"FOREIGN KEY ({COLUNA}) REFERENCES {TABELA_VALOR}(id) "
            "ON DELETE SET NULL"
        ))
        bind.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS {INDICE_ANTIGO} "
            f"ON {TABELA_FREQ} ({COLUNA})"
        ))
        return

    if COLUNA not in _colunas(bind, TABELA_FREQ):
        bind.execute(sa.text(
            f"ALTER TABLE {TABELA_FREQ} ADD COLUMN {COLUNA} INTEGER "
            f"REFERENCES {TABELA_VALOR}(id) ON DELETE SET NULL"
        ))
    bind.execute(sa.text(
        f"CREATE INDEX IF NOT EXISTS {INDICE_ANTIGO} "
        f"ON {TABELA_FREQ} ({COLUNA})"
    ))


def upgrade() -> None:
    bind = op.get_bind()
    _criar_tabela(bind)
    try:
        # As guardas rodam DEPOIS da criação (ordem exigida) e antes de
        # qualquer escrita de dados. No SQLite o DDL pode ser auto-commitado;
        # dropar a tabela recém-criada garante o contrato "nada foi alterado"
        # também nesse dialeto. No PostgreSQL o rollback da transação faria o
        # mesmo.
        _checar_guardas(bind)
    except Exception:
        _dropar_tabela(bind)
        raise
    _backfill(bind)
    _verificar_conjuntos(bind)
    _dropar_coluna_antiga(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _dropar_tabela(bind)
    _recriar_coluna_antiga(bind)
