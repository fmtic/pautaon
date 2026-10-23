"""fix_onda2a: converte colunas VARCHAR para DATE/TIME/ENUM

Revision ID: 5a676f37b9a3
Revises: c4d5e6f7a8b9
Create Date: 2026-10-20

As migrations Onda 2A e 2B usaram batch_alter_table() que NÃO converte
tipos de coluna corretamente em PostgreSQL. Esta migration usa ALTER
TABLE ... ALTER COLUMN ... TYPE ... USING com SQL puro, que funciona.

IDEMPOTÊNCIA (Fase 0 — múltiplos cursos por turma):
    Bancos com drift (ex.: schema restaurado de dump em que as conversões
    DATE/TIME e os índices já existem, mas a revisão nunca foi stampada)
    falhariam ao reexecutar os ALTERs cegos. Cada conversão passou a ser
    condicionada ao tipo ATUAL da coluna (pg_attribute), preservando o
    comportamento em bancos ainda VARCHAR.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Identificadores desta revisão
revision: str = '5a676f37b9a3'
down_revision: str | None = 'c4d5e6f7a8b9'
branch_labels: str | None = None
depends_on: str | None = None


def _tipo_atual(tabela: str, coluna: str) -> str:
    """Tipo atual da coluna no PostgreSQL (via pg_attribute), em minúsculas."""
    row = op.get_bind().execute(
        sa.text(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = CAST(:tbl AS regclass) AND attname = :col"
        ),
        {"tbl": tabela, "col": coluna},
    ).scalar()
    return row or ""


def _alterar_tipo(tabela: str, coluna: str, alvo: str, sql: str) -> None:
    """Executa o ALTER apenas se a coluna ainda não tem o tipo alvo.

    `alvo` é o sufixo verificado no tipo atual: 'date', 'time' ou o nome
    do ENUM (ex.: 'conceito_frequencia_enum').
    """
    atual = _tipo_atual(tabela, coluna)
    if alvo in atual:
        return
    op.execute(sql)


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return

    # =========================================================================
    # TURMA - datas e horas (VARCHAR -> DATE/TIME)
    # =========================================================================
    _alterar_tipo(
        "turma", "data_inicio", "date",
        "ALTER TABLE turma ALTER COLUMN data_inicio TYPE DATE "
        "USING NULLIF(data_inicio, '')::date",
    )
    _alterar_tipo(
        "turma", "data_fim", "date",
        "ALTER TABLE turma ALTER COLUMN data_fim TYPE DATE "
        "USING NULLIF(data_fim, '')::date",
    )
    _alterar_tipo(
        "turma", "hora_inicio", "time",
        "ALTER TABLE turma ALTER COLUMN hora_inicio TYPE TIME "
        "USING NULLIF(hora_inicio, '')::time",
    )
    _alterar_tipo(
        "turma", "hora_fim", "time",
        "ALTER TABLE turma ALTER COLUMN hora_fim TYPE TIME "
        "USING NULLIF(hora_fim, '')::time",
    )

    # =========================================================================
    # TEMA_AULA - data (VARCHAR -> DATE)
    # =========================================================================
    _alterar_tipo(
        "tema_aula", "data", "date",
        "ALTER TABLE tema_aula ALTER COLUMN data TYPE DATE "
        "USING NULLIF(data, '')::date",
    )

    # =========================================================================
    # FREQUENCIA - data (VARCHAR -> DATE) e conceito (VARCHAR -> ENUM)
    # =========================================================================
    _alterar_tipo(
        "frequencia", "data", "date",
        "ALTER TABLE frequencia ALTER COLUMN data TYPE DATE "
        "USING NULLIF(data, '')::date",
    )
    _alterar_tipo(
        "frequencia", "conceito", "conceito_frequencia_enum",
        "ALTER TABLE frequencia ALTER COLUMN conceito "
        "TYPE conceito_frequencia_enum USING conceito::conceito_frequencia_enum",
    )

    # =========================================================================
    # REGISTRO_AULA - data (VARCHAR -> DATE)
    # =========================================================================
    _alterar_tipo(
        "registro_aula", "data", "date",
        "ALTER TABLE registro_aula ALTER COLUMN data TYPE DATE "
        "USING NULLIF(data, '')::date",
    )

    # =========================================================================
    # DIA_BLOQUEADO_TURMA - data (VARCHAR -> DATE)
    # =========================================================================
    _alterar_tipo(
        "dia_bloqueado_turma", "data", "date",
        "ALTER TABLE dia_bloqueado_turma ALTER COLUMN data TYPE DATE "
        "USING NULLIF(data, '')::date",
    )

    # =========================================================================
    # DIA_BLOQUEADO - tipo (VARCHAR -> ENUM)
    # =========================================================================
    _alterar_tipo(
        "dia_bloqueado", "tipo", "tipo_dia_bloqueado_enum",
        "ALTER TABLE dia_bloqueado ALTER COLUMN tipo "
        "TYPE tipo_dia_bloqueado_enum USING tipo::tipo_dia_bloqueado_enum",
    )

    # =========================================================================
    # CONSELHO_CLASSE - etapa (VARCHAR -> ENUM)
    # =========================================================================
    _alterar_tipo(
        "conselho_classe", "etapa", "etapa_conselho_enum",
        "ALTER TABLE conselho_classe ALTER COLUMN etapa "
        "TYPE etapa_conselho_enum USING etapa::etapa_conselho_enum",
    )

    # =========================================================================
    # CONSELHO_PERGUNTA - etapa e tipo (VARCHAR -> ENUM)
    # =========================================================================
    _alterar_tipo(
        "conselho_pergunta", "etapa", "etapa_conselho_enum",
        "ALTER TABLE conselho_pergunta ALTER COLUMN etapa "
        "TYPE etapa_conselho_enum USING NULLIF(etapa, '')::etapa_conselho_enum",
    )
    _alterar_tipo(
        "conselho_pergunta", "tipo", "tipo_pergunta_enum",
        "ALTER TABLE conselho_pergunta ALTER COLUMN tipo "
        "TYPE tipo_pergunta_enum USING NULLIF(tipo, '')::tipo_pergunta_enum",
    )

    # =========================================================================
    # Índices e constraints que faltam
    # =========================================================================
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_frequencia_turma_data "
        "ON frequencia (turma_id, data)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_frequencia_aluno_data "
        "ON frequencia (aluno_id, data)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_frequencia_aluno_turma_data "
        "ON frequencia (aluno_id, turma_id, data)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_conselho_turma_aluno_etapa "
        "ON conselho_classe (turma_id, aluno_id, etapa)"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return

    # Reverte ENUM -> VARCHAR
    op.execute(
        "ALTER TABLE conselho_pergunta ALTER COLUMN tipo TYPE VARCHAR(20) "
        "USING tipo::text"
    )
    op.execute(
        "ALTER TABLE conselho_pergunta ALTER COLUMN etapa TYPE VARCHAR(20) "
        "USING etapa::text"
    )
    op.execute(
        "ALTER TABLE conselho_classe ALTER COLUMN etapa TYPE VARCHAR(20) "
        "USING etapa::text"
    )
    op.execute(
        "ALTER TABLE dia_bloqueado ALTER COLUMN tipo TYPE VARCHAR(50) "
        "USING tipo::text"
    )
    op.execute(
        "ALTER TABLE frequencia ALTER COLUMN conceito TYPE VARCHAR(1) "
        "USING conceito::text"
    )

    # Reverte DATE/TIME -> VARCHAR
    op.execute(
        "ALTER TABLE dia_bloqueado_turma ALTER COLUMN data TYPE VARCHAR(10) "
        "USING data::text"
    )
    op.execute(
        "ALTER TABLE registro_aula ALTER COLUMN data TYPE VARCHAR(20) "
        "USING data::text"
    )
    op.execute(
        "ALTER TABLE frequencia ALTER COLUMN data TYPE VARCHAR(20) "
        "USING data::text"
    )
    op.execute(
        "ALTER TABLE tema_aula ALTER COLUMN data TYPE VARCHAR(20) "
        "USING data::text"
    )
    op.execute(
        "ALTER TABLE turma ALTER COLUMN hora_fim TYPE VARCHAR(5) "
        "USING hora_fim::text"
    )
    op.execute(
        "ALTER TABLE turma ALTER COLUMN hora_inicio TYPE VARCHAR(5) "
        "USING hora_inicio::text"
    )
    op.execute(
        "ALTER TABLE turma ALTER COLUMN data_fim TYPE VARCHAR(10) "
        "USING data_fim::text"
    )
    op.execute(
        "ALTER TABLE turma ALTER COLUMN data_inicio TYPE VARCHAR(10) "
        "USING data_inicio::text"
    )

    # Remove índices criados
    op.execute("DROP INDEX IF EXISTS uix_conselho_turma_aluno_etapa")
    op.execute("DROP INDEX IF EXISTS uix_frequencia_aluno_turma_data")
    op.execute("DROP INDEX IF EXISTS ix_frequencia_aluno_data")
    op.execute("DROP INDEX IF EXISTS ix_frequencia_turma_data")
