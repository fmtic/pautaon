"""H1-P5 — Esquema de `turma_curso_horario` (SQLite, padrão test_d5_schema).

Cobre as constraints portáveis da grade por dia da oferta e os vínculos:
    - UNIQUE `uix_turma_curso_horario_dia` (turma_curso_id, dia_semana).
    - CHECK `ck_tch_dia` (domínio 0-5).
    - CHECK `ck_tch_par` (ambos NULL ou ambos preenchidos).
    - CHECK `ck_tch_fim_maior` (fim > início quando preenchidos).
    - FK `turma_curso_id` ON DELETE CASCADE (apagar a oferta apaga a grade).
    - `excluir_turma` físico (sequência de deletes em massa da rota) continua
      funcionando com a tabela filha presente.
    - Ordenação do relacionamento `TurmaCurso.horarios` por `dia_semana`.

Nenhum teste aqui depende de login/rota; schema pura em SQLite in-memory com
`PRAGMA foreign_keys = ON` para exercitar o CASCADE.
"""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, TurmaCursoHorario, Unidade
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
        assert db.engine.dialect.name == "sqlite"
        # FK enforcement necessário para testar o ON DELETE CASCADE no SQLite.
        @event.listens_for(db.engine, "connect")
        def _fk_on(dbapi_conn, _rec):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _seed():
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
    return {"unidade": unidade.id, "curso": curso.id, "turma": turma.id, "oferta": oferta.id}


def _linha(oferta_id, dia, ini=None, fim=None):
    linha = TurmaCursoHorario(
        turma_curso_id=oferta_id, dia_semana=dia, hora_inicio=ini, hora_fim=fim,
    )
    db.session.add(linha)
    db.session.flush()
    return linha


# --- UNIQUE (oferta, dia) -----------------------------------------------------
def test_uniq_mesmo_dia_na_mesma_oferta_recusado(app):
    i = _seed()
    _linha(i["oferta"], 0, time(13, 0), time(15, 0))
    db.session.commit()
    with pytest.raises(IntegrityError):
        _linha(i["oferta"], 0, time(9, 0), time(10, 0))
        db.session.commit()
    db.session.rollback()


def test_mesmo_dia_em_ofertas_diferentes_permitido(app):
    i = _seed()
    curso2 = Curso(nome="Curso grade 2", unidade_id=i["unidade"], ativo=True)
    db.session.add(curso2)
    db.session.flush()
    oferta2 = nova_oferta(i["turma"], curso2.id, i["unidade"], programa="P2")
    _linha(i["oferta"], 1, time(13, 0), time(15, 0))
    _linha(oferta2.id, 1, time(13, 0), time(15, 0))
    db.session.commit()
    assert TurmaCursoHorario.query.filter_by(dia_semana=1).count() == 2


# --- CHECK domínio 0-5 --------------------------------------------------------
def test_check_dia_fora_do_domainio_recusado(app):
    i = _seed()
    for invalido in (-1, 6, 7):
        with pytest.raises(IntegrityError):
            _linha(i["oferta"], invalido)
            db.session.commit()
        db.session.rollback()


def test_check_dia_0_e_5_aceitos(app):
    i = _seed()
    _linha(i["oferta"], 0, time(9, 0), time(10, 0))
    _linha(i["oferta"], 5, time(9, 0), time(10, 0))
    db.session.commit()
    assert TurmaCursoHorario.query.filter_by(
        turma_curso_id=i["oferta"]
    ).count() == 2


# --- CHECK par (ambos NULL ou ambos preenchidos) ------------------------------
def test_check_par_incompleto_recusado(app):
    i = _seed()
    with pytest.raises(IntegrityError):
        _linha(i["oferta"], 0, time(9, 0), None)   # só início
        db.session.commit()
    db.session.rollback()
    with pytest.raises(IntegrityError):
        _linha(i["oferta"], 1, None, time(10, 0))  # só fim
        db.session.commit()
    db.session.rollback()


def test_check_ambos_null_permitido(app):
    i = _seed()
    _linha(i["oferta"], 2)  # dia sem horário
    db.session.commit()
    assert TurmaCursoHorario.query.filter_by(dia_semana=2).count() == 1


# --- CHECK fim > início -------------------------------------------------------
def test_check_fim_menor_ou_igual_recusado(app):
    i = _seed()
    with pytest.raises(IntegrityError):
        _linha(i["oferta"], 0, time(15, 0), time(13, 0))
        db.session.commit()
    db.session.rollback()
    with pytest.raises(IntegrityError):
        _linha(i["oferta"], 1, time(13, 0), time(13, 0))  # iguais
        db.session.commit()
    db.session.rollback()


# --- ON DELETE CASCADE --------------------------------------------------------
def test_cascade_ao_apagar_oferta(app):
    i = _seed()
    _linha(i["oferta"], 0, time(13, 0), time(15, 0))
    _linha(i["oferta"], 2, time(13, 0), time(15, 0))
    db.session.commit()
    assert TurmaCursoHorario.query.count() == 2

    oferta = db.session.get(TurmaCurso, i["oferta"])
    db.session.delete(oferta)
    db.session.commit()
    # CASCADE físico remove as linhas da grade junto com a oferta.
    assert TurmaCursoHorario.query.count() == 0


# --- excluir_turma físico (sequência da rota) ---------------------------------
def test_excluir_turma_fisicoContinua_funcionando_com_grade(app):
    i = _seed()
    _linha(i["oferta"], 0, time(13, 0), time(15, 0))
    _linha(i["oferta"], 2, time(13, 0), time(15, 0))
    db.session.commit()

    # Reproduz exatamente a ordem de delete em massa de `excluir_turma`
    # (registros/turmas.py) para uma turma SEM histórico.
    TurmaCurso.query.filter_by(turma_id=i["turma"]).delete(
        synchronize_session=False
    )
    db.session.query(Turma).filter_by(id=i["turma"]).delete(
        synchronize_session=False
    )
    db.session.commit()

    assert db.session.get(Turma, i["turma"]) is None
    assert TurmaCurso.query.filter_by(turma_id=i["turma"]).count() == 0
    # Grade caiu via CASCADE da FK turma_curso.
    assert TurmaCursoHorario.query.count() == 0


# --- Ordenação do relacionamento ----------------------------------------------
def test_relacionamento_ordena_por_dia(app):
    i = _seed()
    # Insere fora de ordem; a relação deve vir 0->5.
    _linha(i["oferta"], 5, time(13, 0), time(15, 0))
    _linha(i["oferta"], 0, time(9, 0), time(10, 0))
    _linha(i["oferta"], 2, time(9, 0), time(10, 0))
    db.session.commit()
    db.session.expire_all()

    oferta = db.session.get(TurmaCurso, i["oferta"])
    dias = [h.dia_semana for h in oferta.horarios]
    assert dias == [0, 2, 5]
