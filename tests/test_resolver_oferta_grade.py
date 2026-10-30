"""H3a-P4 — `resolver_oferta_lancamento` valida o dia pela GRADE (weekday 0–5).

A migração do leitor de validação de lançamento (`_data_bate_dias_semana` agora
lê a grade, não o CSV) exige provar que:

    - com oferta explicitamente escolhida, a data é aceita se cai num dia da
      GRADE e recusada se não cai (mensagem citando a oferta);
    - a **regra da oferta única** continua ÍNTEGRA: turma com exatamente 1
      oferta ativa é escolhida automaticamente **sem** validação de vigência/
      dia/tema (comportamento anterior, não alterado pelo H3a);
    - 2+ ofertas ativas sem escolha → ValueError pedindo o curso;
    - oferta inativa / de outra turma → ValueError.
"""
from __future__ import annotations

from datetime import date, time

import pytest

from app import db
from app.models import Curso, Turma, Unidade
from app.services.turma_curso import resolver_oferta_lancamento
from app.services.turma_curso_horario import definir_grade
from config import Config

from _helpers import nova_oferta, professor_semente

SEG = date(2026, 3, 2)
TER = date(2026, 3, 3)
QUI = date(2026, 3, 5)
FIM = date(2026, 3, 8)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _h(dia: int) -> tuple[time, time]:
    return (time(9 + dia), time(10 + dia))


def _turma():
    unidade = Unidade(nome="U res", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    turma = Turma(nome="T res", unidade_id=unidade.id, ativo=True, curso_id=None)
    db.session.add(turma)
    db.session.flush()
    return unidade, turma


def _oferta(unidade, turma, nome_curso, grade, *, ativo=True,
            ini=SEG, fim=FIM):
    curso = Curso(nome=nome_curso, unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    oferta = nova_oferta(
        turma.id, curso.id, unidade.id,
        # G1/P2 (d6e7f8a9b0c1): oferta exige professor — semente compartilhada.
        professor_id=professor_semente(unidade.id, email="prof.res@x.com",
                                       nome="Prof res").id,
        ativo=ativo, data_inicio=ini, data_fim=fim,
    )
    definir_grade(oferta, grade)
    db.session.commit()
    return oferta


# --- oferta escolhida: dia lido da grade --------------------------------------
def test_data_em_dia_da_grade_e_aceita(app):
    unidade, turma = _turma()
    o = _oferta(unidade, turma, "Natação", [(1, *_h(1)), (3, *_h(3))])
    resolvida = resolver_oferta_lancamento(turma.id, TER, turma_curso_id=o.id)
    assert resolvida.id == o.id
    assert resolver_oferta_lancamento(turma.id, QUI, turma_curso_id=o.id).id == o.id


def test_data_fora_da_grade_e_recusada(app):
    unidade, turma = _turma()
    o = _oferta(unidade, turma, "Natação", [(1, *_h(1)), (3, *_h(3))])
    # SEG (0) não está na grade {ter, qui}.
    with pytest.raises(ValueError, match="não cai em um dia de aula"):
        resolver_oferta_lancamento(turma.id, SEG, turma_curso_id=o.id)


def test_domingo_nunca_bate_grade_valida(app):
    # Grade só dias úteis; domingo (weekday 6) é recusado pelo leitor.
    unidade, turma = _turma()
    o = _oferta(unidade, turma, "Natação", [(0, *_h(0))])
    dom = date(2026, 3, 8)
    assert dom.weekday() == 6
    with pytest.raises(ValueError, match="não cai em um dia de aula"):
        resolver_oferta_lancamento(turma.id, dom, turma_curso_id=o.id)


# --- regra da oferta única preservada (sem validação extra) -------------------
def test_oferta_unica_escolhida_sem_validar_dia_ou_vigencia(app):
    # Exatamente 1 oferta ativa: escolhida automaticamente MESMO com data fora
    # da grade e fora da vigência (comportamento anterior, inalterado no H3a).
    unidade, turma = _turma()
    o = _oferta(unidade, turma, "Natação", [(1, *_h(1))], ini=date(2026, 6, 1),
                fim=date(2026, 6, 30))
    resolvida = resolver_oferta_lancamento(turma.id, SEG)  # SEG fora de jun/fora da grade
    assert resolvida is not None and resolvida.id == o.id


# --- 2+ ofertas: escolha obrigatória ------------------------------------------
def test_duas_ofertas_sem_escolha_exigem_curso(app):
    unidade, turma = _turma()
    _oferta(unidade, turma, "Natação", [(1, *_h(1))])
    _oferta(unidade, turma, "Judô", [(3, *_h(3))])
    with pytest.raises(ValueError, match="Selecione o curso"):
        resolver_oferta_lancamento(turma.id, TER)


def test_duas_ofertas_com_escolha_valida_pela_grade(app):
    unidade, turma = _turma()
    o_nat = _oferta(unidade, turma, "Natação", [(1, *_h(1))])
    _oferta(unidade, turma, "Judô", [(3, *_h(3))])
    assert resolver_oferta_lancamento(turma.id, TER, turma_curso_id=o_nat.id).id == o_nat.id
    # TER não está na grade do Judô → recusa.
    o_judo = Curso.query.filter_by(nome="Judô").first().ofertas_turma[0]
    with pytest.raises(ValueError, match="não cai em um dia de aula"):
        resolver_oferta_lancamento(turma.id, TER, turma_curso_id=o_judo.id)


# --- ofertas inativas / de outra turma ----------------------------------------
def test_oferta_inativa_e_recusada(app):
    unidade, turma = _turma()
    o = _oferta(unidade, turma, "Natação", [(1, *_h(1))], ativo=False)
    with pytest.raises(ValueError, match="desativada"):
        resolver_oferta_lancamento(turma.id, TER, turma_curso_id=o.id)


def test_oferta_de_outra_turma_e_recusada(app):
    unidade, turma = _turma()
    o = _oferta(unidade, turma, "Natação", [(1, *_h(1))])
    outra_unidade, outra_turma = _turma()
    with pytest.raises(ValueError, match="não pertence a esta turma"):
        resolver_oferta_lancamento(outra_turma.id, TER, turma_curso_id=o.id)
