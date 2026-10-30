"""V3a — Parte B: o botão Imprimir só aparece quando a impressão é permitida.

A guarda da impressão é por OFERTA (`professor_da_oferta`), sem herdar o
professor da turma. Reaproveita a semente/helpers de `test_v3a_datas_lancadas`.
"""

import re

from test_v3a_datas_lancadas import _get, _seed, login_as


from app import db
from app.models import TurmaCurso


def test_imprimir_visivel_para_o_professor_da_oferta(app, client):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    status, html = _get(client, ids, turma_curso=ids["o1"])

    assert status == 200
    assert "Imprimir Pauta" in html
    assert f"turma_curso={ids['o1']}" in html


def test_imprimir_oculto_para_professor_que_nao_e_o_da_oferta(app, client):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    status, html = _get(client, ids, turma_curso=ids["o2"])

    assert status == 200
    assert "Imprimir Pauta" not in html


def test_imprimir_oculto_sem_oferta_escolhida_com_2_ofertas(app, client):
    ids = _seed(app)

    for perfil in ("prof", "admin", "secretaria"):
        login_as(client, ids[perfil], ids["un"])
        status, html = _get(client, ids)
        assert status == 200
        assert "Imprimir Pauta" not in html, perfil


def test_imprimir_visivel_para_admin_secretaria_pedagogico(app, client):
    ids = _seed(app)

    for perfil in ("admin", "secretaria", "pedagogico"):
        login_as(client, ids[perfil], ids["un"])
        status, html = _get(client, ids, turma_curso=ids["o2"])
        assert status == 200
        assert "Imprimir Pauta" in html, perfil
        assert f"turma_curso={ids['o2']}" in html


def test_professor_em_turma_sem_oferta_perde_acesso(app, client):
    """Turma legada (0 ofertas ativas) — E3 (I1): a regra de acesso é por OFERTA.

    Antigo: o professor entrava pela turma via `turma.professor_id` (200) e o
    botão Imprimir aparecia oculto. Novo: sem oferta ativa própria, a turma sai
    da lista dele e o `turma_id` é recusado (flash + retorno a /frequencia sem
    acesso à pauta). Motivo: acesso por oferta sem herança (MER §8.12/§8.22).
    """
    ids = _seed(app)
    with app.app_context():
        for oferta in TurmaCurso.query.filter_by(turma_id=ids["turma"]).all():
            oferta.ativo = False
        db.session.commit()

    login_as(client, ids["prof"], ids["un"])
    resposta = client.get(
        f"/frequencia?turma_id={ids['turma']}", follow_redirects=True
    )

    assert resposta.status_code == 200
    html = re.sub(r"\s+", " ", resposta.get_data(as_text=True))
    assert "não tem permissão para acessar esta turma" in html
    assert "Imprimir Pauta" not in html
