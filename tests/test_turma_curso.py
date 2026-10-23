"""
Testes da Onda 4 — Fase 1: entidade TurmaCurso (oferta concreta de curso
em uma turma) e o vínculo de Inscricao à oferta.

Cobre (cenários do plano, §16 da especificação):
    - Turma com oferta única sem marcação de principal.
    - Tentativa de ofertar o mesmo curso duas vezes na mesma turma (UNIQUE).
    - Oferta do mesmo curso em turmas diferentes (permitido).
    - Múltiplos cursos na mesma turma com exatamente um principal.
    - Tentativa de criar mais de um principal na mesma turma (índice parcial).
    - Principal em turmas diferentes é permitido (índice é por turma).
    - Inscricao referenciando a oferta concreta e navegando os relacionamentos.

Observação: o BACKFILL das ofertas a partir das turmas legadas é uma operação
de migration (PostgreSQL) validada separadamente; estes testes exercitam o
modelo e as restrições via create_all (SQLite), mesmo mecanismo dos demais
testes do projeto.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import Aluno, Curso, Inscricao, Turma, TurmaCurso, Unidade, User
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def base(app):
    """Cria unidade, admin, dois cursos e duas turmas; retorna os IDs."""
    unidade = Unidade(nome="Unidade Base", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    admin = User(
        name="Admin", email="admin.base@example.com",
        role="admin", first_login=False, unidade_id=unidade.id,
    )
    db.session.add(admin)

    curso1 = Curso(nome="Carpintaria", unidade_id=unidade.id, ativo=True)
    curso2 = Curso(nome="Mecânica", unidade_id=unidade.id, ativo=True)
    db.session.add_all([curso1, curso2])
    db.session.flush()

    turma1 = Turma(nome="Turma 1", unidade_id=unidade.id, ativo=True)
    turma2 = Turma(nome="Turma 2", unidade_id=unidade.id, ativo=True)
    db.session.add_all([turma1, turma2])
    db.session.commit()

    return {
        "unidade_id": unidade.id,
        "curso1": curso1.id,
        "curso2": curso2.id,
        "turma1": turma1.id,
        "turma2": turma2.id,
    }


def test_oferta_unica_sem_principal(base):
    """Turma com um único curso pode ficar sem marcação de principal."""
    oferta = TurmaCurso(
        turma_id=base["turma1"], curso_id=base["curso1"],
        principal=False, unidade_id=base["unidade_id"], ativo=True,
    )
    db.session.add(oferta)
    db.session.commit()

    recuperada = db.session.get(TurmaCurso, oferta.id)
    assert recuperada is not None
    assert recuperada.principal is False


def test_mesmo_curso_nao_pode_repetir_na_mesma_turma(base):
    """UNIQUE(turma_id, curso_id) impede ofertar o mesmo curso duas vezes."""
    db.session.add(TurmaCurso(
        turma_id=base["turma1"], curso_id=base["curso1"],
        principal=False, unidade_id=base["unidade_id"], ativo=True,
    ))
    db.session.commit()

    db.session.add(TurmaCurso(
        turma_id=base["turma1"], curso_id=base["curso1"],
        principal=False, unidade_id=base["unidade_id"], ativo=True,
    ))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_mesmo_curso_em_turmas_diferentes_e_permitido(base):
    """O mesmo curso pode ser ofertado em turmas distintas."""
    db.session.add_all([
        TurmaCurso(turma_id=base["turma1"], curso_id=base["curso1"],
                   unidade_id=base["unidade_id"], ativo=True),
        TurmaCurso(turma_id=base["turma2"], curso_id=base["curso1"],
                   unidade_id=base["unidade_id"], ativo=True),
    ])
    db.session.commit()

    assert db.session.query(TurmaCurso).filter_by(curso_id=base["curso1"]).count() == 2


def test_multiplos_cursos_com_um_exato_principal(base):
    """Dois cursos na mesma turma com exatamente um principal é válido."""
    db.session.add_all([
        TurmaCurso(turma_id=base["turma1"], curso_id=base["curso1"],
                   principal=True, unidade_id=base["unidade_id"], ativo=True),
        TurmaCurso(turma_id=base["turma1"], curso_id=base["curso2"],
                   principal=False, unidade_id=base["unidade_id"], ativo=True),
    ])
    db.session.commit()

    principais = (
        db.session.query(TurmaCurso)
        .filter_by(turma_id=base["turma1"], principal=True)
        .count()
    )
    assert principais == 1


def test_nao_pode_haver_dois_principais_na_mesma_turma(base):
    """Índice único parcial bloqueia um segundo principal na mesma turma."""
    db.session.add(TurmaCurso(
        turma_id=base["turma1"], curso_id=base["curso1"],
        principal=True, unidade_id=base["unidade_id"], ativo=True,
    ))
    db.session.commit()

    db.session.add(TurmaCurso(
        turma_id=base["turma1"], curso_id=base["curso2"],
        principal=True, unidade_id=base["unidade_id"], ativo=True,
    ))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_principal_pode_repetir_em_turmas_diferentes(base):
    """Cada turma tem seu próprio principal; o índice é escopado por turma."""
    db.session.add_all([
        TurmaCurso(turma_id=base["turma1"], curso_id=base["curso1"],
                   principal=True, unidade_id=base["unidade_id"], ativo=True),
        TurmaCurso(turma_id=base["turma2"], curso_id=base["curso1"],
                   principal=True, unidade_id=base["unidade_id"], ativo=True),
    ])
    db.session.commit()

    assert db.session.query(TurmaCurso).filter_by(principal=True).count() == 2


def test_inscricao_vinculada_a_oferta(base):
    """Inscricao referencia a oferta concreta e navega turma/curso/oferta."""
    oferta = TurmaCurso(
        turma_id=base["turma1"], curso_id=base["curso1"],
        principal=False, unidade_id=base["unidade_id"], ativo=True,
    )
    db.session.add(oferta)
    db.session.flush()

    aluno = Aluno(
        nome="Aluno Teste", nome_social="Aluno",
        unidade_id=base["unidade_id"], ativo=True,
    )
    db.session.add(aluno)
    db.session.flush()

    inscricao = Inscricao(
        aluno_id=aluno.id, turma_id=base["turma1"],
        turma_curso_id=oferta.id, ativo=True,
    )
    db.session.add(inscricao)
    db.session.commit()

    assert inscricao.turma_curso_id == oferta.id
    assert inscricao.turma_curso.curso_id == base["curso1"]
    assert oferta.inscricoes_oferta[0].id == inscricao.id
