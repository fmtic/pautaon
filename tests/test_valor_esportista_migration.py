"""AJ16-B — migration do valor do esportista: da frequência para a AULA.

As funções de DDL/checagem são exercitadas diretamente contra o bind SQLite
(mesmo padrão de `test_h5b_migrations.py`), sem depender de contexto Alembic.
O SQL compilado no dialeto PostgreSQL é conferido com `create_mock_engine`.

O schema "pré-AJ16-B" é montado à mão: `frequencia` COM
`valor_esportista_id` (sem FK declarada, para o SQLite permitir `DROP COLUMN`),
`registro_aula` e `valor_esportista`. É fiel ao banco que a migration encontra
— inclusive porque o head anterior (`c1d2e3f4a5b6`) já tem `registro_aula` e a
coluna antiga.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import (
    Column,
    Date,
    Integer,
    MetaData,
    String,
    Table,
    create_mock_engine,
    inspect,
    text,
)

from app import create_app, db
from config import Config

RAIZ = Path(__file__).resolve().parents[1]


def _carregar(nome: str, arquivo: str):
    espec = importlib.util.spec_from_file_location(
        nome, RAIZ / "migrations" / "versions" / arquivo
    )
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


mig = _carregar(
    "mig_valor_aula", "f2a3b4c5d6e7_valor_esportista_na_aula.py"
)

DATA = date(2026, 11, 3)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        yield test_app
        db.session.remove()
        db.drop_all()


def _schema_pre_aj16b(bind):
    metadata = MetaData()
    Table(
        "valor_esportista", metadata,
        Column("id", Integer(), primary_key=True),
        Column("nome", String(100), nullable=False),
        Column("ativo", Integer(), nullable=False, default=1),
        Column("unidade_id", Integer(), nullable=True),
    ).create(bind)
    Table(
        "registro_aula", metadata,
        Column("id", Integer(), primary_key=True),
        Column("turma_id", Integer(), nullable=False),
        Column("turma_curso_id", Integer(), nullable=True),
        Column("data", Date(), nullable=False),
    ).create(bind)
    # A coluna antiga sem FK: o SQLite não dropa coluna que aparece numa FK.
    Table(
        "frequencia", metadata,
        Column("id", Integer(), primary_key=True),
        Column("aluno_id", Integer(), nullable=False),
        Column("turma_id", Integer(), nullable=False),
        Column("turma_curso_id", Integer(), nullable=True),
        Column("data", Date(), nullable=False),
        Column("conceito", String(1), nullable=True),
        Column("unidade_id", Integer(), nullable=True),
        Column(mig.COLUNA, Integer(), nullable=True),
    ).create(bind)


def _tabelas():
    return set(inspect(db.session.connection()).get_table_names())


def _colunas(tabela):
    return {
        c["name"] for c in inspect(db.session.connection()).get_columns(tabela)
    }


def _inserir_valor(nome):
    return db.session.execute(
        text(
            "INSERT INTO valor_esportista (nome, ativo, unidade_id) "
            "VALUES (:n, 1, 1) RETURNING id"
        ),
        {"n": nome},
    ).scalar()


def _inserir_registro(turma_curso_id, data=DATA, turma_id=1):
    return db.session.execute(
        text(
            "INSERT INTO registro_aula (turma_id, turma_curso_id, data) "
            "VALUES (:t, :tc, :d) RETURNING id"
        ),
        {"t": turma_id, "tc": turma_curso_id, "d": data.isoformat()},
    ).scalar()


def _inserir_frequencia(
    *, aluno_id, valor_id, turma_curso_id=1, data=DATA, conceito="A",
):
    db.session.execute(
        text(
            "INSERT INTO frequencia "
            "(aluno_id, turma_id, turma_curso_id, data, conceito, unidade_id, "
            f"{mig.COLUNA}) "
            "VALUES (:a, 1, :tc, :d, :c, 1, :v)"
        ),
        {
            "a": aluno_id, "tc": turma_curso_id, "d": data.isoformat(),
            "c": conceito, "v": valor_id,
        },
    )


def _aplicar_upgrade(*, backfill_duas_vezes=False):
    bind = db.session.connection()
    try:
        mig._criar_tabela(bind)
        mig._checar_guardas(bind)
        mig._backfill(bind)
        if backfill_duas_vezes:
            mig._backfill(bind)
        mig._verificar_conjuntos(bind)
        mig._dropar_coluna_antiga(bind)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _aplicar_downgrade():
    bind = db.session.connection()
    mig._dropar_tabela(bind)
    mig._recriar_coluna_antiga(bind)
    db.session.commit()


def _vinculos():
    return db.session.execute(
        text(
            f"SELECT registro_aula_id, valor_esportista_id "
            f"FROM {mig.TABELA} ORDER BY 1, 2"
        )
    ).all()


def _valores_antigos():
    return db.session.execute(
        text(
            f"SELECT aluno_id, {mig.COLUNA} FROM frequencia ORDER BY aluno_id"
        )
    ).all()


def _preparar_pares(quantidade_valores, *, duplicar_aluno=False):
    """`quantidade_valores` valores distintos na MESMA oferta+data."""
    registro_id = _inserir_registro(1)
    for indice in range(1, quantidade_valores + 1):
        _inserir_frequencia(aluno_id=indice, valor_id=indice)
    if duplicar_aluno:
        # Mesmo valor repetido em outro aluno da mesma aula: um único vínculo.
        _inserir_frequencia(aluno_id=99, valor_id=1)
    return registro_id


# ---------------------------------------------------------------------------
# Upgrade com dados
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quantidade", [3, 7])
def test_upgrade_move_n_valores_para_a_aula(app, quantidade):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        for indice in range(1, quantidade + 1):
            _inserir_valor(f"Valor {indice}")
        registro_id = _preparar_pares(quantidade)
        db.session.commit()

        _aplicar_upgrade()

        assert mig.TABELA in _tabelas()
        assert mig.COLUNA not in _colunas(mig.TABELA_FREQ)
        assert _vinculos() == [
            (registro_id, indice) for indice in range(1, quantidade + 1)
        ]
        # Conceitos e linhas de frequência intactos.
        assert db.session.execute(
            text("SELECT COUNT(*) FROM frequencia")
        ).scalar() == quantidade


def test_upgrade_deduplica_valores_do_mesmo_par(app):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        for indice in range(1, 4):
            _inserir_valor(f"Valor {indice}")
        registro_id = _preparar_pares(3, duplicar_aluno=True)
        db.session.commit()

        _aplicar_upgrade()

        assert _vinculos() == [
            (registro_id, 1),
            (registro_id, 2),
            (registro_id, 3),
        ]


def test_backfill_escolhe_o_diario_canonico_min_id(app):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        _inserir_valor("Alegria")
        _inserir_valor("Foco")
        canonico = _inserir_registro(1)
        duplicado = _inserir_registro(1)
        _inserir_frequencia(aluno_id=1, valor_id=1)
        _inserir_frequencia(aluno_id=2, valor_id=2)
        db.session.commit()

        _aplicar_upgrade()

        assert _vinculos() == [(canonico, 1), (canonico, 2)]
        assert duplicado != canonico


def test_backfill_e_idempotente(app):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        _inserir_valor("Alegria")
        _inserir_valor("Foco")
        _preparar_pares(2, duplicar_aluno=True)
        db.session.commit()

        _aplicar_upgrade(backfill_duas_vezes=True)

        assert len(_vinculos()) == 2


def test_verificacao_interna_aborta_quando_conjuntos_divergem(app):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        _inserir_valor("Alegria")
        _inserir_valor("Foco")
        registro_id = _inserir_registro(1)
        _inserir_frequencia(aluno_id=1, valor_id=1)
        db.session.commit()

        bind = db.session.connection()
        mig._criar_tabela(bind)
        mig._checar_guardas(bind)
        mig._backfill(bind)
        # Força um vínculo que não existe no conjunto antigo.
        db.session.execute(
            text(
                f"INSERT INTO {mig.TABELA} "
                "(registro_aula_id, valor_esportista_id) VALUES (:r, 2)"
            ),
            {"r": registro_id},
        )
        db.session.flush()

        # Commit fecharia a connection capturada; a verificação lê o mesmo bind.
        with pytest.raises(RuntimeError, match="verificação interna"):
            mig._verificar_conjuntos(bind)
        db.session.rollback()


# ---------------------------------------------------------------------------
# Guardas: abortam antes de qualquer escrita
# ---------------------------------------------------------------------------

def test_guarda_aborta_com_valor_sem_oferta_e_nada_muda(app, monkeypatch):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        _inserir_valor("Alegria")
        _inserir_frequencia(aluno_id=1, valor_id=1, turma_curso_id=None)
        db.session.commit()

        monkeypatch.setattr(
            mig.op, "get_bind", lambda: db.session.connection(),
        )
        with pytest.raises(RuntimeError, match="turma_curso_id NULL"):
            mig.upgrade()
        db.session.rollback()

        assert mig.COLUNA in _colunas(mig.TABELA_FREQ)
        assert _valores_antigos() == [(1, 1)]
        assert mig.TABELA not in _tabelas()


def test_guarda_aborta_sem_registro_aula_e_nada_muda(app, monkeypatch):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        _inserir_valor("Alegria")
        _inserir_frequencia(aluno_id=1, valor_id=1, turma_curso_id=1)
        db.session.commit()

        monkeypatch.setattr(
            mig.op, "get_bind", lambda: db.session.connection(),
        )
        with pytest.raises(RuntimeError, match="sem registro_aula"):
            mig.upgrade()
        db.session.rollback()

        assert mig.COLUNA in _colunas(mig.TABELA_FREQ)
        assert _valores_antigos() == [(1, 1)]
        assert mig.TABELA not in _tabelas()


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def test_downgrade_recria_coluna_vazia_e_remove_a_tabela(app):
    with app.app_context():
        _schema_pre_aj16b(db.session.connection())
        for indice in range(1, 4):
            _inserir_valor(f"Valor {indice}")
        _preparar_pares(3)
        db.session.commit()

        _aplicar_upgrade()
        assert len(_vinculos()) == 3

        _aplicar_downgrade()

        assert mig.TABELA not in _tabelas()
        assert mig.COLUNA in _colunas(mig.TABELA_FREQ)
        # O vínculo aluno↔valor NÃO é restaurado (o dado antigo era por aluno).
        assert all(valor is None for _aluno, valor in _valores_antigos())
        assert db.session.execute(
            text("SELECT COUNT(*) FROM frequencia")
        ).scalar() == 3


def test_docstring_avisa_que_downgrade_nao_restaura_vinculo():
    assert "NÃO restaura" in (mig.__doc__ or "")


# ---------------------------------------------------------------------------
# DDL compilada para PostgreSQL
# ---------------------------------------------------------------------------

def _sql_postgres(funcao, *args):
    comandos = []
    engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda stmt, *a, **k: comandos.append(
            str(stmt.compile(dialect=engine.dialect))
        ),
    )
    funcao(engine, *args)
    return " ".join("\n".join(comandos).split())


def test_ddl_postgres_cria_tabela_com_pk_fks_e_indice():
    sql = _sql_postgres(mig._criar_tabela)

    assert "CREATE TABLE registro_aula_valor_esportista" in sql
    assert "PRIMARY KEY (registro_aula_id, valor_esportista_id)" in sql
    assert (
        "CONSTRAINT fk_registro_aula_valor_esportista_registro "
        "FOREIGN KEY(registro_aula_id) REFERENCES registro_aula (id) "
        "ON DELETE CASCADE"
    ) in sql
    assert (
        "CONSTRAINT fk_registro_aula_valor_esportista_valor "
        "FOREIGN KEY(valor_esportista_id) REFERENCES valor_esportista (id) "
        "ON DELETE RESTRICT"
    ) in sql
    assert (
        "CREATE INDEX ix_registro_aula_valor_esportista_valor "
        "ON registro_aula_valor_esportista (valor_esportista_id)"
    ) in sql


def test_ddl_postgres_dropa_indice_fk_e_coluna_antiga():
    sql = _sql_postgres(mig._dropar_coluna_antiga)

    assert "DROP INDEX IF EXISTS ix_frequencia_valor_esportista" in sql
    assert (
        "ALTER TABLE frequencia DROP CONSTRAINT IF EXISTS "
        "fk_frequencia_valor_esportista"
    ) in sql
    assert (
        "ALTER TABLE frequencia DROP COLUMN IF EXISTS valor_esportista_id"
    ) in sql


def test_ddl_postgres_downgrade_recria_coluna_fk_e_indice():
    sql = _sql_postgres(mig._recriar_coluna_antiga)

    assert (
        "ALTER TABLE frequencia ADD COLUMN IF NOT EXISTS "
        "valor_esportista_id INTEGER"
    ) in sql
    assert (
        "ALTER TABLE frequencia ADD CONSTRAINT fk_frequencia_valor_esportista "
        "FOREIGN KEY (valor_esportista_id) REFERENCES valor_esportista(id) "
        "ON DELETE SET NULL"
    ) in sql
    assert (
        "CREATE INDEX IF NOT EXISTS ix_frequencia_valor_esportista "
        "ON frequencia (valor_esportista_id)"
    ) in sql


def test_ddl_postgres_downgrade_dropa_tabela_nova():
    sql = _sql_postgres(mig._dropar_tabela)

    assert (
        "DROP TABLE IF EXISTS registro_aula_valor_esportista"
    ) in sql
    assert (
        "DROP INDEX IF EXISTS ix_registro_aula_valor_esportista_valor"
    ) in sql
