"""H1-P5 — Serviço `app/services/turma_curso_horario.py` (contrato H2).

Cobre a camada da grade por dia da oferta:
    - `definir_grade`: substitui sem duplicar, rollback atômico (ValueError não
      deixa grade parcial e preserva a anterior), idempotência (reaplicar o
      mesmo conjunto não escreve nada). Desde o H2 recusa grade vazia, domingo
      e dia sem horário completo — os cenários "sem horário" abaixo são
      semeados via modelo direto (tolerância do banco ao legado pré-H2), para
      manter a cobertura dos leitores (`duracao_do_dia`, `grade_uniforme`,
      `resumo_grade`).
    - `duracao_do_dia`: minutos do dia; None p/ dia ausente ou sem horário.
    - `grade_uniforme`: uniforme / dias diferentes / sem horário / mista.
    - `resumo_grade`: os três formatos (uniforme, não uniforme, só dias).
    - `grades_em_lote`: uma única consulta para várias ofertas.

H5a: `sincronizar_projecao_horario` foi removida (a grade é a única fonte de
agenda, sem projeção nas colunas escalares) — os casos que só caracterizavam a
projeção saíram com ela.

Nenhuma função do serviço faz commit — os testes confirmam isso ao não
commitar e ver o estado coerente no flush.
"""
from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import event

from app import db
from app.models import Curso, Turma, TurmaCursoHorario, Unidade, User
from app.services.turma_curso_horario import (
    definir_grade,
    duracao_do_dia,
    grade_da_oferta,
    grade_uniforme,
    grades_em_lote,
    resumo_grade,
)
from config import Config

