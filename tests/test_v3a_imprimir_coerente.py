"""V3a — Parte B: o botão Imprimir só aparece quando a impressão é permitida.

A guarda da impressão é por OFERTA (`professor_da_oferta`), sem herdar o
professor da turma. Reaproveita a semente/helpers de `test_v3a_datas_lancadas`.
"""

from test_v3a_datas_lancadas import SQLiteTestConfig, _get, _seed, login_as

import pytest

from app import create_app, db
from app.models import TurmaCurso


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


@pytest.fixture
def client(app):
    return app.test_client()


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


def test_imprimir_oculto_para_professor_em_turma_sem_oferta(app, client):
    """Turma legada (0 ofertas ativas): o professor levaria 403 — botão oculto."""
    ids = _seed(app)
    with app.app_context():
        for oferta in TurmaCurso.query.filter_by(turma_id=ids["turma"]).all():
            oferta.ativo = False
        db.session.commit()

    login_as(client, ids["prof"], ids["un"])
    status, html = _get(client, ids)

    assert status == 200
    assert "Imprimir Pauta" not in html
