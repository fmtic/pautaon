"""
G1/P2 (E2) — `turma_curso.professor_id` NOT NULL (migration d6e7f8a9b0c1).

A obrigatoriedade de escrita já vigora no serviço/formulário (E2 da rodada,
test_g1_p2_professor_oferta.py). Este arquivo fecha o G1/P2 pelo lado do
**banco**: mesmo um INSERT bruto, fora de qualquer validação, é recusado.

O schema dos testes vem do metadata dos modelos (`db.create_all` no SQLite em
memória), então o `nullable=False` do modelo é a mesma trava que a migration
d6e7f8a9b0c1 aplicou nos bancos reais (conferido na estrutura da coluna).
"""

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, Unidade, User
from config import Config

DATA_INI = date(2026, 3, 9)
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def base(app):
    unidade = Unidade(nome="U", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome="C", unidade_id=unidade.id, ativo=True)
    professor = User(
        name="Prof", email="prof@e.com", role="professor",
        first_login=False, unidade_id=unidade.id,
    )
    turma = Turma(
        nome="T", unidade_id=unidade.id, ativo=True, turno="Manhã",
        data_inicio=DATA_INI, data_fim=DATA_FIM, programa="X",
    )
    db.session.add_all([curso, professor, turma])
    db.session.commit()
    return {"unidade": unidade.id, "curso": curso.id, "professor": professor.id, "turma": turma.id}


def test_insert_bruto_sem_professor_recusado_pelo_banco(app, base):
    """Antigo: `turma_curso.professor_id` era nullable — INSERT fora do serviço
    gravava oferta sem professor (foi assim que as 16/17/18 nasceram).
    Novo: IntegrityError já no flush. Motivo: NOT NULL da migration
    d6e7f8a9b0c1 (G1/P2), espelhada no modelo."""
    oferta = TurmaCurso(
        turma_id=base["turma"], curso_id=base["curso"], principal=True,
        programa="X", turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
        unidade_id=base["unidade"], ativo=True, professor_id=None,
    )
    db.session.add(oferta)
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_insert_bruto_com_professor_grava(app, base):
    """Contraprova: a recusa é do NULL, não da tabela — com professor o mesmo
    INSERT bruto passa."""
    oferta = TurmaCurso(
        turma_id=base["turma"], curso_id=base["curso"], principal=True,
        programa="X", turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
        unidade_id=base["unidade"], ativo=True, professor_id=base["professor"],
    )
    db.session.add(oferta)
    db.session.commit()
    assert oferta.id is not None


def test_modelo_declara_coluna_not_null(app):
    """Guarda de coerência modelo × migration: se alguém devolver nullable=True
    no modelo sem downgrade da d6e7f8a9b0c1, os bancos e os testes divergem."""
    coluna = TurmaCurso.__table__.columns["professor_id"]
    assert coluna.nullable is False
