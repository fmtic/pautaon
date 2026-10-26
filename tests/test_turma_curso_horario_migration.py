"""H1-P5 — Funções puras da migration `5730d7c594ba` sobre sementes SQLite.

Executa os blocos reaproveitáveis da migration (checagens, backfill e guarda
de downgrade) diretamente contra o bind de um SQLite em-memory criado via
``db.create_all()``, com sementes montadas à mão. Cobre:

    - herança campo a campo (oferta -> turma) via COALESCE;
    - token com acento e sem acento;
    - (i) token desconhecido, (ii) duplicata, (iii) par incompleto
      pós-COALESCE, (iv) fim <= início, (v) horário sem dias;
    - (vi) informativo não bloqueante;
    - oferta sem dias efetivos não gera linhas; oferta inativa é incluída;
    - idempotência (duas execuções do backfill);
    - downgrade recusado com grade não uniforme.

A migration em si (DDL via ``op``) é exercida no ensaio A-E do P6; aqui só as
funções que recebem ``bind`` como parâmetro.
"""
from __future__ import annotations

import importlib.util
from datetime import date, time
from pathlib import Path

import pytest

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, TurmaCursoHorario, Unidade
from config import Config

from _helpers import nova_oferta

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)

# Carrega o módulo da migration pelo caminho (ele não importa nada da app).
_CAMINHO = (
    Path(__file__).resolve().parents[1]
    / "migrations" / "versions"
    / "5730d7c594ba_horario_por_dia_na_oferta_h1.py"
)
_espec = importlib.util.spec_from_file_location("mig_h1_5730d7c594ba", _CAMINHO)
mig = importlib.util.module_from_spec(_espec)
_espec.loader.exec_module(mig)


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
        db.create_all()  # inclui turma_curso_horario (modelo P2)
        yield test_app
        db.session.remove()
        db.drop_all()


