# ruff: noqa: F811
"""ETAPA D3b-2.4 — estatísticas do GET /frequencia por oferta.

Caracterização (P2) + equivalência/N+1 (P4).
"""

from datetime import date

from _helpers import nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401
from test_frequencia_oferta import _base

from app.models import User


def _login(client, uid, unidade_id=None):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
        if unidade_id is not None:
            sess["unidade_id"] = unidade_id


def _uid(app):
    with app.app_context():
        return User.query.filter_by(email="admin.freq@example.com").first().id


def test_caracterizacao_estats_misturadas_oferta_a(app, client):
    s = _base(app)
    with app.app_context():
        un = None
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    # Caia está em Alfa (2 ofertas): A em o1, F em o2 → hoje misturado.
    resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o1']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Hoje (misturado): Caia tem A + F → P: 33.3%
    assert "P: 33.3%" in body


def test_caracterizacao_estats_misturadas_oferta_b(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o2']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 33.3%" in body


def test_caracterizacao_oferta_unica_legado_inalterada(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    # Gema: oferta única + legado. Dan tem A (oferta) + A,A (legado) → P: 75.0%
    resp = client.get(f"/frequencia?turma_id={s['gema']}&turma_curso={s['g']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 75.0%" in body
