"""Concomitância de horário POR DIA (H3b).

Caracterização ANTES da migração (P2): para grades UNIFORMES, fixa quais pares
de ofertas geram aviso e o texto EXATO da mensagem. Estes testes devem passar
idênticos antes e depois de os dias/horas passarem a ser lidos da grade
(``turma_curso_horario``).

Regra (MER §8.10): concomitância é AVISO, nunca bloqueio; adjacência de
horários não conflita; vigências sem interseção não conflitam.
"""

from datetime import date, time

import pytest

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, Unidade, User
from app.services.turma_curso import adicionar_oferta, editar_oferta
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
    """Unidade com 3 cursos e 1 turma multioferta."""
    unidade = Unidade(nome="Unidade Concomitância", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    admin = User(
        name="Admin H3b",
        email="admin.h3b@example.com",
        role="admin",
        first_login=False,
        unidade_id=unidade.id,
    )
    db.session.add(admin)

    c1 = Curso(nome="Carpintaria", unidade_id=unidade.id, ativo=True)
    c2 = Curso(nome="Mecânica", unidade_id=unidade.id, ativo=True)
    c3 = Curso(nome="Natação", unidade_id=unidade.id, ativo=True)
    db.session.add_all([c1, c2, c3])

    turma = Turma(
        nome="Turma H3b",
        unidade_id=unidade.id,
        ativo=True,
        curso_id=None,
    )
    db.session.add(turma)
    db.session.commit()

    return {
        "turma_id": turma.id,
        "c1": c1.id,
        "c2": c2.id,
        "c3": c3.id,
    }


def _turma(base):
    return db.session.get(Turma, base["turma_id"])


def _oferta(base, curso, dias, ini, fim, data_ini=None, data_fim=None, principal=False):
    return adicionar_oferta(
        _turma(base),
        curso_id=curso,
        principal=principal,
        programa="Teste",
        dias_semana=dias,
        hora_inicio=ini,
        hora_fim=fim,
        data_inicio=data_ini,
        data_fim=data_fim,
    )


# ---------------------------------------------------------------------------
# Caracterização (grades uniformes): pares que geram aviso e o texto exato
# ---------------------------------------------------------------------------

def test_sobreposicao_total_gera_aviso_texto_exato(base):
    _oferta(
        base, base["c1"], "Segunda, Quarta", time(8), time(12),
        date(2026, 1, 1), date(2026, 6, 30), principal=True,
    )
    o2 = _oferta(
        base, base["c2"], "Segunda, Quarta", time(8), time(12),
        date(2026, 1, 1), date(2026, 6, 30),
    )
    assert o2.avisos_horario == [
        "Horário concomitante com 'Carpintaria' "
        "(Segunda, Quarta, 08:00–12:00). A oferta foi salva."
    ]


def test_sobreposicao_parcial_gera_aviso_texto_exato(base):
    _oferta(base, base["c1"], "Segunda", time(8), time(12), principal=True)
    o2 = _oferta(base, base["c2"], "Segunda", time(10), time(14))
    assert o2.avisos_horario == [
        "Horário concomitante com 'Carpintaria' "
        "(Segunda, 08:00–12:00). A oferta foi salva."
    ]


def test_adjacencia_de_horario_nao_gera_aviso(base):
    _oferta(base, base["c1"], "Segunda, Quarta", time(8), time(12), principal=True)
    o2 = _oferta(base, base["c2"], "Segunda, Quarta", time(12), time(14))
    assert o2.avisos_horario == []


def test_dias_diferentes_nao_gera_aviso(base):
    _oferta(base, base["c1"], "Segunda, Quarta", time(8), time(12), principal=True)
    o2 = _oferta(base, base["c2"], "Terça, Sexta", time(8), time(12))
    assert o2.avisos_horario == []


def test_vigencia_sem_intersecao_nao_gera_aviso(base):
    _oferta(
        base, base["c1"], "Segunda", time(8), time(12),
        date(2026, 1, 1), date(2026, 6, 30), principal=True,
    )
    o2 = _oferta(
        base, base["c2"], "Segunda", time(8), time(12),
        date(2026, 7, 1), date(2026, 12, 31),
    )
    assert o2.avisos_horario == []


def test_edicao_que_cria_conflito_gera_aviso_texto_exato(base):
    _oferta(base, base["c1"], "Segunda", time(8), time(12), principal=True)
    o2 = _oferta(base, base["c2"], "Terça", time(8), time(12))
    assert o2.avisos_horario == []

    editar_oferta(o2, dias_semana="Segunda")
    assert o2.avisos_horario == [
        "Horário concomitante com 'Carpintaria' "
        "(Segunda, 08:00–12:00). A oferta foi salva."
    ]


def test_dois_conflitos_geram_dois_avisos_em_ordem_de_id(base):
    _oferta(base, base["c1"], "Segunda", time(8), time(12), principal=True)
    _oferta(base, base["c2"], "Segunda", time(8), time(12))
    o3 = _oferta(base, base["c3"], "Segunda", time(8), time(12))
    assert o3.avisos_horario == [
        "Horário concomitante com 'Carpintaria' "
        "(Segunda, 08:00–12:00). A oferta foi salva.",
        "Horário concomitante com 'Mecânica' "
        "(Segunda, 08:00–12:00). A oferta foi salva.",
    ]


def test_concomitancia_nunca_bloqueia(base):
    _oferta(base, base["c1"], "Segunda", time(8), time(12), principal=True)
    o2 = _oferta(base, base["c2"], "Segunda", time(8), time(12))
    # Aviso não impede a gravação: as duas ofertas ficam ativas.
    assert TurmaCurso.query.filter_by(
        turma_id=base["turma_id"], ativo=True
    ).count() == 2
    assert o2.avisos_horario  # aviso presente, mas a oferta foi salva