def _ambiente():
    """Unidade + curso + turma legada; devolve ids para montar ofertas."""
    unidade = Unidade(nome="U mig", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome="Curso mig", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    turma = Turma(
        nome="Turma mig", unidade_id=unidade.id, ativo=True,
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    db.session.flush()
    return {"unidade": unidade.id, "curso": curso.id, "turma": turma.id}


def _oferta_com_curso(i, nome_curso=None, **campos):
    curso_id = i["curso"]
    if nome_curso:  # segunda oferta na mesma turma precisa de outro curso
        curso = Curso(nome=nome_curso, unidade_id=i["unidade"], ativo=True)
        db.session.add(curso)
        db.session.flush()
        curso_id = curso.id
    oferta = nova_oferta(i["turma"], curso_id, i["unidade"], **campos)
    db.session.commit()
    return oferta


def _linhas(oferta_id):
    return (
        TurmaCursoHorario.query
        .filter_by(turma_curso_id=oferta_id)
        .order_by(TurmaCursoHorario.dia_semana)
        .all()
    )


# --- backfill: herança campo a campo ------------------------------------------
def test_backfill_heranca_campo_a_campo(app):
    i = _ambiente()
    turma = db.session.get(Turma, i["turma"])
    turma.dias_semana = "Segunda, Terça"
    turma.hora_inicio = time(9, 0)
    turma.hora_fim = time(16, 0)
    # Oferta: próprios dias NULL; início próprio; fim herdado da turma.
    oferta = _oferta_com_curso(i, dias_semana=None, hora_inicio=time(14, 0),
                               hora_fim=None)
    db.session.commit()

    mig._checar_antes_de_alterar(db.session.connection())
    inseridas = mig._executar_backfill(db.session.connection())
    db.session.commit()

    assert inseridas == 2
    linhas = _linhas(oferta.id)
    assert [l.dia_semana for l in linhas] == [0, 1]
    # INÍCO da oferta (14:00), FIM da turma (16:00) — COALESCE campo a campo.
    assert all(l.hora_inicio == time(14, 0) for l in linhas)
    assert all(l.hora_fim == time(16, 0) for l in linhas)


# --- backfill: com e sem acento ------------------------------------------------
def test_backfill_acento_e_sem_acento(app):
    i = _ambiente()
    o1 = _oferta_com_curso(i, dias_semana="Terça, Sábado",
                           hora_inicio=time(13, 30), hora_fim=time(16, 30))
    o2 = _oferta_com_curso(i, nome_curso="Curso mig 2",
                           dias_semana="Terca, Sabado")  # sem acento
    db.session.commit()

    mig._checar_antes_de_alterar(db.session.connection())
    mig._executar_backfill(db.session.connection())
    db.session.commit()

    assert [l.dia_semana for l in _linhas(o1.id)] == [1, 5]
    assert [l.dia_semana for l in _linhas(o2.id)] == [1, 5]
    # Dias sem horário -> par NULL nas duas linhas.
    assert all(l.hora_inicio is None and l.hora_fim is None
               for l in _linhas(o2.id))


# --- pré-checagens bloqueantes (i)-(v) ------------------------------------------
def _espera_erro(i, trecho, **campos):
    nome = campos.pop("_nome", None)
    kwargs = dict(dias_semana=None, hora_inicio=None, hora_fim=None)
    kwargs.update(campos)
    _oferta_com_curso(i, nome_curso=nome, **kwargs)
    db.session.commit()
    with pytest.raises(RuntimeError) as exc:
        mig._checar_antes_de_alterar(db.session.connection())
    assert trecho in str(exc.value)


def test_check_i_token_desconhecido(app):
    i = _ambiente()
    _espera_erro(i, "(i)", dias_semana="Fulgora")


def test_check_ii_dia_duplicado_apos_normalizacao(app):
    i = _ambiente()
    # "seg." e "Segunda" viram o mesmo dia após o conversor embutido.
    _espera_erro(i, "(ii)", dias_semana="Seg., Segunda")


def test_check_iii_par_incompleto_pos_coalesce(app):
    i = _ambiente()
    turma = db.session.get(Turma, i["turma"])
    turma.hora_inicio = time(9, 0)  # nada para herdar do lado do fim
    oferta = _oferta_com_curso(i, dias_semana="Segunda",
                               hora_inicio=time(14, 0), hora_fim=None)
    db.session.commit()
    with pytest.raises(RuntimeError) as exc:
        mig._checar_antes_de_alterar(db.session.connection())
    assert "(iii)" in str(exc.value)


def test_check_iv_fim_menor_ou_igual(app):
    i = _ambiente()
    o1 = _oferta_com_curso(i, dias_semana="Segunda",
                           hora_inicio=time(15, 0), hora_fim=time(13, 0))
    o2 = _oferta_com_curso(i, nome_curso="Curso mig 2", dias_semana="Terça",
                           hora_inicio=time(13, 0), hora_fim=time(13, 0))
    db.session.commit()
    with pytest.raises(RuntimeError) as exc:
        mig._checar_antes_de_alterar(db.session.connection())
    msg = str(exc.value)
    assert msg.count("(iv)") == 2  # fim < início E fim == início, ambos listados
    assert str(o1.id) in msg and str(o2.id) in msg


def test_check_v_horario_sem_dias(app):
    i = _ambiente()
    _espera_erro(i, "(v)", dias_semana=None,
                 hora_inicio=time(9, 0), hora_fim=time(10, 0))


def test_erro_acumula_todos_os_itens_em_um_runtimeerror(app):
    i = _ambiente()
    _oferta_com_curso(i, dias_semana="Fulgora")
    _oferta_com_curso(i, nome_curso="Curso mig 2", dias_semana="Segunda",
                      hora_inicio=time(15, 0), hora_fim=time(13, 0))
    db.session.commit()
    with pytest.raises(RuntimeError) as exc:
        mig._checar_antes_de_alterar(db.session.connection())
    msg = str(exc.value)
    assert "(i)" in msg and "(iv)" in msg  # padrão D5.5: um único erro, tudo listado


# --- informativo (vi) não bloqueante --------------------------------------------
def test_vi_informativo_nao_bloqueia(app):
    i = _ambiente()
    oferta = _oferta_com_curso(i, dias_semana="Quarta")  # ativa, dias, sem hora
    db.session.commit()
    mig._checar_antes_de_alterar(db.session.connection())  # não levanta
    mig._executar_backfill(db.session.connection())
    db.session.commit()
    linhas = _linhas(oferta.id)
    assert [l.dia_semana for l in linhas] == [2]  # Quarta = date.weekday() 2
    assert linhas[0].hora_inicio is None and linhas[0].hora_fim is None


# --- ofertas sem dias / inativas --------------------------------------------------
def test_oferta_sem_dias_nao_gera_linhas(app):
    i = _ambiente()
    oferta = _oferta_com_curso(i)  # tudo NULL na oferta e na turma
    db.session.commit()
    assert mig._executar_backfill(db.session.connection()) == 0
    assert _linhas(oferta.id) == []


def test_backfill_inclui_oferta_inativa(app):
    i = _ambiente()
    oferta = _oferta_com_curso(i, ativo=False, dias_semana="Sexta",
                               hora_inicio=time(19, 0), hora_fim=time(22, 0))
    db.session.commit()
    mig._executar_backfill(db.session.connection())
    db.session.commit()
    linhas = _linhas(oferta.id)
    assert [l.dia_semana for l in linhas] == [4]
    assert linhas[0].hora_inicio == time(19, 0)


# --- idempotência ------------------------------------------------------------------
def test_backfill_duas_vezes_nao_duplica(app):
    i = _ambiente()
    oferta = _oferta_com_curso(i, dias_semana="Segunda, Quarta",
                               hora_inicio=time(9, 0), hora_fim=time(10, 0))
    db.session.commit()
    primeira = mig._executar_backfill(db.session.connection())
    db.session.commit()
    segunda = mig._executar_backfill(db.session.connection())
    db.session.commit()
    assert primeira == 2
    assert segunda == 0
    assert [l.dia_semana for l in _linhas(oferta.id)] == [0, 2]  # Seg, Qua
    assert TurmaCursoHorario.query.count() == 2


# --- downgrade: guarda de grade não uniforme ----------------------------------------
def test_downgrade_recusa_grade_nao_uniforme(app):
    i = _ambiente()
    oferta = _oferta_com_curso(i, dias_semana="Segunda, Terça",
                               hora_inicio=time(9, 0), hora_fim=time(10, 0))
    db.session.commit()
    mig._executar_backfill(db.session.connection())
    db.session.commit()
    assert mig._ofertas_grade_nao_uniforme(db.session.connection()) == []

    # alguém editou a grade depois: terça passa a ter outro par.
    linha_ter = _linhas(oferta.id)[1]
    linha_ter.hora_inicio = time(14, 0)
    linha_ter.hora_fim = time(15, 0)
    db.session.commit()

    assert mig._ofertas_grade_nao_uniforme(db.session.connection()) == [oferta.id]
    with pytest.raises(RuntimeError) as exc:
        mig._guardar_downgrade(db.session.connection())
    assert "NÃO uniforme" in str(exc.value)
    assert str(oferta.id) in str(exc.value)


def test_downgrade_permite_grade_uniforme(app):
    i = _ambiente()
    oferta = _oferta_com_curso(i, dias_semana="Segunda, Terça",
                               hora_inicio=time(9, 0), hora_fim=time(10, 0))
    db.session.commit()
    mig._executar_backfill(db.session.connection())
    db.session.commit()
    mig._guardar_downgrade(db.session.connection())  # não levanta
