# ruff: noqa: F811
"""ETAPA D3b-2.4 — estatísticas do GET /frequencia por oferta."""

from _helpers import login_as, nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401
from test_frequencia_oferta import _base

from app.models import User


def _login(client, uid, unidade_id=None):
    login_as(client, str(uid), unidade_id)
def _uid(app):
    with app.app_context():
        return User.query.filter_by(email="admin.freq@example.com").first().id


def test_estats_oferta_a_nao_ve_b(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o1']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 50.0%" in body


def test_estats_oferta_b_nao_ve_a(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o2']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 0.0%" in body


def test_estats_oferta_unica_legado_inalterada(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    resp = client.get(f"/frequencia?turma_id={s['gema']}&turma_curso={s['g']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 75.0%" in body


def test_n1_estats_constante(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)

    from sqlalchemy import event
    from app.database import db as _db

    contagem = {"n": 0}

    def _before(conn, cursor, statement, params, context, executemany):
        if "frequencia" in statement.lower():
            contagem["n"] += 1

    event.listen(_db.engine, "before_cursor_execute", _before)
    try:
        contagem["n"] = 0
        resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o1']}&data=2026-03-02")
        assert resp.status_code == 200
        assert contagem["n"] <= 2, contagem["n"]
    finally:
        event.remove(_db.engine, "before_cursor_execute", _before)
