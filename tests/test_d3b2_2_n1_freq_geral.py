# ruff: noqa: F811
"""ETAPA D3b-2.2 — remoção de N+1 de freq_geral/freq_geral_oferta na listagem.

Testes de caracterização + equivalência + N+1. A semente é a de
`tests/test_frequencia_oferta.py::_base`.
"""

from datetime import date

from _helpers import nova_inscricao, nova_oferta  # noqa: F401
from test_conselho_oferta import app, client  # noqa: F401
from test_frequencia_oferta import _base

from app.database import db
from app.models import Turma
from app.services.frequencia_oferta import (
    freq_geral_ofertas_em_lote,
    freq_geral_turmas_em_lote,
)


def _ids(app):
    with app.app_context():
        s = _base(app)
        return s


def test_equivalencia_mapa_batch_vs_property(app):
    s = _ids(app)
    with app.app_context():
        turmas = [Turma.query.get(s["alfa"]), Turma.query.get(s["gema"]),
                  Turma.query.get(s["zeta"])]
        oferta_ids = [s["o1"], s["o2"], s["g"], s["z"]]
        mapa_t = freq_geral_turmas_em_lote([t.id for t in turmas])
        mapa_o = freq_geral_ofertas_em_lote(oferta_ids)
        for t in turmas:
            assert mapa_t[t.id] == t.freq_geral, (t.id, mapa_t[t.id], t.freq_geral)
        for oid in oferta_ids:
            # oferta pertence à turma correspondente; usa a property da turma
            from app.models import TurmaCurso
            tc = db.session.get(TurmaCurso, oid)
            t = db.session.get(Turma, tc.turma_id)
            assert mapa_o[oid] == t.freq_geral_oferta(oid), (oid, mapa_o[oid])


def test_batch_uma_consulta_por_mapa(app):
    s = _ids(app)
    from sqlalchemy import event
    from app.database import db as _db

    contagem = {"n": 0}

    def _before(conn, cursor, statement, params, context, executemany):
        if "frequencia" in statement.lower():
            contagem["n"] += 1

    event.listen(_db.engine, "before_cursor_execute", _before)
    try:
        # 1 turma
        contagem["n"] = 0
        freq_geral_turmas_em_lote([s["alfa"]])
        c1 = contagem["n"]
        # 3 turmas
        contagem["n"] = 0
        freq_geral_turmas_em_lote([s["alfa"], s["gema"], s["zeta"]])
        c3 = contagem["n"]
        assert c1 == 1 and c3 == 1, (c1, c3)

        contagem["n"] = 0
        freq_geral_ofertas_em_lote([s["o1"]])
        o1 = contagem["n"]
        contagem["n"] = 0
        freq_geral_ofertas_em_lote([s["o1"], s["o2"], s["g"], s["z"]])
        o4 = contagem["n"]
        assert o1 == 1 and o4 == 1, (o1, o4)
    finally:
        event.remove(_db.engine, "before_cursor_execute", _before)


def test_listagem_rota_nao_faz_n_plus_1(app, client):
    _ids(app)
    from app.models import User

    def _login(cid, uid):
        with client.session_transaction() as sess:
            sess["_user_id"] = str(uid)
            sess["_fresh"] = True

    with app.app_context():
        u = User.query.filter_by(email="admin.freq@example.com").first()
        _login(client, u.id)

    from sqlalchemy import event
    from app.database import db as _db

    contagem = {"n": 0}

    def _before(conn, cursor, statement, params, context, executemany):
        if "frequencia" in statement.lower():
            contagem["n"] += 1

    event.listen(_db.engine, "before_cursor_execute", _before)
    try:
        contagem["n"] = 0
        resp = client.get("/turma")
        assert resp.status_code == 200
        # Apenas 2 SELECTs em frequencia: um por mapa (turma + oferta).
        assert contagem["n"] <= 2, contagem["n"]
    finally:
        event.remove(_db.engine, "before_cursor_execute", _before)
