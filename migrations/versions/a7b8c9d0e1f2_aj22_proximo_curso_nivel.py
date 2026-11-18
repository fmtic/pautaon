"""AJ22 — Próximo curso + nível no fechamento do conselho.

Revision ID: a7b8c9d0e1f2
Revises: 1fdc7c03bdc2
Create Date: 2026-11-17

Contexto (AJ22-C): o "próximo curso" do fechamento é um CURSO já cadastrado
(`curso`) e cada CURSO tem sua própria nomenclatura de níveis. A opção
`opcao_proxima_turma` permanece LEGADA (tabela e coluna preservadas, sem
novas escritas e sem UI). Esta revisão é ADITIVA, não faz backfill e cria
apenas:

    1. `nivel.curso_id` INTEGER NULL FK → `curso.id` ON DELETE RESTRICT —
       NULL = nível sem curso (legado), que NUNCA aparece como opção no
       fechamento.
    2. `conselho_classe.proximo_curso_id` INTEGER NULL FK → `curso.id`
       ON DELETE RESTRICT — NULL = "Não se aplica".
    3. `conselho_classe.proximo_nivel_id` INTEGER NULL FK → `nivel.id`
       ON DELETE RESTRICT — NULL = "Não se aplica".
    4. Unicidade do nível: `uq_nivel_nome_unidade` (nome, unidade_id) é
       substituída pelo índice funcional `uq_nivel_nome_unidade_curso`
       (nome, unidade_id, COALESCE(curso_id, 0)) — o mesmo nome pode
       repetir entre cursos; níveis legados sem curso mantêm a unicidade
       de antes.

Não existem mais `curso.programa` nem `nivel.programa` (o AJ22-B foi
substituído antes do deploy): o vínculo do nível é diretamente com o curso.

Portabilidade e idempotência: cada passo é precedido de inspeção do bind
(`_colunas`, `_tem_constraint`, `_tem_indice`) — rodar duas vezes não
falha nem duplica. O DDL vai por `bind.execute(text(...))` para ser
exercitável nos testes SQLite; no PostgreSQL (produção) emite os mesmos
comandos.

Particularidades por dialeto:
- SQLite não aceita `ALTER TABLE ... ADD CONSTRAINT` nem
  `DROP CONSTRAINT` de UNIQUE de tabela: as FKs de `nivel.curso_id`,
  `proximo_curso_id` e `proximo_nivel_id` são puladas no SQLite (o schema
  dos testes nasce de `db.create_all`, que já cria as FKs) e a troca da
  unicidade do nível é feita reconstruindo a tabela `nivel` com
  `PRAGMA foreign_keys=OFF` + `legacy_alter_table=ON` (as FKs das outras
  tabelas referenciam `nivel` pelo nome e continuam válidas após o
  rename+recreate).
- PostgreSQL recebe `ALTER TABLE ... ADD/DROP CONSTRAINT` e
  `CREATE/DROP INDEX` diretos.

Downgrade: remove as FKs/colunas de destino, `nivel.curso_id` e o índice
funcional, recriando `uq_nivel_nome_unidade`. GUARDA (D8): recusa o
downgrade se existir duplicata de (nome, unidade_id) — recriar a
constraint antiga fundiria ou falharia com níveis de cursos diferentes.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "1fdc7c03bdc2"
branch_labels: str | None = None
depends_on: str | None = None

T_NIVEL = "nivel"
T_CURSO = "curso"
T_CONSELHO = "conselho_classe"

COL_NIVEL_CURSO = "curso_id"
COL_CONSELHO_CURSO = "proximo_curso_id"
COL_CONSELHO_NIVEL = "proximo_nivel_id"

UNQ_ANTIGA = "uq_nivel_nome_unidade"
IDX_NOVA = "uq_nivel_nome_unidade_curso"
FK_CURSO = "fk_conselho_classe_proximo_curso"
FK_NIVEL = "fk_conselho_classe_proximo_nivel"
FK_NIVEL_CURSO = "fk_nivel_curso"


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


def _add_coluna(bind, tabela: str, coluna: str, tipo: str) -> None:
    if coluna not in _colunas(bind, tabela):
        bind.execute(sa.text(
            f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"
        ))


def _drop_coluna(bind, tabela: str, coluna: str) -> None:
    if coluna in _colunas(bind, tabela):
        bind.execute(sa.text(
            f"ALTER TABLE {tabela} DROP COLUMN {coluna}"
        ))


def _fks(bind, tabela: str) -> set[str]:
    if not sa.inspect(bind).has_table(tabela):
        return set()
    return {
        fk.get("name")
        for fk in sa.inspect(bind).get_foreign_keys(tabela)
    }


def _criar_fk(bind, tabela: str, coluna: str, alvo: str, nome: str) -> None:
    """FK `coluna` → `alvo.id` ON DELETE RESTRICT (se ausente).

    SQLite não aceita ADD CONSTRAINT via ALTER — lá a FK já nasce do
    `db.create_all` dos testes; em PostgreSQL o ALTER é emitido.
    """
    if not sa.inspect(bind).has_table(tabela):
        return
    if not _eh_postgres(bind):
        return
    if nome in _fks(bind, tabela):
        return
    bind.execute(sa.text(
        f"ALTER TABLE {tabela} ADD CONSTRAINT {nome} "
        f"FOREIGN KEY ({coluna}) REFERENCES {alvo}(id) "
        "ON DELETE RESTRICT"
    ))


def _drop_fk(bind, tabela: str, nome: str) -> None:
    if not _eh_postgres(bind):
        return
    if not sa.inspect(bind).has_table(tabela):
        return
    if nome in _fks(bind, tabela):
        bind.execute(sa.text(
            f"ALTER TABLE {tabela} DROP CONSTRAINT {nome}"
        ))


def _colunas_nivel(bind) -> list[dict]:
    return sa.inspect(bind).get_columns(T_NIVEL)


def _recriar_nivel_sqlite(bind, *, unica_antiga: bool) -> None:
    """Reconstrói `nivel` no SQLite (única forma de trocar a unicidade de
    tabela). Preserva exatamente as colunas presentes no momento — o
    caller decide se `curso_id` já foi removida (downgrade) ou não
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
                "(nome, unidade_id, COALESCE(curso_id, 0))"
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
            "(nome, unidade_id, COALESCE(curso_id, 0))"
        ))
    else:
        if tem_idx:
            bind.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_NOVA}"))
        if tem_unq:
            # Constraint antiga já presente (banco legado pré-AJ22).
            return
        _recriar_nivel_sqlite(bind, unica_antiga=True)


