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
from sqlalchemy import event

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, Unidade, User
from app.services.turma_curso import (
    _conflitos_horario_concomitante,
    adicionar_oferta,
    editar_oferta,
)
from app.services.turma_curso_horario import definir_grade
from config import Config

from _helpers import itens_grade


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
        agenda=itens_grade(dias, ini, fim),
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

    editar_oferta(o2, agenda=itens_grade("Segunda", time(8), time(12)))
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


# ---------------------------------------------------------------------------
# Grade POR DIA (P4): não uniforme, criação sem grade e sem N+1
# ---------------------------------------------------------------------------

def test_grade_nao_uniforme_conflito_so_no_dia_que_sobrepoe(base):
    # Outra oferta: Segunda 08–10 e Quarta 14–16 (grade não uniforme).
    o1 = _oferta(base, base["c1"], "Segunda, Quarta", time(8), time(10),
                 principal=True)
    definir_grade(o1, [(0, time(8), time(10)), (2, time(14), time(16))])

    # Candidata Segunda/Quarta 09–11: sobrepõe SÓ na segunda-feira.
    o2 = _oferta(base, base["c2"], "Segunda, Quarta", time(9), time(11))
    assert o2.avisos_horario == [
        "Horário concomitante com 'Carpintaria' "
        "(Segunda 08:00–10:00). A oferta foi salva."
    ]


def test_grade_nao_uniforme_sem_conflito_no_outro_dia(base):
    o1 = _oferta(base, base["c1"], "Segunda, Quarta", time(8), time(10),
                 principal=True)
    definir_grade(o1, [(0, time(8), time(10)), (2, time(14), time(16))])

    # Só quarta 09–11: o dia da outra oferta é à tarde -> sem aviso.
    o2 = _oferta(base, base["c2"], "Quarta", time(9), time(11))
    assert o2.avisos_horario == []


def test_edicao_de_vigencia_usa_a_grade_nao_uniforme_da_candidata(base):
    _oferta(base, base["c1"], "Terça", time(9), time(11), principal=True)
    o2 = _oferta(base, base["c2"], "Terça, Quinta", time(8), time(10))
    definir_grade(o2, [(1, time(8), time(10)), (3, time(14), time(16))])

    # Edição que só mexe na vigência: compara a GRADE real da candidata
    # (Terça 08–10 sobrepõe Terça 09–11), não o par escalar projetado (NULL).
    editar_oferta(o2, data_fim=date(2026, 12, 31))
    assert o2.avisos_horario == [
        "Horário concomitante com 'Carpintaria' "
        "(Terça, 09:00–11:00). A oferta foi salva."
    ]


def test_candidata_sem_grade_usa_a_agenda_recebida(base):
    _oferta(base, base["c1"], "Segunda", time(8), time(12), principal=True)

    # Criação: a candidata ainda não tem linhas; a agenda recebida é usada.
    avisos = _conflitos_horario_concomitante(
        base["turma_id"],
        agenda=[(0, time(10), time(13))],
    )
    assert avisos == [
        "Horário concomitante com 'Carpintaria' "
        "(Segunda, 08:00–12:00). A oferta foi salva."
    ]
    # A checagem não cria oferta alguma.
    assert TurmaCurso.query.filter_by(
        turma_id=base["turma_id"], ativo=True
    ).count() == 1


def test_grade_em_lote_uma_consulta_de_horarios(base):
    _oferta(base, base["c1"], "Segunda", time(8), time(12), principal=True)
    _oferta(base, base["c2"], "Segunda", time(8), time(12))
    _oferta(base, base["c3"], "Segunda", time(8), time(12))

    consultas: list[str] = []

    def _contar(conn, cursor, statement, parameters, context, executemany):
        if "turma_curso_horario" in statement:
            consultas.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", _contar)
    try:
        avisos = _conflitos_horario_concomitante(
            base["turma_id"],
            agenda=[(0, time(8), time(9))],
        )
    finally:
        event.remove(engine, "before_cursor_execute", _contar)

    # Conflita com as três ofertas, mas as grades saem em UMA consulta.
    assert len(avisos) == 3
    assert len(consultas) == 1, consultas
