"""A1 — migration do Valor do Esportista: upgrade e downgrade com dados.

As funções de DDL são exercitadas diretamente contra o bind SQLite (mesmo
padrão de `test_h5b_migrations.py`), sem depender de contexto Alembic.

O schema "pré-A1" é montado à mão — apenas `unidade` + `frequencia` sem a
coluna nova. Não dá para partir de `db.create_all()` e dropar a coluna: o
SQLite recusa `ALTER TABLE ... DROP COLUMN` quando a coluna aparece na
definição de uma FK (a do modelo), embora aceite a mesma coluna criada por
`ADD COLUMN`. Montar o estado anterior evita esse atrito e é fiel ao banco
que a migration vai encontrar.
"""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
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
from app.models import Unidade
from app.utils.logica import get_local_now
from config import Config

RAIZ = Path(__file__).resolve().parents[1]


def _carregar(nome: str, arquivo: str):
    espec = importlib.util.spec_from_file_location(
        nome, RAIZ / "migrations" / "versions" / arquivo
    )
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


mig = _carregar("mig_valor_esportista", "b7c8d9e0f1a2_valor_esportista.py")


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


def _schema_pre_a1(bind):
    """Estado anterior à feature: `unidade` + `frequencia` sem a coluna nova."""
    Unidade.__table__.create(bind)
    Table(
        mig.TABELA_FREQUENCIA,
        MetaData(),
        Column("id", Integer(), primary_key=True),
        Column("aluno_id", Integer(), nullable=False),
        Column("turma_id", Integer(), nullable=False),
        Column("turma_curso_id", Integer(), nullable=True),
        Column("data", Date(), nullable=False),
        Column("conceito", String(length=1), nullable=True),
        Column("unidade_id", Integer(), nullable=True),
    ).create(bind)


def _seed(unidade_id):
    """Dois registros de frequência anteriores à feature (A e F)."""
    hoje = get_local_now().date()
    for indice, conceito in enumerate(("A", "F")):
        db.session.execute(
            text(
                "INSERT INTO frequencia "
                "(aluno_id, turma_id, data, conceito, unidade_id) "
                "VALUES (1, 1, :d, :c, :u)"
            ),
            {
                "d": (hoje - timedelta(days=indice)).isoformat(),
                "c": conceito,
                "u": unidade_id,
            },
        )
    db.session.commit()


def _colunas(tabela):
    return {
        c["name"] for c in inspect(db.session.connection()).get_columns(tabela)
    }


def _tabelas():
    return set(inspect(db.session.connection()).get_table_names())


def _conceitos():
    return db.session.execute(
        text("SELECT conceito FROM frequencia ORDER BY data DESC")
    ).scalars().all()


def _aplicar_upgrade():
    bind = db.session.connection()
    mig._criar_tabela(bind)
    mig._adicionar_coluna_frequencia(bind)
    db.session.commit()


def _aplicar_downgrade():
    bind = db.session.connection()
    mig._dropar_coluna_frequencia(bind)
    mig._dropar_tabela(bind)
    db.session.commit()


def _inserir_valor(nome, unidade_id):
    db.session.execute(
        text(
            f"INSERT INTO {mig.TABELA} (nome, ativo, unidade_id) "
            "VALUES (:n, 1, :u)"
        ),
        {"n": nome, "u": unidade_id},
    )
    db.session.commit()
    return db.session.execute(
        text(f"SELECT id FROM {mig.TABELA} WHERE nome = :n"), {"n": nome}
    ).scalar()


def _valor_da_linha(conceito):
    return db.session.execute(
        text(
            f"SELECT {mig.COLUNA} FROM frequencia WHERE conceito = :c"
        ),
        {"c": conceito},
    ).scalar()


def test_upgrade_cria_tabela_e_coluna_sem_perder_dados(app):
    with app.app_context():
        bind = db.session.connection()
        _schema_pre_a1(bind)
        unidade_id = db.session.execute(
            text(
                "INSERT INTO unidade (nome, ativo) VALUES ('U A1V-MIG', 1) "
                "RETURNING id"
            )
        ).scalar()
        db.session.commit()
        _seed(unidade_id)

        _aplicar_upgrade()

        assert mig.TABELA in _tabelas()
        assert mig.COLUNA in _colunas(mig.TABELA_FREQUENCIA)
        assert _conceitos() == ["A", "F"]  # nenhuma linha perdida
        # Sem backfill: a coluna nasce NULL em todas as linhas antigas.
        assert _valor_da_linha("A") is None
        assert _valor_da_linha("F") is None


