"""Etapa D5.1 — Esquema aditivo do conselho por oferta (schema, SQLite).

Regras do responsável (decisão D5, 24/10/2026):
    - Conselho de classe passa a ter OFERTA própria: `conselho_classe.turma_curso_id`.
    - A UNIQUE antiga (turma_id, aluno_id, etapa) foi substituída por dois
      índices ÚNICOS PARCIAIS:
        uix_conselho_legado (turma_id, aluno_id, etapa) WHERE turma_curso_id IS NULL
        uix_conselho_oferta (turma_curso_id, aluno_id, etapa) WHERE turma_curso_id IS NOT NULL
    - O mesmo aluno pode ter um conselho POR OFERTA na mesma turma/etapa.
    - `turma_curso` ganha conselho_concluido (NOT NULL default false) e os
      pareceres avaliacao_inicial/percurso/final (nullable), espelhando Turma.

Cobertura:
    1. Colunas novas e defaults (oferta e conselho); NULL em turma_curso_id é
       aceito (estado legado).
    2. Mesmo aluno, mesma turma/etapa, DUAS ofertas diferentes → permitido.
    3. Duplicata na MESMA oferta/etapa → recusada (uix_conselho_oferta).
    4. Duplicata legada (turma_curso_id NULL) → recusada (uix_conselho_legado).
    5. Conselho legado (NULL) e conselho de oferta COEXISTEM na mesma
       turma/aluno/etapa.
    6. Os dois índices parciais e ix_conselho_turma_curso existem na schema
       SQLite gerada pelos modelos, e a UNIQUE antiga não está na tabela.

Um usuário por teste (nenhum login/rota; schema pura em SQLite in-memory).
"""