def _guarda_downgrade(bind) -> None:
    """D8: recusa restaurar (nome, unidade_id) único se houver duplicata
    entre cursos diferentes (ou curso × legado NULL)."""
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
            f"mesmo nome na mesma unidade em cursos diferentes: {amostra}. "
            "Restaurar uq_nivel_nome_unidade fundiria ou falharia. "
            "Renomeie os níveis duplicados antes de reverter. "
            "Nada foi alterado."
        )


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Curso do nível (idempotente por inspeção) + FK.
    _add_coluna(bind, T_NIVEL, COL_NIVEL_CURSO, "INTEGER")
    _criar_fk(bind, T_NIVEL, COL_NIVEL_CURSO, T_CURSO, FK_NIVEL_CURSO)

    # 2-3. Colunas + FKs de destino no conselho (curso e nível).
    _add_coluna(bind, T_CONSELHO, COL_CONSELHO_CURSO, "INTEGER")
    _add_coluna(bind, T_CONSELHO, COL_CONSELHO_NIVEL, "INTEGER")
    _criar_fk(bind, T_CONSELHO, COL_CONSELHO_CURSO, T_CURSO, FK_CURSO)
    _criar_fk(bind, T_CONSELHO, COL_CONSELHO_NIVEL, T_NIVEL, FK_NIVEL)

    # 4. Unicidade funcional do nível.
    _trocar_unicidade_nivel(bind, "upgrade")


def downgrade() -> None:
    bind = op.get_bind()

    _guarda_downgrade(bind)

    # Remove primeiro o que depende das colunas, depois as colunas.
    _drop_fk(bind, T_CONSELHO, FK_CURSO)
    _drop_fk(bind, T_CONSELHO, FK_NIVEL)
    _drop_coluna(bind, T_CONSELHO, COL_CONSELHO_CURSO)
    _drop_coluna(bind, T_CONSELHO, COL_CONSELHO_NIVEL)

    # O índice funcional referencia nivel.curso_id: some antes da coluna.
    if _eh_postgres(bind):
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_NOVA}"))
    else:
        if _tem_indice(bind, T_NIVEL, IDX_NOVA):
            bind.execute(sa.text(f"DROP INDEX IF EXISTS {IDX_NOVA}"))
    _trocar_unicidade_nivel(bind, "downgrade")
    _drop_fk(bind, T_NIVEL, FK_NIVEL_CURSO)
    _drop_coluna(bind, T_NIVEL, COL_NIVEL_CURSO)
