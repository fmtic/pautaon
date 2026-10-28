"""H5b — testes das migrations A (CHECK 0–5) e B (DROP das 6 colunas).

As funções de checagem/DDL são exercitadas diretamente contra o bind SQLite
(mesmo padrão do teste da migration H1), sem depender de contexto Alembic.
O ensaio no Postgres cobre o `upgrade()`/`downgrade()` completos.
"""
from __future__ import annotations

import importlib.util
from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, TurmaCursoHorario, Unidade
from app.services.turma_curso_horario import definir_grade
from config import Config

from _helpers import nova_oferta

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)
RAIZ = Path(__file__).resolve().parents[1]


def _carregar(nome: str, arquivo: str):
    espec = importlib.util.spec_from_file_location(nome, RAIZ / "migrations" / "versions" / arquivo)
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


mig_a = _carregar("mig_h5b_a", "7c1d2e3f4a5b_h5b_check_dia_0_5.py")
mig_b = _carregar("mig_h5b_b", "8d2e3f4a5b6c_h5b_drop_colunas_agenda.py")

COLUNAS = {
    "dias_semana": "VARCHAR(80)",
    "hora_inicio": "TIME",
    "hora_fim": "TIME",
}


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


def _seed(*, ofertas=1):
    unidade = Unidade(nome="U H5b", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    periodo = None
    curso = Curso(nome="Curso H5b", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    turma = Turma(
        nome="Turma H5b", unidade_id=unidade.id, ativo=True,
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    db.session.flush()
    ofertas_obj = []
    for i in range(ofertas):
        c = curso
        if i:
            c = Curso(nome=f"Curso H5b {i + 1}", unidade_id=unidade.id, ativo=True)
            db.session.add(c)
            db.session.flush()
        ofertas_obj.append(nova_oferta(
            turma.id, c.id, unidade.id, principal=(i == 0), programa="P",
        ))
    db.session.flush()
    return {
        "unidade": unidade.id, "curso": curso.id, "turma": turma.id,
        "ofertas": ofertas_obj, "periodo": periodo,
    }


def _garantir_colunas_legadas():
    """Simula o schema pré-H5b (colunas escalares ainda existentes).

    Inspeciona pela conexão da sessão (não pelo Engine): no SQLite em memória
    o ``StaticPool`` compartilha a conexão e a inspeção pelo Engine abriria
    uma transação paralela que desfaria o flush pendente da semente.
    """
    for tabela in ("turma", "turma_curso"):
        existentes = {
            c["name"]
            for c in inspect(db.session.connection()).get_columns(tabela)
        }
        for nome, tipo in COLUNAS.items():
            if nome not in existentes:
                db.session.execute(
                    text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")
                )
    db.session.commit()


def _colunas(tabela):
    return {
        c["name"] for c in inspect(db.session.connection()).get_columns(tabela)
    }


def _aplicar_drop_b():
    bind = db.session.connection()
    mig_b._checar_ofertas_sem_grade(bind)
    mig_b._dropar_colunas(bind)
    db.session.commit()


def _aplicar_downgrade_b():
    bind = db.session.connection()
    mig_b._adicionar_colunas(bind)
    mig_b._repopular_projecao(bind)
    db.session.commit()


def _hora(valor):
    """Normaliza TIME para ``HH:MM:SS`` (SQLite devolve texto com microssegundos)."""
    if valor is None:
        return None
    if hasattr(valor, "strftime"):
        return valor.strftime("%H:%M:%S")
    return str(valor)[:8]


def _linhas_oferta(oferta_id):
    return {
        "dias": db.session.execute(
            text("SELECT dias_semana FROM turma_curso WHERE id = :i"), {"i": oferta_id}
        ).scalar(),
        "ini": _hora(db.session.execute(
            text("SELECT hora_inicio FROM turma_curso WHERE id = :i"), {"i": oferta_id}
        ).scalar()),
        "fim": _hora(db.session.execute(
            text("SELECT hora_fim FROM turma_curso WHERE id = :i"), {"i": oferta_id}
        ).scalar()),
    }


def _linha_turma(turma_id):
    return {
        "dias": db.session.execute(
            text("SELECT dias_semana FROM turma WHERE id = :i"), {"i": turma_id}
        ).scalar(),
        "ini": _hora(db.session.execute(
            text("SELECT hora_inicio FROM turma WHERE id = :i"), {"i": turma_id}
        ).scalar()),
        "fim": _hora(db.session.execute(
            text("SELECT hora_fim FROM turma WHERE id = :i"), {"i": turma_id}
        ).scalar()),
    }


# ---------------------------------------------------------------------------
# Migration A — CHECK ck_tch_dia 0–5
# ---------------------------------------------------------------------------
def test_a_recusa_dia_6_listando_ids(app):
    i = _seed()
    definir_grade(i["ofertas"][0], [(0, time(8), time(10))])
    db.session.execute(text("PRAGMA ignore_check_constraints = ON"))
    db.session.execute(
        text(
            "INSERT INTO turma_curso_horario "
            "(turma_curso_id, dia_semana, hora_inicio, hora_fim) "
            "VALUES (:o, 6, '08:00:00', '09:00:00')"
        ),
        {"o": i["ofertas"][0].id},
    )
    db.session.flush()
    with pytest.raises(RuntimeError) as exc:
        mig_a._checar_dia_6(db.session.connection())
    assert "dia_semana = 6" in str(exc.value)
    assert str(i["ofertas"][0].id) in str(exc.value)
    db.session.rollback()


def test_a_aceita_0_5_e_recusa_6(app):
    i = _seed()
    definir_grade(i["ofertas"][0], [(0, time(8), time(10)), (5, time(8), time(10))])
    mig_a._checar_dia_6(db.session.connection())  # não levanta
    assert "<= 5" in str(
        next(
            c for c in TurmaCursoHorario.__table__.constraints
            if c.name == "ck_tch_dia"
        ).sqltext
    )
    with pytest.raises(Exception):
        definir_grade(i["ofertas"][0], [(0, time(8), time(10)), (6, time(8), time(10))])
    db.session.rollback()


# ---------------------------------------------------------------------------
# Migration B — DROP e downgrade que reconstrói a projeção
# ---------------------------------------------------------------------------
def test_b_upgrade_dropa_as_6_colunas_e_e_idempotente(app):
    i = _seed()
    definir_grade(i["ofertas"][0], [(0, time(8), time(10))])
    _garantir_colunas_legadas()
    assert set(COLUNAS) <= _colunas("turma")
    assert set(COLUNAS) <= _colunas("turma_curso")

    _aplicar_drop_b()
    assert not (set(COLUNAS) & _colunas("turma"))
    assert not (set(COLUNAS) & _colunas("turma_curso"))

    _aplicar_drop_b()  # idempotente
    assert not (set(COLUNAS) & _colunas("turma_curso"))


def test_b_upgrade_recusa_oferta_sem_grade(app):
    i = _seed()
    _garantir_colunas_legadas()
    with pytest.raises(RuntimeError) as exc:
        _aplicar_drop_b()
    assert str(i["ofertas"][0].id) in str(exc.value)
    db.session.rollback()


def test_b_downgrade_reconstroi_uniforme_e_espelha_turma(app):
    i = _seed()
    definir_grade(i["ofertas"][0], [
        (0, time(8), time(10)), (2, time(8), time(10)),
    ])
    _garantir_colunas_legadas()
    _aplicar_drop_b()
    _aplicar_downgrade_b()

    assert _linhas_oferta(i["ofertas"][0].id) == {
        "dias": "Segunda, Quarta", "ini": "08:00:00", "fim": "10:00:00",
    }
    assert _linha_turma(i["turma"]) == {
        "dias": "Segunda, Quarta", "ini": "08:00:00", "fim": "10:00:00",
    }


def test_b_downgrade_nao_uniforme_dias_sem_horas(app):
    i = _seed()
    definir_grade(i["ofertas"][0], [
        (1, time(8), time(10)), (3, time(14), time(16)),
    ])
    _garantir_colunas_legadas()
    _aplicar_drop_b()
    _aplicar_downgrade_b()

    assert _linhas_oferta(i["ofertas"][0].id) == {
        "dias": "Terça, Quinta", "ini": None, "fim": None,
    }
    # Turma com uma única oferta ativa espelha dias + NULLs.
    assert _linha_turma(i["turma"]) == {
        "dias": "Terça, Quinta", "ini": None, "fim": None,
    }


def test_b_downgrade_turma_0_e_2_ofertas_ficam_null(app):
    # Turma sem oferta
    i0 = _seed(ofertas=0)
    _garantir_colunas_legadas()
    _aplicar_drop_b()
    _aplicar_downgrade_b()
    assert _linha_turma(i0["turma"]) == {"dias": None, "ini": None, "fim": None}

    # Turma com 2 ofertas ativas: cada oferta tem projeção, a turma fica NULL.
    i2 = _seed(ofertas=2)
    definir_grade(i2["ofertas"][0], [(0, time(8), time(10))])
    definir_grade(i2["ofertas"][1], [(2, time(14), time(16))])
    _garantir_colunas_legadas()
    _aplicar_drop_b()
    _aplicar_downgrade_b()
    assert _linha_turma(i2["turma"]) == {"dias": None, "ini": None, "fim": None}
    assert _linhas_oferta(i2["ofertas"][0].id)["dias"] == "Segunda"
    assert _linhas_oferta(i2["ofertas"][1].id)["dias"] == "Quarta"


def test_b_reupgrade_idempotente_apos_downgrade(app):
    i = _seed()
    definir_grade(i["ofertas"][0], [(0, time(8), time(10))])
    _garantir_colunas_legadas()
    _aplicar_drop_b()
    _aplicar_downgrade_b()
    _aplicar_drop_b()
    assert not (set(COLUNAS) & _colunas("turma"))
    assert not (set(COLUNAS) & _colunas("turma_curso"))
    # E o downgrade de novo ainda encontra a grade intacta.
    _aplicar_downgrade_b()
    assert _linha_turma(i["turma"])["dias"] == "Segunda"
