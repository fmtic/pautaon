"""Etapa D5.1—D5.5 — Esquema do conselho por oferta (schema, SQLite).

Regras do responsável (decisões D5/D5.5, 24-25/10/2026):
    - Conselho de classe tem OFERTA própria e OBRIGATÓRIA:
      `conselho_classe.turma_curso_id` é NOT NULL (D5.5).
    - A UNIQUE antiga (turma_id, aluno_id, etapa) não existe: `uix_conselho_oferta`
      (turma_curso_id, aluno_id, etapa) é a única unicidade, POR OFERTA.
    - O ramo legado `uix_conselho_legado` saiu junto com o NULL (D5.5).
    - O mesmo aluno pode ter um conselho POR OFERTA na mesma turma/etapa.
    - `turma_curso` ganha conselho_concluido (NOT NULL default false) e os
      pareceres avaliacao_inicial/percurso/final (nullable) — `turma` NÃO tem
      mais `conselho_concluido` (derivada das ofertas na leitura).

Cobertura:
    1. Colunas novas e defaults; `turma_curso_id` NOT NULL + FK RESTRICT;
       conselho sem oferta é RECUSADO pelo banco.
    2. Mesmo aluno, mesma turma/etapa, DUAS ofertas diferentes → permitido.
    3. Duplicata na MESMA oferta/etapa → recusada (uix_conselho_oferta).
    4. Conselho sem oferta → recusado (NOT NULL).
    5. `turma` não tem a coluna `conselho_concluido`; a flag vive só na oferta.
    6. O índice único por oferta e ix_conselho_turma_curso existem na schema
       SQLite gerada pelos modelos; o ramo legado não volta.

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
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    db.session.flush()

    # UNIQUE (turma_id, curso_id): duas ofertas da mesma turma exigem cursos.
    # G1/P2 (d6e7f8a9b0c1): oferta exige professor — usa o responsável da turma.
    o1 = nova_oferta(
        turma.id, curso.id, unidade.id, programa="Programa 1", professor_id=user.id,
    )
    o2 = nova_oferta(
        turma.id, curso2.id, unidade.id, programa="Programa 2", professor_id=user.id,
    )

    aluno = Aluno(nome="Aluno D5", ativo=True, unidade_id=unidade.id)
    db.session.add(aluno)
    db.session.flush()

    return {
        "unidade": unidade.id, "user": user.id, "curso": curso.id,
        "curso2": curso2.id,
        "turma": turma.id, "o1": o1.id, "o2": o2.id, "aluno": aluno.id,
    }


def _conselho(i, etapa=EtapaConselho.INICIAL, turma_curso_id="o1"):
    """Cria um conselho na OFERTA indicada (por padrão a oferta `o1`).

    D5.5: `turma_curso_id` é obrigatório — a única forma de pedir NULL é
    passar `turma_curso_id=None`, que o banco recusa.
    """
    alvo = i[turma_curso_id] if isinstance(turma_curso_id, str) else turma_curso_id
    cc = ConselhoClasse(
        turma_id=i["turma"], aluno_id=i["aluno"],
        etapa=etapa, unidade_id=i["unidade"],
        turma_curso_id=alvo,
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

    # ConselhoClasse.turma_curso_id: NOT NULL (D5.5) + FK RESTRICT.
    col = ConselhoClasse.__table__.c.turma_curso_id
    assert col.nullable is False
    fk = next(iter(col.foreign_keys))
    assert fk.target_fullname == "turma_curso.id"
    assert fk.ondelete == "RESTRICT"

    # Conselho sem oferta deixou de existir: o banco recusa.
    with pytest.raises(IntegrityError):
        _conselho(i, turma_curso_id=None)
        db.session.commit()
    db.session.rollback()


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
# 4. Conselho sem oferta → recusado (D5.5)
# ---------------------------------------------------------------------------

def test_conselho_sem_oferta_recusado(app):
    i = _seed()
    _conselho(i, turma_curso_id=i["o1"])
    db.session.commit()

    with pytest.raises(IntegrityError):
        _conselho(i, etapa=EtapaConselho.PERCURSO, turma_curso_id=None)
        db.session.commit()
    db.session.rollback()

    assert ConselhoClasse.query.filter_by(turma_curso_id=None).count() == 0


# ---------------------------------------------------------------------------
# 5. `turma` sem a flag; o encerramento vive só na oferta
# ---------------------------------------------------------------------------

def test_turma_sem_flag_e_oferta_com_flag(app):
    i = _seed()
    assert "conselho_concluido" not in Turma.__table__.c

    oferta = db.session.get(TurmaCurso, i["o1"])
    oferta.conselho_concluido = True
    db.session.commit()
    assert db.session.get(TurmaCurso, i["o1"]).conselho_concluido is True
    assert db.session.get(TurmaCurso, i["o2"]).conselho_concluido is False

    # As duas ofertas da mesma turma/etapa convivem para o mesmo aluno.
    _conselho(i, turma_curso_id=i["o1"])
    _conselho(i, turma_curso_id=i["o2"])
    db.session.commit()
    assert ConselhoClasse.query.filter_by(
        turma_id=i["turma"], aluno_id=i["aluno"],
        etapa=EtapaConselho.INICIAL,
    ).count() == 2


# ---------------------------------------------------------------------------
# 6. Schema: UNIQUE por oferta presente, ramo legado ausente
# ---------------------------------------------------------------------------

def test_schema_indice_unico_por_oferta(app):
    idx = {x["name"]: x for x in inspect(db.engine).get_indexes("conselho_classe") if x.get("name")}

    assert "uix_conselho_oferta" in idx
    assert idx["uix_conselho_oferta"]["unique"]

    assert "ix_conselho_turma_curso" in idx
    assert not idx["ix_conselho_turma_curso"]["unique"]

    # D5.5: o ramo legado não pode voltar pela create_all dos modelos.
    assert "uix_conselho_legado" not in idx
    assert "uix_conselho_turma_aluno_etapa" not in idx
    unicos = {u["name"] for u in inspect(db.engine).get_unique_constraints("conselho_classe") if u.get("name")}
    assert "uix_conselho_turma_aluno_etapa" not in unicos

    # SQLite: o WHERE parcial continua na DDL do índice (inócuo com NOT NULL).
    with db.engine.connect() as conn:
        ddl = dict(conn.execute(
            text(
                "SELECT name, sql FROM sqlite_master WHERE type='index' "
                "AND tbl_name='conselho_classe'"
            )
        ).fetchall())
    assert "turma_curso_id IS NOT NULL" in ddl["uix_conselho_oferta"]
