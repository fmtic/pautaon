"""H3a-P4 — Leitores de agenda passam a ler a GRADE (`datas_aula_oferta`).

Cobre o que a ETAPA H3a exige da migração dos leitores de datas de aula:

    - weekdays 0–5: as datas saem EXATAMENTE dos dias da grade;
    - vigência: janela [data_inicio, data_fim] da oferta, com herança da turma
      quando NULL; sem início OU fim definíveis → sem datas;
    - dias bloqueados: `blocked` ('YYYY-MM-DD') continua descontado;
    - grade NÃO uniforme: dias da OFERTA (grade) ≠ dias antigos da TURMA — a
      leitura segue a grade, não o CSV da turma;
    - oferta SEM linhas de grade: cai no CSV projetado (fallback legado) e, se
      nenhum dos dois define dias, retorna [];
    - N+1: `dias_por_ofertas` carrega dias de K ofertas em UMA consulta;
    - equivalência: para uma grade uniforme que espelha o CSV, as datas geradas
      pela grade são IDÊNTICAS às que o caminho antigo (parse de CSV) gerava.
"""
from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, Unidade
from app.services.turma_curso import datas_aula_oferta, datas_esperadas_oferta
from app.services.turma_curso_horario import (
    definir_grade,
    dias_da_oferta,
    dias_da_turma,
    dias_por_ofertas,
)
from config import Config

from _helpers import nova_oferta

# Semana de referência: seg 02/03 ... dom 08/03/2026.
SEG = date(2026, 3, 2)
TER = date(2026, 3, 3)
QUA = date(2026, 3, 4)
QUI = date(2026, 3, 5)
SEX = date(2026, 3, 6)
SAB = date(2026, 3, 7)
DOM = date(2026, 3, 8)
FIM_SEMANA = DOM  # data_fim cobre toda a semana


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


def _h(dia: int) -> tuple[time, time]:
    return (time(9 + dia), time(10 + dia))