def test_upgrade_aplica_unicidade_por_unidade_sem_distinguir_case(app):
    with app.app_context():
        bind = db.session.connection()
        _schema_pre_a1(bind)
        unidade_id = db.session.execute(
            text(
                "INSERT INTO unidade (nome, ativo) VALUES ('U A1V-MIG', 1) "
                "RETURNING id"
            )
        ).scalar()
        db.session.commit()

        _aplicar_upgrade()
        _inserir_valor("Alegria", unidade_id)

        try:
            _inserir_valor("ALEGRIA", unidade_id)
        except Exception:
            db.session.rollback()
        else:  # pragma: no cover - falha explícita se o índice não existir
            raise AssertionError("índice único funcional não barrou o duplicado")

        assert db.session.execute(
            text(f"SELECT COUNT(*) FROM {mig.TABELA}")
        ).scalar() == 1


def test_downgrade_remove_apenas_a_feature_e_preserva_registros(app):
    with app.app_context():
        bind = db.session.connection()
        _schema_pre_a1(bind)
        unidade_id = db.session.execute(
            text(
                "INSERT INTO unidade (nome, ativo) VALUES ('U A1V-MIG', 1) "
                "RETURNING id"
            )
        ).scalar()
        db.session.commit()
        _seed(unidade_id)

        _aplicar_upgrade()
        valor_id = _inserir_valor("Foco", unidade_id)
        db.session.execute(
            text(f"UPDATE frequencia SET {mig.COLUNA} = :v WHERE conceito = 'A'"),
            {"v": valor_id},
        )
        db.session.commit()
        assert _valor_da_linha("A") == valor_id

        _aplicar_downgrade()

        assert mig.TABELA not in _tabelas()
        assert mig.COLUNA not in _colunas(mig.TABELA_FREQUENCIA)
        assert _conceitos() == ["A", "F"]  # conceito e linhas intactos


def test_reaplicar_upgrade_apos_downgrade(app):
    with app.app_context():
        bind = db.session.connection()
        _schema_pre_a1(bind)
        unidade_id = db.session.execute(
            text(
                "INSERT INTO unidade (nome, ativo) VALUES ('U A1V-MIG', 1) "
                "RETURNING id"
            )
        ).scalar()
        db.session.commit()
        _seed(unidade_id)

        _aplicar_upgrade()
        _aplicar_downgrade()
        _aplicar_upgrade()

        assert mig.TABELA in _tabelas()
        assert mig.COLUNA in _colunas(mig.TABELA_FREQUENCIA)
        assert _conceitos() == ["A", "F"]
        # A tabela recriada volta vazia (o downgrade leva o catálogo junto).
        assert db.session.execute(
            text(f"SELECT COUNT(*) FROM {mig.TABELA}")
        ).scalar() == 0
        assert date.fromisoformat(
            db.session.execute(
                text("SELECT data FROM frequencia LIMIT 1")
            ).scalar()
        )


def test_sql_gerado_para_postgres_e_reversivel(monkeypatch):
    """A DDL do Postgres recebe a FK SET NULL e o downgrade desfaz só a feature.

    Não abre conexão: o `MockEngine` compila o que a migration emitiria no
    dialeto PostgreSQL (o SQLite dos testes não valida o `ADD CONSTRAINT`).
    """
    comandos = []
    engine = create_mock_engine(
        "postgresql+psycopg://",
        lambda stmt, *a, **k: comandos.append(
            str(stmt.compile(dialect=engine.dialect))
        ),
    )
    monkeypatch.setattr(mig.op, "get_bind", lambda: engine)

    mig.upgrade()
    sql = " ".join("\n".join(comandos).split())
    assert "CREATE TABLE valor_esportista" in sql
    assert "CONSTRAINT fk_valor_esportista_unidade" in sql
    assert (
        "CREATE UNIQUE INDEX uix_valor_esportista_nome_unidade "
        "ON valor_esportista (lower(nome), unidade_id)"
    ) in sql
    assert "ALTER TABLE frequencia ADD COLUMN valor_esportista_id INTEGER" in sql
    assert (
        "ADD CONSTRAINT fk_frequencia_valor_esportista FOREIGN KEY "
        "(valor_esportista_id) REFERENCES valor_esportista(id) "
        "ON DELETE SET NULL"
    ) in sql
    assert "CREATE INDEX ix_frequencia_valor_esportista" in sql

    comandos.clear()
    mig.downgrade()
    sql = " ".join("\n".join(comandos).split())
    assert "DROP INDEX IF EXISTS ix_frequencia_valor_esportista" in sql
    assert "DROP CONSTRAINT IF EXISTS fk_frequencia_valor_esportista" in sql
    assert "ALTER TABLE frequencia DROP COLUMN valor_esportista_id" in sql
    assert "DROP INDEX IF EXISTS uix_valor_esportista_nome_unidade" in sql
    assert "DROP TABLE valor_esportista" in sql
    # Reversível sem apagar dados de frequência.
    assert "DELETE FROM" not in sql.upper()
