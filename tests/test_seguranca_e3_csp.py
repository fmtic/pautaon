"""S1-14: CSP em Report-Only (não enforcing).

O inventário da E0 encontrou apenas dois hosts carregados de fato:
``cdn.jsdelivr.net`` (Chart.js e bootstrap-icons) e ``calendar.google.com``
(iframe do Serviço Social). `sos.grael.org.br` e `developers.google.com` são
apenas links `<a href>` e não entram em diretiva nenhuma.
"""

import pytest

from app import create_app, db
from app.models import Unidade, User
from config import Config
from _helpers import login_as


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def _montar(**overrides):
    """App nova por chamada: `overrides` vale só para esta instância."""
    overrides.setdefault("DEBUG", False)
    classe = type("Cfg", (SQLiteTestConfig,), dict(overrides))
    test_app = create_app(classe)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        db.create_all()
    return test_app


@pytest.fixture
def app():
    test_app = _montar()
    yield test_app
    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def cliente_logado(app):
    client = app.test_client()
    with app.app_context():
        unidade = Unidade(nome="Unidade CSP", ativo=True)
        user = User(
            name="Admin CSP",
            email="admin.csp@example.com",
            role="admin",
            first_login=False,
        )
        user.set_password("SenhaCsp!123")
        db.session.add_all([unidade, user])
        db.session.commit()
        ids = (str(user.id), str(unidade.id))

    login_as(client, *ids)
    return client


def _politica(resposta):
    return resposta.headers["Content-Security-Policy-Report-Only"]


def test_csp_report_only_presente_no_login(app):
    resposta = app.test_client().get("/login")

    assert resposta.status_code == 200
    assert "Content-Security-Policy-Report-Only" in resposta.headers
    # Report-Only de verdade: nada de header enforcing convivendo.
    assert "Content-Security-Policy" not in resposta.headers


def test_csp_report_only_presente_no_painel(cliente_logado):
    resposta = cliente_logado.get("/painel")

    assert resposta.status_code == 200
    assert "Content-Security-Policy-Report-Only" in resposta.headers


@pytest.mark.parametrize(
    "trecho",
    [
        "default-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'self'",
        "img-src 'self' data:",
    ],
)
def test_csp_tem_as_diretivas_obrigatorias(app, trecho):
    assert trecho in _politica(app.test_client().get("/login"))


@pytest.mark.parametrize(
    "diretiva, hosts",
    [
        ("script-src", ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"]),
        ("style-src", ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"]),
        ("font-src", ["'self'", "https://cdn.jsdelivr.net"]),
        ("frame-src", ["'self'", "https://calendar.google.com"]),
    ],
)
def test_csp_libera_os_hosts_do_inventario(app, diretiva, hosts):
    politica = _politica(app.test_client().get("/login"))
    trecho = next(
        parte.strip() for parte in politica.split(";") if parte.strip().startswith(diretiva)
    )

    for host in hosts:
        assert host in trecho.split(), f"{host} ausente em {diretiva}: {trecho}"


def test_csp_nao_libera_hosts_de_navegacao(app):
    politica = _politica(app.test_client().get("/login"))

    assert "sos.grael.org.br" not in politica
    assert "developers.google.com" not in politica
    assert "*" not in politica.split()


def test_csp_desligavel(app):
    app_desligada = _montar(CSP_REPORT_ONLY=False)
    resposta = app_desligada.test_client().get("/login")

    assert "Content-Security-Policy-Report-Only" not in resposta.headers


def test_csp_politica_configuravel():
    app_custom = _montar(CSP_REPORT_ONLY_POLICY="default-src 'none'")
    resposta = app_custom.test_client().get("/login")

    assert _politica(resposta) == "default-src 'none'"


def test_csp_fora_do_static(app):
    resposta = app.test_client().get("/static/css/style.css")

    assert resposta.status_code == 200
    assert "Content-Security-Policy-Report-Only" not in resposta.headers


def test_pagina_com_cdn_continua_renderizando(cliente_logado):
    """Report-Only não bloqueia: a página que carrega Chart.js responde 200."""
    resposta = cliente_logado.get("/relatorios/bi")

    assert resposta.status_code in (200, 302)


def test_politica_padrao_do_config_cobre_o_inventario():
    politica = Config.CSP_REPORT_ONLY_POLICY

    assert "https://cdn.jsdelivr.net" in politica
    assert "https://calendar.google.com" in politica