def _setup(*, grade=None, turma_dias="Segunda", oferta_ini=SEG, oferta_fim=FIM_SEMANA,
           turma_ini=SEG, turma_fim=FIM_SEMANA, nome="U"):
    """Unidade + curso + turma (com `turma_dias`) + oferta com `grade`.

    `grade` é uma lista de (dia, ini, fim) aplicada via `definir_grade` (ou
    None para deixar a oferta sem linhas). Retorna a oferta.
    """
    unidade = Unidade(nome=nome, ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome=f"Curso {nome}", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    turma = Turma(
        nome=f"Turma {nome}", unidade_id=unidade.id, ativo=True,
        data_inicio=turma_ini, data_fim=turma_fim, dias_semana=turma_dias,
        hora_inicio=time(9), hora_fim=time(10),
    )
    db.session.add(turma)
    db.session.flush()
    oferta = nova_oferta(
        turma.id, curso.id, unidade.id,
        data_inicio=oferta_ini, data_fim=oferta_fim,
    )
    if grade:
        definir_grade(oferta, grade)
    db.session.commit()
    return oferta


# --- weekdays 0–5 -------------------------------------------------------------
def test_grade_de_um_dia_gera_so_aquelos_dias_da_semana(app):
    o = _setup(grade=[(0, *_h(0))])  # só segunda
    assert datas_aula_oferta(o) == [SEG]


@pytest.mark.parametrize(
    "dia,esperada",
    [(0, SEG), (1, TER), (2, QUA), (3, QUI), (4, SEX), (5, SAB)],
)
def test_cada_weekday_de_segunda_a_sabado_e_respeitado(app, dia, esperada):
    o = _setup(grade=[(dia, *_h(dia))], nome=f"W{dia}")
    assert datas_aula_oferta(o) == [esperada]


def test_grade_com_varios_dias_produz_todas_as_ocorrencias(app):
    o = _setup(grade=[(1, *_h(1)), (3, *_h(3))], nome="Multi")  # ter + qui
    assert datas_aula_oferta(o) == [TER, QUI]


# --- vigência -----------------------------------------------------------------
def test_vigencia_da_oferta_delimita_as_datas(app):
    # Oferta só até quarta: ter e qui, mas qui (05) entra; sex (06) fica fora.
    o = _setup(grade=[(1, *_h(1)), (3, *_h(3)), (4, *_h(4))],
               oferta_fim=QUI, nome="Vig1")
    assert datas_aula_oferta(o) == [TER, QUI]


def test_vigencia_nula_herda_janela_da_turma(app):
    o = _setup(grade=[(0, *_h(0))], oferta_ini=None, oferta_fim=None,
               nome="HerdaVig")
    # turma cobre SEG..DOM; segunda cai em SEG.
    assert datas_aula_oferta(o) == [SEG]


def test_sem_inicio_ou_fim_definiveis_nao_gera_datas(app):
    o = _setup(grade=[(0, *_h(0))], oferta_ini=None, oferta_fim=None,
               turma_ini=None, turma_fim=None, nome="SemJanela")
    assert datas_aula_oferta(o) == []


def test_limite_corta_na_data_pedida(app):
    o = _setup(grade=[(0, *_h(0)), (2, *_h(2)), (4, *_h(4))], nome="Limite")
    # SEG, QUA, SEX. `limite` é INCLUSIVO (o laço usa `<=`, como em
    # datas_esperadas_oferta que inclui `hoje`). limite=QUI -> corta antes de SEX.
    assert datas_aula_oferta(o, limite=QUI) == [SEG, QUA]
    # limite >= SEX inclui SEX (capped em data_fim da oferta).
    assert datas_aula_oferta(o, limite=DOM) == [SEG, QUA, SEX]


# --- dias bloqueados ----------------------------------------------------------
def test_dias_bloqueados_sao_descontados(app):
    o = _setup(grade=[(1, *_h(1)), (3, *_h(3))], nome="Blocked")
    blocked = {TER.strftime("%Y-%m-%d")}
    assert datas_aula_oferta(o, blocked=blocked) == [QUI]


def test_datas_esperadas_oferta_usma_grade_e_desconta_bloqueios(app):
    o = _setup(grade=[(1, *_h(1)), (3, *_h(3))], nome="Esperadas")
    # hoje = SEX: ter e qui já passaram; sem bloqueio.
    assert datas_esperadas_oferta(o, hoje=SEX) == [TER, QUI]
    assert datas_esperadas_oferta(o, hoje=SEX, blocked={QUI.strftime("%Y-%m-%d")}) == [TER]


# --- grade NÃO uniforme: dias da oferta mandam, não o CSV da turma ------------
def test_grade_nao_uniforme_le_dias_da_oferta_nao_da_turma(app):
    # turma legada diz "Segunda"; grade real é terça+quinta.
    o = _setup(grade=[(1, *_h(1)), (3, *_h(3))], turma_dias="Segunda",
               nome="NaoUnif")
    datas = datas_aula_oferta(o)
    assert SEG not in datas          # dia antigo da turma NÃO aparece
    assert datas == [TER, QUI]       # o que a grade define


# --- oferta sem linhas de grade (fallback legado) -----------------------------
def test_oferta_sem_grade_cai_no_csv_projetado(app):
    # Sem definir_grade, mas com projeção CSV na oferta (espelho legado).
    o = _setup(grade=None, nome="SoCSV")
    o.dias_semana = "Quarta, Sexta"
    db.session.commit()
    assert datas_aula_oferta(o) == [QUA, SEX]


def test_oferta_sem_grade_nem_csv_nao_gera_datas(app):
    o = _setup(grade=None, turma_dias=None, nome="Nada")
    o.dias_semana = None
    db.session.commit()
    assert datas_aula_oferta(o) == []


# --- serviço de dias (P2) -----------------------------------------------------
def test_dias_da_oferta_le_grade_em_consulta(app):
    o = _setup(grade=[(1, *_h(1)), (5, *_h(5))], nome="DiasOf")
    assert dias_da_oferta(o.id) == {1, 5}


def test_dias_da_turma_e_uniao_das_ofertas_ativas(app):
    # Duas ofertas ativas na mesma turma: dias 1 e 3 → união {1, 3}.
    o1 = _setup(grade=[(1, *_h(1))], nome="Un1")
    curso2 = Curso(nome="C2 uniao", unidade_id=o1.unidade_id, ativo=True)
    db.session.add(curso2)
    db.session.flush()
    o2 = nova_oferta(o1.turma_id, curso2.id, o1.unidade_id)
    definir_grade(o2, [(3, *_h(3))])
    db.session.commit()
    assert dias_da_turma(o1.turma_id) == {1, 3}


def test_dias_da_turma_ignora_ofertas_inativas(app):
    o1 = _setup(grade=[(1, *_h(1))], nome="Inat1")
    curso2 = Curso(nome="C2 inat", unidade_id=o1.unidade_id, ativo=True)
    db.session.add(curso2)
    db.session.flush()
    o2 = nova_oferta(o1.turma_id, curso2.id, o1.unidade_id, ativo=False)
    definir_grade(o2, [(3, *_h(3))])
    db.session.commit()
    assert dias_da_turma(o1.turma_id) == {1}


# --- sem N+1: várias ofertas em UMA consulta ----------------------------------
def test_dias_por_ofertas_carrega_em_uma_consulta(app):
    ids = []
    esperado = {}
    for i in range(5):
        o = _setup(grade=[(i, *_h(i))], nome=f"Lote{i}")
        ids.append(o.id)
        esperado[o.id] = {i}

    stmts: list[str] = []

    from sqlalchemy import event

    @event.listens_for(db.engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        if "turma_curso_horario" in statement.lower():
            stmts.append(statement)

    try:
        resultado = dias_por_ofertas(ids)
    finally:
        event.remove(db.engine, "before_cursor_execute", _count)

    # Toda oferta aparece no resultado, com seus dias.
    assert resultado == esperado
    # UMA única statement de leitura da grade para as 5 ofertas (sem N+1).
    assert len(stmts) == 1, stmts


# --- equivalência: grade == caminho antigo (CSV) ------------------------------
def _datas_caminho_antigo(dias_csv, inicio, fim, blocked):
    """Reimplementa o laço LEGADO (antes do H3a): parse de CSV em minúsculas e
    comparação por nome — para provar que a grade reproduz as mesmas datas."""
    nomes = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
    dias = {d.strip().lower() for d in (dias_csv or "").split(",") if d.strip()}
    if not dias:
        return []
    out = []
    atual = inicio
    while atual <= fim:
        nome = nomes[atual.weekday()]
        bate = nome in dias or f"{nome}-feira" in dias
        if bate and atual.strftime("%Y-%m-%d") not in (blocked or set()):
            out.append(atual)
        atual += timedelta(days=1)
    return out


@pytest.mark.parametrize("dias_csv,dias_grade", [
    ("Segunda", [0]),
    ("Terça, Quinta", [1, 3]),
    ("Segunda, Quarta, Sexta", [0, 2, 4]),
    ("Sábado", [5]),
])
def test_equivalencia_grade_vs_caminho_antigo(app, dias_csv, dias_grade):
    o = _setup(grade=[(d, *_h(d)) for d in dias_grade], turma_dias=dias_csv,
               nome=f"Eq{dias_grade[0]}")
    blocked = {QUI.strftime("%Y-%m-%d")}
    novas = datas_aula_oferta(o, blocked=blocked)
    antigas = _datas_caminho_antigo(dias_csv, SEG, FIM_SEMANA, blocked)
    assert novas == antigas
