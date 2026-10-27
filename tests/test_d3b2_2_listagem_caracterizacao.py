# ruff: noqa: F811
"""Caracterização da listagem de turmas (D3b-2.2 P0 / D3b-2.3 P0).

Fixa o texto exibido na coluna/sub-linha de frequência e o resultado de
`min_freq` numa turma com 2+ ofertas (compara a oferta principal).
"""

from test_conselho_oferta import app, client  # noqa: F401
from test_frequencia_oferta import _base

from app.models import Turma, User
from app.registros.turmas import pos_filtrar_turmas


def _login(client, uid):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True


def test_listagem_exibe_freq_geral_e_por_oferta(app, client):
    s = _base(app)
    with app.app_context():
        u = User.query.filter_by(email="admin.freq@example.com").first()
        _login(client, u.id)
    resp = client.get("/turma")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # Alfa: freq_geral 50.0; o1 75.0; o2 0.0. Gema: 75.0.
    assert "50.0%" in body
    assert "75.0%" in body


def test_min_freq_turma_multi_ofertas_compara_turma_soma(app):
    s = _base(app)
    with app.app_context():
        alfa = Turma.query.get(s["alfa"])
        # Após D3b-2.5: min_freq compara a soma da turma (freq_geral=50.0),
        # não a oferta principal (75.0). min_freq=70 exclui; min_freq=40 mantém.
        res70 = pos_filtrar_turmas([alfa], {"min_freq": "70"})
        res40 = pos_filtrar_turmas([alfa], {"min_freq": "40"})
        assert res70 == []
        assert [t.id for t in res40] == [alfa.id]
