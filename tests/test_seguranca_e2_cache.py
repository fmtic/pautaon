"""S1-10: cache de páginas autenticadas.

Regras:
- resposta de usuário autenticado: ``no-store, private`` (+ ``Pragma``/``Expires``),
  inclusive downloads — o arquivo continua baixando, só não fica guardado;
- ``/login`` e páginas de erro anônimas: ``no-cache``, sem ``no-store``;
- ``/static``: intocado (o cache ali é o desejado).
"""

import pytest

from app import create_app, db
from app.models import Aluno, Unidade, User
from config import Config
from _helpers import login_as


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


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
def admin(app, client):
    with app.app_context():
        unidade = Unidade(nome="Unidade Cache", ativo=True)
        user = User(
            name="Admin Cache",
            email="admin.cache@example.com",
            role="admin",
            first_login=False,
        )
        user.set_password("SenhaCache!123")
        db.session.add_all([unidade, user])
        db.session.flush()
        aluno = Aluno(
            nome="Aluno Cache",
            nome_social="Aluno Cache",
            ativo=True,
            unidade_id=unidade.id,
        )
        db.session.add(aluno)
        db.session.commit()
        dados = {"user_id": user.id, "unidade_id": unidade.id, "aluno_id": aluno.id}

    login_as(client, str(dados["user_id"]), str(dados["unidade_id"]))
    return dados


def test_painel_autenticado_nao_vai_para_o_cache(client, admin):
    resposta = client.get("/painel")

    assert resposta.status_code == 200
    assert resposta.headers["Cache-Control"] == "no-store, private"
    assert resposta.headers["Pragma"] == "no-cache"
    assert resposta.headers["Expires"] == "0"


def test_download_xlsx_continua_funcionando_e_sem_cache(client, admin):
    """Arquivo gerado continua íntegro; só deixa de ser cacheável."""
    resposta = client.get("/relatorios/bi/exportar/xlsx?codigo=ALU-001")

    assert resposta.status_code == 200
    assert resposta.content_type.startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    # ZIP (xlsx) começa com PK: o download não foi alterado pelo hook.
    assert resposta.data[:2] == b"PK"
    assert resposta.headers["Cache-Control"] == "no-store, private"


def test_login_anonimo_usa_no_cache_e_nao_no_store(client):
    resposta = client.get("/login")

    assert resposta.status_code == 200
    assert resposta.headers["Cache-Control"] == "no-cache"
    assert "no-store" not in resposta.headers["Cache-Control"]


def test_pagina_de_erro_anonima_usa_no_cache(client):
    resposta = client.get("/rota-inexistente-para-cache")

    assert resposta.status_code == 404
    assert resposta.headers["Cache-Control"] == "no-cache"


def test_static_nao_recebe_o_cache_de_pagina(client):
    resposta = client.get("/static/css/style.css")

    assert resposta.status_code == 200
    assert resposta.headers.get("Cache-Control") != "no-store, private"
    assert "Pragma" not in resposta.headers


def test_info_professor_mantem_o_proprio_cache_control(client, app, admin):
    """Rota que já definia `no-store` não é sobrescrita pelo hook."""
    with app.app_context():
        aluno = db.session.get(Aluno, admin["aluno_id"])
        resposta = client.get(f"/aluno/{aluno.id}/info-professor")

    assert resposta.status_code in (200, 403, 404)
    if resposta.status_code == 200:
        assert resposta.headers["Cache-Control"] == "no-store"
