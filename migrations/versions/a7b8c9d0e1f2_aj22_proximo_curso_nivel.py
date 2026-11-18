"""AJ22 — Próximo curso + nível no fechamento do conselho.

Revision ID: a7b8c9d0e1f2
Revises: 1fdc7c03bdc2
Create Date: 2026-11-17

Contexto: o fechamento do conselho passa a registrar, além da "Próxima
Turma" (catálogo `opcao_proxima_turma`), um NÍVEL de destino vinculado ao
programa da opção. Esta revisão é ADITIVA e não faz backfill:

    1. `opcao_proxima_turma.programa` VARCHAR(50) NULL — programa de curso
       ao qual a opção se refere (lista central de programas).
    2. `nivel.programa` VARCHAR(50) NULL — nível sem programa (legado,
       NULL) NUNCA aparece como opção no fechamento.
    3. `conselho_classe.proximo_nivel_id` INTEGER NULL FK → `nivel.id`
       ON DELETE RESTRICT — NULL = "Não se aplica".
    4. Unicidade do nível: `uq_nivel_nome_unidade` (nome, unidade_id) é
       substituída pelo índice funcional
       `uq_nivel_nome_unidade_programa` (nome, unidade_id,
       COALESCE(programa, '')) — o mesmo nome pode repetir entre
       programas; níveis legados sem programa mantêm a unicidade de antes.

Portabilidade e idempotência: cada passo é precedido de inspeção do bind
(`_colunas`, `_tem_constraint`, `_tem_indice`) — rodar duas vezes não
falha nem duplica. O DDL vai por `bind.execute(text(...))` para ser
exercitável nos testes SQLite; no PostgreSQL (produção) emite os mesmos
comandos.

Particularidades por dialeto:
- SQLite não aceita `ALTER TABLE ... ADD CONSTRAINT` nem
  `DROP CONSTRAINT` de UNIQUE de tabela: a FK de `proximo_nivel_id` é
  pulada no SQLite (o schema dos testes nasce de `db.create_all`, que já
  cria a FK) e a troca da unicidade do nível é feita reconstruindo a
  tabela `nivel` com `PRAGMA foreign_keys=OFF` + `legacy_alter_table=ON`
  (as FKs das outras tabelas referenciam `nivel` pelo nome e continuam
  válidas após o rename+recreate).
- PostgreSQL recebe `ALTER TABLE ... ADD/DROP CONSTRAINT` e
  `CREATE/DROP INDEX` diretos.

Downgrade: remove `conselho_classe.proximo_nivel_id` (coluna + FK),
`opcao_proxima_turma.programa`, `nivel.programa` e o índice funcional,
recriando `uq_nivel_nome_unidade`. GUARDA (D8): recusa o downgrade se
existir duplicata de (nome, unidade_id) — recriar a constraint antiga
fundiria ou falharia com níveis de programas diferentes.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "1fdc7c03bdc2"
branch_labels: str | None = None
depends_on: str | None = None

T_NIVEL = "nivel"
T_OPCAO = "opcao_proxima_turma"
T_CONSELHO = "conselho_classe"

COL_NIVEL = "programa"
COL_OPCAO = "programa"
COL_CONSELHO = "proximo_nivel_id"

UNQ_ANTIGA = "uq_nivel_nome_unidade"
IDX_NOVA = "uq_nivel_nome_unidade_programa"
FK_NOVA = "fk_conselho_classe_proximo_nivel"


def _eh_postgres(bind) -> bool:
    return bind.dialect.name == "postgresql"


def _colunas(bind, tabela: str) -> set[str]:
    insp = sa.inspect(bind)
    if not insp.has_table(tabela):
        return set()
    return {c["name"] for c in insp.get_columns(tabela)}


def _tem_constraint(bind, tabela: str, nome: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(tabela):
        return False
    return nome in {
        c["name"] for c in insp.get_unique_constraints(tabela)
    } or nome in {
        fk["name"] for fk in insp.get_foreign_keys(tabela)
    }


def _tem_indice(bind, tabela: str, nome: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(tabela):
        return False
    return nome in {i["name"] for i in insp.get_indexes(tabela)}


def _add_coluna(bind, tabela: str, coluna: str) -> None:
    if coluna not in _colunas(bind, tabela):
        bind.execute(sa.text(
            f"ALTER TABLE {tabela} ADD COLUMN {coluna} VARCHAR(50)"
        ))


def _drop_coluna(bind, tabela: str, coluna: str) -> None:
    if coluna in _colunas(bind, tabela):
        bind.execute(sa.text(
            f"ALTER TABLE {tabela} DROP COLUMN {coluna}"
        ))


def _criar_fk_nivel(bind) -> None:
    """FK proximo_nivel_id → nivel.id ON DELETE RESTRICT (se ausente).

    SQLite não aceita ADD CONSTRAINT via ALTER — lá a FK já nasce do
    `db.create_all` dos testes; em PostgreSQL o ALTER é emitido.
    """
    if not sa.inspect(bind).has_table(T_CONSELHO):
        return
    if not _eh_postgres(bind):
        return
    fks = {
        fk.get("name")
        for fk in sa.inspect(bind).get_foreign_keys(T_CONSELHO)
    }
    if FK_NOVA in fks:
        return
    bind.execute(sa.text(
        f"ALTER TABLE {T_CONSELHO} ADD CONSTRAINT {FK_NOVA} "
        f"FOREIGN KEY ({COL_CONSELHO}) REFERENCES {T_NIVEL}(id) "
        "ON DELETE RESTRICT"
    ))


def _drop_fk_nivel(bind) -> None:
    if not _eh_postgres(bind):
        return
    if not sa.inspect(bind).has_table(T_CONSELHO):
        return
    fks = {
        fk.get("name")
        for fk in sa.inspect(bind).get_foreign_keys(T_CONSELHO)
    }
    if FK_NOVA in fks:
        bind.execute(sa.text(
            f"ALTER TABLE {T_CONSELHO} DROP CONSTRAINT {FK_NOVA}"
        ))


def _colunas_nivel(bind) -> list[dict]:
    return sa.inspect(bind).get_columns(T_NIVEL)


def _recriar_nivel_sqlite(bind, *, unica_antiga: bool) -> None:
    """Reconstrói `nivel` no SQLite (única forma de trocar a unicidade de
    tabela). Preserva exatamente as colunas presentes no momento — o
    caller decide se `programa` já foi removida (downgrade) ou não
    (upgrade)."""
    cols = _colunas_nivel(bind)
    nomes = [c["name"] for c in cols]
    create_cols = []
    for c in cols:
        tipo = str(c["type"])
        if c["name"] == "id":
            create_cols.append('"id" INTEGER PRIMARY KEY')
            continue
        nulo = "NULL" if c.get("nullable", True) else "NOT NULL"
        default = " DEFAULT 1" if c["name"] == "ativo" else ""
        create_cols.append(f'"{c["name"]}" {tipo} {nulo}{default}')
    if unica_antiga:
        create_cols.append(
            f'CONSTRAINT {UNQ_ANTIGA} UNIQUE ("nome", "unidade_id")'
        )
    col_list = ", ".join(f'"{n}"' for n in nomes)

    bind.execute(sa.text("PRAGMA foreign_keys=OFF"))
    bind.execute(sa.text("PRAGMA legacy_alter_table=ON"))
    try:
        bind.execute(sa.text("ALTER TABLE nivel RENAME TO nivel__aj22_old"))
        bind.execute(sa.text(
            "CREATE TABLE nivel (" + ", ".join(create_cols) + ")"
        ))
        bind.execute(sa.text(
            f"INSERT INTO nivel ({col_list}) "
            f"SELECT {col_list} FROM nivel__aj22_old"
        ))
        bind.execute(sa.text("DROP TABLE nivel__aj22_old"))
    finally:
        bind.execute(sa.text("PRAGMA legacy_alter_table=OFF"))
        bind.execute(sa.text("PRAGMA foreign_keys=ON"))


def _trocar_unicidade_nivel(bind, direcao: str) -> None:
    """'upgrade': unique constraint → índice funcional.
    'downgrade': índice funcional → unique constraint."""
    if not sa.inspect(bind).has_table(T_NIVEL):
        return

    tem_unq = _tem_constraint(bind, T_NIVEL, UNQ_ANTIGA)
    tem_idx = _tem_indice(bind, T_NIVEL, IDX_NOVA)

    if _eh_postgres(bind):
        if direcao == "upgrade":
            if tem_unq:
                bind.execute(sa.text(
                    f"ALTER TABLE {T_NIVEL} DROP CONSTRAINT {UNQ_ANTIGA}"
                ))
            # IF NOT EXISTS: inspetores podem não refletir índice de
            # expressão — a idempotência não pode depender disso.
            bind.execute(sa.text(
                f"CREATE UNIQUE INDEX IF NOT EXISTS {IDX_NOVA} ON {T_NIVEL} "
                "(nome, unidade_id, COALESCE(programa, ''))"
            ))
        else:
            bind.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_NOVA}"))
            if not tem_unq:
                bind.execute(sa.text(
                    f"ALTER TABLE {T_NIVEL} ADD CONSTRAINT {UNQ_ANTIGA} "
                    "UNIQUE (nome, unidade_id)"
                ))
        return

    # SQLite: a constraint de tabela não pode ser dropada via ALTER —
    # a tabela é reconstruída com a unicidade desejada e o índice
    # funcional (quando upgrade) é criado em seguida.
    if direcao == "upgrade":
        if tem_unq or not tem_idx:
            _recriar_nivel_sqlite(bind, unica_antiga=False)
        bind.execute(sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {IDX_NOVA} ON {T_NIVEL} "
            "(nome, unidade_id, COALESCE(programa, ''))"
        ))
    else:
        if tem_idx or not tem_unq:
            _recriar_nivel_sqlite(bind, unica_antiga=True)


def _guarda_downgrade(bind) -> None:
    """D8: recusa restaurar (nome, unidade_id) único se houver duplicata
    entre programas diferentes (ou programa × legado NULL)."""
    duplicatas = bind.execute(sa.text(
        "SELECT nome, unidade_id, COUNT(*) AS qtd FROM nivel "
        "GROUP BY nome, unidade_id HAVING COUNT(*) > 1"
    )).fetchall()
    if duplicatas:
        amostra = ", ".join(
            f"('{n}', unidade {u})" for n, u, _ in duplicatas[:5]
        )
        raise RuntimeError(
            "Downgrade de a7b8c9d0e1f2 (AJ22) recusado: há nível(s) com o "
            f"mesmo nome na mesma unidade em programas diferentes: {amostra}. "
            "Restaurar uq_nivel_nome_unidade fundiria ou falharia. "
            "Renomeie os níveis duplicados antes de reverter. "
            "Nada foi alterado."
        )


def upgrade() -> None:
    bind = op.get_bind()

    # 1-2. Colunas de programa (idempotente por inspeção).
    _add_coluna(bind, T_OPCAO, COL_OPCAO)
    _add_coluna(bind, T_NIVEL, COL_NIVEL)

    # 3. Coluna + FK do nível de destino no conselho.
    if COL_CONSELHO not in _colunas(bind, T_CONSELHO):
        bind.execute(sa.text(
            f"ALTER TABLE {T_CONSELHO} ADD COLUMN {COL_CONSELHO} INTEGER"
        ))
    _criar_fk_nivel(bind)

    # 4. Unicidade funcional do nível.
    _trocar_unicidade_nivel(bind, "upgrade")


def downgrade() -> None:
    bind = op.get_bind()

    _guarda_downgrade(bind)

    _drop_fk_nivel(bind)
    _drop_coluna(bind, T_CONSELHO, COL_CONSELHO)
    _drop_coluna(bind, T_OPCAO, COL_OPCAO)
    _drop_coluna(bind, T_NIVEL, COL_NIVEL)
    _trocar_unicidade_nivel(bind, "downgrade")