from _helpers import nova_oferta

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _oferta(**legado):
    unidade = Unidade(nome="U serv", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome="Curso serv", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    turma = Turma(
        nome="Turma serv", unidade_id=unidade.id, ativo=True,
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    # G1/P2 (d6e7f8a9b0c1): oferta exige professor — a semente garante um
    # (email numerado: `_oferta()` pode ser chamada mais de uma vez no teste).
    professor = User(
        name="Prof serv", email=f"prof.serv{db.session.query(User).count() + 1}@x.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    db.session.add(professor)
    db.session.flush()
    campos = dict(dias_semana=None, hora_inicio=None, hora_fim=None)
    campos.update(legado)
    oferta = nova_oferta(
        turma.id, curso.id, unidade.id, programa="P",
        professor_id=professor.id, **campos,
    )
    db.session.commit()
    return oferta


def _semeiar_linhas_legado(oferta, itens):
    """Insere linhas na grade pelo MODELO (não pelo serviço), permitindo os
    formatos tolerados pelo banco mas recusados pelo contrato H2 de
    `definir_grade` (dia sem horário, domingo). Usado para cobrir leitores."""
    for dia, ini, fim in itens:
        db.session.add(TurmaCursoHorario(
            turma_curso_id=oferta.id, dia_semana=dia, hora_inicio=ini, hora_fim=fim,
        ))
    db.session.flush()
    # A relação já carregada não vê o add direto por FK: expira para reler.
    db.session.expire(oferta, ["horarios"])


# --- definir_grade ------------------------------------------------------------
def test_definir_grade_substitui_sem_duplicar(app):
    o = _oferta()
    definir_grade(o, [(0, time(13, 30), time(16, 30)), (2, time(13, 30), time(16, 30))])
    db.session.commit()
    assert [l.dia_semana for l in grade_da_oferta(o)] == [0, 2]

    # Reaplicar outro conjunto substitui por completo (sem deixar rastro).
    definir_grade(o, [(1, time(9, 0), time(10, 0))])
    db.session.commit()
    assert [l.dia_semana for l in grade_da_oferta(o)] == [1]
    assert TurmaCursoHorario.query.count() == 1


def test_definir_grade_idempotencia_reaplicar_mesmo_conjunto(app):
    o = _oferta()
    itens = [(0, time(13, 30), time(16, 30)), (2, time(13, 30), time(16, 30))]
    definir_grade(o, itens)
    db.session.commit()
    primeiro = [(l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(o)]

    definir_grade(o, itens)
    db.session.commit()
    segundo = [(l.dia_semana, l.hora_inicio, l.hora_fim) for l in grade_da_oferta(o)]
    assert primeiro == segundo
    assert TurmaCursoHorario.query.count() == 2  # não duplicou linhas


def test_definir_grade_rollback_atomic_preserva_anterior(app):
    o = _oferta()
    definir_grade(o, [(0, time(13, 30), time(16, 30))])
    db.session.commit()

    with pytest.raises(ValueError):
        # dia válido, mas par incompleto no segundo item -> recusa tudo
        definir_grade(o, [(1, time(9, 0), time(10, 0)), (2, time(9, 0), None)])
    db.session.rollback()

    # grade anterior intacta
    assert [l.dia_semana for l in grade_da_oferta(o)] == [0]


@pytest.mark.parametrize(
    "itens",
    [
        [],                                     # grade vazia (H2)
        [(7, time(9, 0), time(10, 0))],         # dia fora do domínio
        [(-1, time(9, 0), time(10, 0))],        # dia negativo
        [(6, time(9, 0), time(10, 0))],         # domingo (H2)
        [(0, time(9, 0), time(10, 0)), (0, time(11, 0), time(12, 0))],  # duplicata
        [(1, time(9, 0), None)],                # falta fim
        [(1, None, time(9, 0))],                # falta início
        [(1, None, None)],                      # dia sem horário (H2 exige par)
        [(2, time(15, 0), time(13, 0))],        # fim < início
        [(2, time(13, 0), time(13, 0))],        # fim == início
    ],
)
def test_definir_grade_validacoes_levantam_valueerror(app, itens):
    o = _oferta()
    with pytest.raises(ValueError):
        definir_grade(o, itens)


# --- duracao_do_dia -----------------------------------------------------------
def test_duracao_do_dia(app):
    o = _oferta()
    definir_grade(o, [(0, time(13, 30), time(16, 30))])
    _semeiar_linhas_legado(o, [(2, None, None)])  # legado: dia sem horário
    db.session.commit()
    assert duracao_do_dia(o, 0) == 180      # 13:30 -> 16:30
    assert duracao_do_dia(o, 2) is None     # dia sem horário
    assert duracao_do_dia(o, 5) is None     # dia ausente da grade


# --- grade_uniforme -----------------------------------------------------------
def test_grade_uniforme_casos(app):
    # vazia
    o = _oferta()
    assert grade_uniforme(o) is True

    # uniforme com horário
    definir_grade(o, [(0, time(9, 0), time(10, 0)), (2, time(9, 0), time(10, 0))])
    db.session.commit()
    assert grade_uniforme(o) is True

    # sem horário em todos os dias -> uniforme (legado: semeadura via modelo)
    o2 = _oferta()
    _semeiar_linhas_legado(o2, [(1, None, None), (3, None, None)])
    db.session.commit()
    assert grade_uniforme(o2) is True

    # horários diferentes entre dias -> não uniforme
    definir_grade(o, [(0, time(9, 0), time(10, 0)), (1, time(14, 0), time(15, 0))])
    db.session.commit()
    assert grade_uniforme(o) is False

    # mista: um dia com horário, outro sem -> não uniforme (legado)
    o3 = _oferta()
    _semeiar_linhas_legado(o3, [(0, time(9, 0), time(10, 0)), (1, None, None)])
    db.session.commit()
    assert grade_uniforme(o3) is False


# --- resumo_grade -------------------------------------------------------------
def test_resumo_grade_formatos(app):
    o = _oferta()
    assert resumo_grade(o) == ""

    # uniforme com horário -> dias + par único
    definir_grade(o, [(0, time(13, 30), time(16, 30)), (2, time(13, 30), time(16, 30))])
    db.session.commit()
    assert resumo_grade(o) == "Seg, Qua · 13:30-16:30"

    # não uniforme -> um segmento por dia
    definir_grade(o, [(0, time(13, 30), time(16, 30)), (1, time(13, 0), time(15, 0))])
    db.session.commit()
    assert resumo_grade(o) == "Seg 13:30-16:30 · Ter 13:00-15:00"

    # sem horário -> só os dias (legado: semeadura via modelo)
    o2 = _oferta()
    _semeiar_linhas_legado(o2, [(0, None, None), (3, None, None)])
    db.session.commit()
    assert resumo_grade(o2) == "Seg, Qui"


# --- sincronizar_projecao_horario (removida no H5a) ---------------------------
# Os quatro casos antigos (`test_projecao_*`) caracterizavam apenas a projeção
# nas colunas escalares de agenda. Com a projeção removida (a grade é a única
# fonte), eles deixam de ter contrato a defender e saíram junto.


def test_definir_grade_recusa_domingo(app):
    o = _oferta()
    definir_grade(o, [(0, time(9, 0), time(10, 0))])
    db.session.commit()
    with pytest.raises(ValueError, match="[Dd]omingo"):
        definir_grade(o, [(6, time(9, 0), time(10, 0))])
    # grade anterior intacta
    assert [l.dia_semana for l in grade_da_oferta(o)] == [0]


def test_definir_grade_idempotencia_nao_escreve(app):
    """Mesma grade de novo = zero DELETE/INSERT na tabela (no-op real)."""
    o = _oferta()
    itens = [(0, time(9, 0), time(10, 0)), (2, time(9, 0), time(10, 0))]
    definir_grade(o, itens)
    db.session.commit()
    ids_antes = sorted(l.id for l in o.horarios)

    cont = {"escrita": 0}

    def _antes(conn, cur, statement, params, context, executemany):
        if "turma_curso_horario" in str(statement).lower() and any(
            k in str(statement).upper() for k in ("INSERT", "DELETE", "UPDATE")
        ):
            cont["escrita"] += 1

    event.listen(db.engine, "before_cursor_execute", _antes)
    try:
        definir_grade(o, itens)
        db.session.commit()
    finally:
        event.remove(db.engine, "before_cursor_execute", _antes)
    assert cont["escrita"] == 0
    assert sorted(l.id for l in o.horarios) == ids_antes


# --- grades_em_lote (uma consulta, sem N+1) -----------------------------------
def test_grades_em_lote_uma_consulta(app):
    o1 = _oferta()
    definir_grade(o1, [(0, time(9, 0), time(10, 0)), (2, time(9, 0), time(10, 0))])
    db.session.commit()

    # segunda oferta na mesma estrutura
    curso2 = Curso(nome="Curso serv 2", unidade_id=o1.unidade_id, ativo=True)
    db.session.add(curso2)
    db.session.flush()
    o2 = nova_oferta(
        o1.turma_id, curso2.id, o1.unidade_id, programa="P2",
        professor_id=o1.professor_id,
    )
    definir_grade(o2, [(1, time(14, 0), time(15, 0))])
    db.session.commit()

    # Ids resolvidos ANTES do listener: acessar atributo expirado pós-commit
    # dispararia o selectin da relação e contaria como consulta extra.
    id1, id2 = o1.id, o2.id
    cont = {"n": 0}

    def _antes(conn, cur, statement, params, context, executemany):
        if "turma_curso_horario" in str(statement):
            cont["n"] += 1

    event.listen(db.engine, "before_cursor_execute", _antes)
    try:
        lotes = grades_em_lote([id1, id2])
    finally:
        event.remove(db.engine, "before_cursor_execute", _antes)

    assert sorted(l.dia_semana for l in lotes[id1]) == [0, 2]
    assert sorted(l.dia_semana for l in lotes[id2]) == [1]
    # UMA única consulta à tabela para as duas ofertas.
    assert cont["n"] == 1


def test_grades_em_lote_oferta_sem_grade_vem_lista_vazia(app):
    o = _oferta()
    lotes = grades_em_lote([o.id])
    assert lotes[o.id] == []
    assert grades_em_lote([]) == {}
