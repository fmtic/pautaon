"""S1-09 e S1-15: cookie Secure, HSTS e ProxyFix.

O `test_client` fala HTTP; `environ_overrides={"wsgi.url_scheme": "https"}`
simula o terminador TLS sem depender de proxy. Os testes de configuração usam
classes próprias (não o `Config` do processo) para provar a regra de padrão.
"""

import importlib
import os

import pytest

from app import create_app, db
from config import Config, _resolver_session_cookie_secure


class BaseConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def _app(**overrides):
    """Cria a app com os valores pedidos, sem herdar o `.env` da máquina."""
    # `FLASK_DEBUG=true` no `.env` ligaria o depurador e, com
    # `APP_ENV=production`, `validar_configuracao` recusaria subir.
    overrides.setdefault("DEBUG", False)
    classe = type("Cfg", (BaseConfig,), dict(overrides))
    test_app = create_app(classe)
    test_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    # O contexto de template consulta `InformacaoPadrao`/`Unidade` no `/login`.
    with test_app.app_context():
        db.create_all()
    return test_app


# ---------------------------------------------------------------- cookie Secure


@pytest.mark.parametrize(
    "ambiente, esperado",
    [
        (None, True),  # nada declarado: padrão seguro
        ("production", True),
        ("development", False),  # único caso em que desliga sozinho
        ("Development ", False),  # espaços e caixa não escapam da regra
        ("staging", True),
    ],
)
def test_cookie_secure_por_ambiente(monkeypatch, ambiente, esperado):
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    if ambiente is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", ambiente)

    assert _resolver_session_cookie_secure() is esperado


def test_cookie_secure_nao_depende_de_flask_env(monkeypatch):
    """`FLASK_ENV=development` sozinho não derruba o padrão seguro."""
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")

    assert _resolver_session_cookie_secure() is True


@pytest.mark.parametrize(
    "ambiente, override, esperado",
    [
        ("development", "1", True),
        ("production", "0", False),
        (None, "false", False),
    ],
)
def test_cookie_secure_aceita_override_explicito(
    monkeypatch, ambiente, override, esperado
):
    if ambiente is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", ambiente)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", override)

    assert _resolver_session_cookie_secure() is esperado


def test_config_aplica_o_ambiente_no_import():
    """A regra é resolvida no import de `config` (start do processo).

    Recarrega o módulo com `APP_ENV` controlado (vale para toda a classe
    `Config`) e devolve o ambiente original no fim, para não contaminar o
    resto da suíte.
    """
    import config as config_module

    original = os.environ.get("APP_ENV")
    original_override = os.environ.pop("SESSION_COOKIE_SECURE", None)

    def resolver(ambiente):
        if ambiente is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = ambiente
        return importlib.reload(config_module).Config.SESSION_COOKIE_SECURE

    try:
        assert resolver("production") is True
        assert resolver("development") is False
        # O caso "sem APP_ENV" só é verificável na função pura
        # (`test_cookie_secure_por_ambiente`): o `load_dotenv()` do próprio
        # `config` repõe o valor do `.env` a cada import.
    finally:
        if original is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = original
        if original_override is not None:
            os.environ["SESSION_COOKIE_SECURE"] = original_override
        importlib.reload(config_module)


# ------------------------------------------------------------------------- HSTS


def test_hsts_ausente_em_http():
    resposta = _app().test_client().get("/login")

    assert resposta.status_code == 200
    assert "Strict-Transport-Security" not in resposta.headers


def test_hsts_presente_em_https():
    resposta = _app().test_client().get(
        "/login", environ_overrides={"wsgi.url_scheme": "https"}
    )

    assert resposta.status_code == 200
    assert resposta.headers["Strict-Transport-Security"] == "max-age=15552000"


def test_hsts_sem_include_subdomains_e_sem_preload():
    resposta = _app().test_client().get(
        "/login", environ_overrides={"wsgi.url_scheme": "https"}
    )

    valor = resposta.headers["Strict-Transport-Security"].lower()
    assert "includesubdomains" not in valor
    assert "preload" not in valor


@pytest.mark.parametrize("max_age, esperado", [(600, "max-age=600"), (0, None)])
def test_hsts_valor_configuravel(max_age, esperado):
    resposta = _app(HSTS_MAX_AGE=max_age).test_client().get(
        "/login", environ_overrides={"wsgi.url_scheme": "https"}
    )

    if esperado is None:
        assert "Strict-Transport-Security" not in resposta.headers
    else:
        assert resposta.headers["Strict-Transport-Security"] == esperado


def test_hsts_aparece_em_resposta_de_erro_https():
    resposta = _app().test_client().get(
        "/rota-que-nao-existe", environ_overrides={"wsgi.url_scheme": "https"}
    )

    assert resposta.status_code == 404
    assert resposta.headers["Strict-Transport-Security"] == "max-age=15552000"


# -------------------------------------------------------------------- ProxyFix


def test_proxy_fix_desligado_ignora_cabecalho_forjado():
    """Sem `TRUSTED_PROXY`, `X-Forwarded-Proto` não torna a requisição HTTPS."""
    resposta = _app().test_client().get(
        "/login",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-For": "10.0.0.9"},
    )

    assert resposta.status_code == 200
    assert "Strict-Transport-Security" not in resposta.headers


def test_proxy_fix_ligado_honra_x_forwarded_proto():
    resposta = _app(TRUSTED_PROXY=True).test_client().get(
        "/login", headers={"X-Forwarded-Proto": "https"}
    )

    assert resposta.status_code == 200
    assert resposta.headers["Strict-Transport-Security"] == "max-age=15552000"


def test_proxy_fix_ligado_sem_cabecalho_continua_http():
    resposta = _app(TRUSTED_PROXY=True).test_client().get("/login")

    assert "Strict-Transport-Security" not in resposta.headers
