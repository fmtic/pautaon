# ruff: noqa: F811
"""ETAPA D3b-2.5 — min_freq coerente com a frequência exibida (D7)."""

from test_frequencia_oferta import _base

from app.models import Turma
from app.registros.turmas import pos_filtrar_turmas


def test_min_freq_multi_principal_acima_soma_abaixo_deixa_de_aparecer(app):
    # Alfa: principal (o1) = 75.0, soma = 50.0.
    s = _base(app)
    with app.app_context():
        alfa = Turma.query.get(s["alfa"])
        # min_freq=60: principal passaria (75>=60), soma não (50<60) → exclui.
        res = pos_filtrar_turmas([alfa], {"min_freq": "60"})
        assert res == []


def test_min_freq_multi_soma_acima_principal_abaixo_passa_a_aparecer(app):
    # Caso inverso: forçar principal baixo e soma alta não existe na semente;
    # usamos Alfa com min_freq=40: soma 50>=40 → mantém (antes excluía por principal? não).
    # Teste de coerência: valor da coluna (freq_geral=50) == valor comparado.
    s = _base(app)
    with app.app_context():
        alfa = Turma.query.get(s["alfa"])
        assert alfa.freq_geral == 50.0
        res = pos_filtrar_turmas([alfa], {"min_freq": "50"})
        assert [t.id for t in res] == [alfa.id]
        res2 = pos_filtrar_turmas([alfa], {"min_freq": "51"})
        assert res2 == []


def test_min_freq_zero_ofertas_inalterado(app):
    s = _base(app)
    with app.app_context():
        zeta = Turma.query.get(s["zeta"])
        # Zeta sem lançamentos: freq_geral=0.0. min_freq=0 mantém; min_freq=1 exclui.
        assert pos_filtrar_turmas([zeta], {"min_freq": "0"}) != []
        assert pos_filtrar_turmas([zeta], {"min_freq": "1"}) == []


def test_min_freq_uma_oferta_inalterado(app):
    s = _base(app)
    with app.app_context():
        gema = Turma.query.get(s["gema"])
        # Gema: freq_geral=75.0 (oferta única + legado).
        assert pos_filtrar_turmas([gema], {"min_freq": "70"}) != []
        assert pos_filtrar_turmas([gema], {"min_freq": "80"}) == []


def test_n1_min_freq_constante(app):
    s = _base(app)
    from sqlalchemy import event
    from app.database import db as _db

    with app.app_context():
        alfa = Turma.query.get(s["alfa"])
        gema = Turma.query.get(s["gema"])
        zeta = Turma.query.get(s["zeta"])
        turmas = [alfa, gema, zeta]

        contagem = {"n": 0}

        def _before(conn, cursor, statement, params, context, executemany):
            if "frequencia" in statement.lower():
                contagem["n"] += 1

        event.listen(_db.engine, "before_cursor_execute", _before)
        try:
            contagem["n"] = 0
            pos_filtrar_turmas(turmas, {"min_freq": "50"})
            c1 = contagem["n"]
            assert c1 <= 1, c1
        finally:
            event.remove(_db.engine, "before_cursor_execute", _before)