from datetime import date, time

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import (
    Aluno,
    ConselhoClasse,
    Curso,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho
from config import Config

from _helpers import nova_inscricao, nova_oferta

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
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
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _seed(nome_user="Resp D5"):
    """Unidade + 1 usuário + curso + turma com 2 ofertas ativas e 1 aluno.

    Retorna dict com ids. O aluno NÃO tem inscrição ainda (cada teste decide).
    """
    unidade = Unidade(nome=f"U {nome_user}", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    user = User(
        name=nome_user, email=f"{nome_user.lower().replace(' ', '.')}@example.com",
        role="pedagogico", first_login=False, unidade_id=unidade.id,
    )
    db.session.add(user)
    curso = Curso(nome="Curso D5", unidade_id=unidade.id, ativo=True)
    curso2 = Curso(nome="Curso D5 B", unidade_id=unidade.id, ativo=True)
    db.session.add_all([curso, curso2])
    turma = Turma(
        nome="Turma D5", unidade_id=unidade.id, ativo=True,
        curso_id=curso.id, professor_id=user.id, turno="Manhã",
        dias_semana="Segunda", hora_inicio=time(9, 0), hora_fim=time(10, 0),
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    db.session.flush()

    # UNIQUE (turma_id, curso_id): duas ofertas da mesma turma exigem cursos.
    o1 = nova_oferta(turma.id, curso.id, unidade.id, programa="Programa 1")
    o2 = nova_oferta(turma.id, curso2.id, unidade.id, programa="Programa 2")

    aluno = Aluno(nome="Aluno D5", ativo=True, unidade_id=unidade.id)
    db.session.add(aluno)
    db.session.flush()

    return {
        "unidade": unidade.id, "user": user.id, "curso": curso.id,
        "curso2": curso2.id,
        "turma": turma.id, "o1": o1.id, "o2": o2.id, "aluno": aluno.id,
    }


def _conselho(i, etapa=EtapaConselho.INICIAL, turma_curso_id=None):
    cc = ConselhoClasse(
        turma_id=i["turma"], aluno_id=i["aluno"],
        etapa=etapa, unidade_id=i["unidade"],
        turma_curso_id=turma_curso_id,
    )
    db.session.add(cc)
    db.session.flush()
    return cc


# ---------------------------------------------------------------------------
# 1. Colunas e defaults
# ---------------------------------------------------------------------------

def test_colunas_novas_e_defaults(app):
    i = _seed()
    oferta = db.session.get(TurmaCurso, i["o1"])

    # TurmaCurso (D5.1): flag e pareceres espelhando Turma.
    assert oferta.conselho_concluido is False
    assert oferta.avaliacao_inicial is None
    assert oferta.avaliacao_percurso is None
    assert oferta.avaliacao_final is None

    server_default = TurmaCurso.__table__.c.conselho_concluido.server_default
    assert server_default is not None  # server_default false na DDL
    assert TurmaCurso.__table__.c.conselho_concluido.nullable is False
    assert TurmaCurso.__table__.c.avaliacao_inicial.nullable is True

    # ConselhoClasse.turma_curso_id: nullable + FK RESTRICT.
    col = ConselhoClasse.__table__.c.turma_curso_id
    assert col.nullable is True
    fk = next(iter(col.foreign_keys))
    assert fk.target_fullname == "turma_curso.id"
    assert fk.ondelete == "RESTRICT"

    # Estado legado: conselho sem oferta é aceito (NULL).
    cc = _conselho(i)
    assert cc.turma_curso_id is None


# ---------------------------------------------------------------------------
# 2. Mesmo aluno em duas ofertas da mesma turma/etapa → permitido
# ---------------------------------------------------------------------------

def test_conselho_por_oferta_mesmo_aluno_permitido(app):
    i = _seed()
    nova_inscricao(i["aluno"], i["turma"], i["o1"])
    nova_inscricao(i["aluno"], i["turma"], i["o2"])

    _conselho(i, turma_curso_id=i["o1"])
    _conselho(i, turma_curso_id=i["o2"])  # mesma etapa, outra oferta
    db.session.commit()

    n = ConselhoClasse.query.filter_by(aluno_id=i["aluno"], etapa=EtapaConselho.INICIAL).count()
    assert n == 2


# ---------------------------------------------------------------------------
# 3. Duplicata na MESMA oferta/etapa → recusada
# ---------------------------------------------------------------------------

def test_duplicata_mesma_oferta_recusada(app):
    i = _seed()
    _conselho(i, turma_curso_id=i["o1"])
    db.session.commit()

    with pytest.raises(IntegrityError):
        _conselho(i, turma_curso_id=i["o1"])
        db.session.commit()
    db.session.rollback()

    # Etapa diferente na mesma oferta é permitida.
    _conselho(i, etapa=EtapaConselho.PERCURSO, turma_curso_id=i["o1"])
    db.session.commit()
    assert ConselhoClasse.query.filter_by(turma_curso_id=i["o1"]).count() == 2


# ---------------------------------------------------------------------------
# 4. Duplicata legada (turma_curso_id NULL) → recusada
# ---------------------------------------------------------------------------

def test_duplicata_legada_recusada(app):
    i = _seed()
    _conselho(i)  # NULL = legado
    db.session.commit()

    with pytest.raises(IntegrityError):
        _conselho(i)
        db.session.commit()
    db.session.rollback()


# ---------------------------------------------------------------------------
# 5. Legado (NULL) e oferta coexistem
# ---------------------------------------------------------------------------

def test_legado_e_oferta_coexistem(app):
    i = _seed()
    _conselho(i)  # legado
    _conselho(i, turma_curso_id=i["o1"])  # oferta — mesma turma/aluno/etapa
    db.session.commit()

    rows = ConselhoClasse.query.filter_by(
        turma_id=i["turma"], aluno_id=i["aluno"], etapa=EtapaConselho.INICIAL,
    ).all()
    assert len(rows) == 2
    assert {r.turma_curso_id for r in rows} == {None, i["o1"]}


# ---------------------------------------------------------------------------
# 6. Schema: índices parciais presentes, UNIQUE antiga ausente
# ---------------------------------------------------------------------------

def test_schema_indices_parciais(app):
    idx = {x["name"]: x for x in inspect(db.engine).get_indexes("conselho_classe") if x.get("name")}

    for nome in ("uix_conselho_legado", "uix_conselho_oferta"):
        assert nome in idx, f"índice parcial {nome} ausente na schema SQLite"
        assert idx[nome]["unique"]

    assert "ix_conselho_turma_curso" in idx
    assert not idx["ix_conselho_turma_curso"]["unique"]

    # A UNIQUE antiga não pode voltar pela create_all dos modelos.
    assert "uix_conselho_turma_aluno_etapa" not in idx
    unicos = {u["name"] for u in inspect(db.engine).get_unique_constraints("conselho_classe") if u.get("name")}
    assert "uix_conselho_turma_aluno_etapa" not in unicos

    # SQLite: os WHERE parciais devem estar na DDL dos índices.
    with db.engine.connect() as conn:
        ddl = dict(conn.execute(
            text(
                "SELECT name, sql FROM sqlite_master WHERE type='index' "
                "AND tbl_name='conselho_classe'"
            )
        ).fetchall())
    assert "turma_curso_id IS NULL" in ddl["uix_conselho_legado"]
    assert "turma_curso_id IS NOT NULL" in ddl["uix_conselho_oferta"]
