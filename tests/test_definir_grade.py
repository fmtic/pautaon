"""H2-P4 — Contrato de ``definir_grade`` (validações, atomicidade, idempotência).

Complementa ``test_turma_curso_horario_servico.py`` (cobertura da camada toda,
validações parametrizadas e no-op de escrita) com o que a decisão H2 exige
especificamente da porta única de escrita da grade:

    - domínio gravável completo: aceita segunda (0) a sábado (5) sem exceção;
    - mensagens em português que IDENTIFICAM O DIA de cada violação;
    - atomicidade em nível de BANCO: grade inválida não altera nada mesmo com
      estado persistido (releitura após rollback, não só a sessão);
    - validação vem ANTES da idempotência: reaplicar a grade vigente com um
      domingo acrescentado continua sendo recusa, não no-op.
"""
from __future__ import annotations

from datetime import date, time

import pytest

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, TurmaCursoHorario, Unidade
from app.services.turma_curso_horario import definir_grade, grade_da_oferta
from config import Config

from _helpers import nova_oferta

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
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _oferta():
    unidade = Unidade(nome="U grade", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome="Curso grade", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    turma = Turma(
        nome="Turma grade", unidade_id=unidade.id, ativo=True,
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    db.session.flush()
    oferta = nova_oferta(turma.id, curso.id, unidade.id, programa="P")
    db.session.commit()
    return oferta


# --- domínio 0–5 --------------------------------------------------------------
@pytest.mark.parametrize("dia", [0, 1, 2, 3, 4, 5])
def test_cada_dia_de_segunda_a_sabado_e_aceito(app, dia):
    o = _oferta()
    definir_grade(o, [(dia, time(9, 0), time(10, 0))])
    db.session.commit()
    assert [l.dia_semana for l in grade_da_oferta(o)] == [dia]


def test_domingo_rejeitado_mesmo_apos_grade_valida(app):
    o = _oferta()
    definir_grade(o, [(0, time(9, 0), time(10, 0))])
    db.session.commit()
    with pytest.raises(ValueError, match="Domingo não é dia de aula"):
        definir_grade(o, [(0, time(9, 0), time(10, 0)), (6, time(9, 0), time(10, 0))])


# --- mensagens identificam o dia -----------------------------------------------
def test_mensagem_dia_duplicado_cita_o_dia(app):
    o = _oferta()
    with pytest.raises(ValueError, match="Dia duplicado na grade: Terça\\."):
        definir_grade(
            o,
            [(0, time(9, 0), time(10, 0)), (1, time(9, 0), time(10, 0)),
             (1, time(14, 0), time(15, 0))],
        )


def test_mensagem_hora_faltando_cita_o_dia(app):
    o = _oferta()
    with pytest.raises(ValueError, match=r"Falta horário no dia Quinta"):
        definir_grade(o, [(3, None, None)])


def test_mensagem_fim_invalido_cita_o_dia(app):
    o = _oferta()
    with pytest.raises(ValueError, match="Horário inválido no dia Sábado"):
        definir_grade(o, [(5, time(16, 0), time(8, 0))])


def test_mensagem_dia_fora_do_dominio(app):
    o = _oferta()
    with pytest.raises(ValueError, match="dia_semana inválido"):
        definir_grade(o, [(9, time(9, 0), time(10, 0))])


def test_mensagem_grade_vazia(app):
    o = _oferta()
    with pytest.raises(ValueError, match="A grade não pode ficar vazia"):
        definir_grade(o, [])


# --- atomicidade em nível de banco ----------------------------------------------
def test_grade_invalida_nao_altera_nada_no_banco(app):
    """Erro no meio da lista não encosta nas linhas nem na projeção já
    persistidas — verificado por releitura do BANCO após rollback."""
    o = _oferta()
    definir_grade(o, [(0, time(9, 0), time(10, 0)), (2, time(9, 0), time(10, 0))])
    db.session.commit()
    ids_antes = sorted(l.id for l in o.horarios)

    with pytest.raises(ValueError):
        # primeiro item ok, segundo duplicado: recusa tudo
        definir_grade(o, [(1, time(8, 0), time(9, 0)), (1, time(10, 0), time(11, 0))])
    db.session.rollback()

    oferta_ok = db.session.get(TurmaCurso, o.id)
    assert sorted(l.id for l in oferta_ok.horarios) == ids_antes
    assert [
        (l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta_ok)
    ] == [
        (0, time(9, 0), time(10, 0)),
        (2, time(9, 0), time(10, 0)),
    ]
    # projeção intacta (dias + par uniforme)
    assert oferta_ok.dias_semana == "Segunda, Quarta"
    assert oferta_ok.hora_inicio == time(9, 0) and oferta_ok.hora_fim == time(10, 0)
    assert TurmaCursoHorario.query.count() == 2


def test_grade_vazia_recusada_preserva_linhas_persistidas(app):
    o = _oferta()
    definir_grade(o, [(4, time(9, 0), time(12, 0))])
    db.session.commit()

    with pytest.raises(ValueError, match="vazia"):
        definir_grade(o, [])
    db.session.rollback()

    assert TurmaCursoHorario.query.filter_by(turma_curso_id=o.id).count() == 1


def test_validacao_vem_antes_da_idempotencia(app):
    """Reaplicar a grade vigente MAIS um domingo não é no-op: valida primeiro."""
    o = _oferta()
    itens = [(0, time(9, 0), time(10, 0))]
    definir_grade(o, itens)
    db.session.commit()

    with pytest.raises(ValueError, match="Domingo"):
        definir_grade(o, itens + [(6, time(9, 0), time(10, 0))])
    db.session.rollback()
    assert TurmaCursoHorario.query.count() == 1
