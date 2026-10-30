"""Endurecimento de configuração (S1-01/S1-02).

Cobre a recusa de inicialização sem ``SECRET_KEY`` utilizável, o padrão
``DEBUG=False`` e a recusa de ``DEBUG`` em produção, além da escolha de
endereço do servidor de desenvolvimento.
"""

import pytest

from app import create_app
from app.utils.execucao import MENSAGEM_PRODUCAO, PORTA_PADRAO, escolher_bind_dev
from config import (
    Config,
    _resolver_app_env,
    _resolver_debug,
    validar_configuracao,
    validar_secret_key,
)

CHAVE_VALIDA = "c" * 40


class _ConfigBase(Config):
    SECRET_KEY = CHAVE_VALIDA
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    APP_ENV = "development"
    DEBUG = False


class ConfigSemChave(_ConfigBase):
    SECRET_KEY = None


class ConfigChaveCurta(_ConfigBase):
    SECRET_KEY = "curta-demais"


class ConfigChaveDev(_ConfigBase):
    SECRET_KEY = "dev-key-substituir-em-producao"


class ConfigDebugProducao(_ConfigBase):
    APP_ENV = "production"
    DEBUG = True


# ---------------------------------------------------------------- SECRET_KEY


def test_secret_key_ausente_orienta_geracao():
    with pytest.raises(RuntimeError) as erro:
        validar_secret_key(None)

    mensagem = str(erro.value)
    assert "SECRET_KEY ausente" in mensagem
    assert "secrets.token_urlsafe(48)" in mensagem


@pytest.mark.parametrize("valor", ["", "   "])
def test_secret_key_vazia_e_recusada(valor):
    with pytest.raises(RuntimeError, match="SECRET_KEY ausente"):
        validar_secret_key(valor)


def test_secret_key_padrao_de_desenvolvimento_e_recusada():
    with pytest.raises(RuntimeError) as erro:
        validar_secret_key("dev-key-substituir-em-producao")

    assert "público" in str(erro.value)


def test_secret_key_com_prefixo_dev_key_e_recusada():
    with pytest.raises(RuntimeError, match="público"):
        validar_secret_key("dev-key-qualquer-outra-coisa-com-tamanho-suficiente")


def test_secret_key_curta_e_recusada():
    with pytest.raises(RuntimeError) as erro:
        validar_secret_key("a" * 31)

    assert "pelo menos 32 caracteres" in str(erro.value)
    assert "(atual: 31)" in str(erro.value)


def test_secret_key_no_limite_e_aceita():
    assert validar_secret_key("b" * 32) == "b" * 32


def test_create_app_falha_sem_chave():
    with pytest.raises(RuntimeError, match="SECRET_KEY ausente"):
        create_app(ConfigSemChave)


def test_create_app_falha_com_chave_curta():
    with pytest.raises(RuntimeError, match="pelo menos 32 caracteres"):
        create_app(ConfigChaveCurta)


def test_create_app_falha_com_chave_padrao():
    with pytest.raises(RuntimeError, match="público"):
        create_app(ConfigChaveDev)


def test_create_app_aceita_chave_valida():
    app = create_app(_ConfigBase)
    assert app.config["SECRET_KEY"] == CHAVE_VALIDA
    assert app.config["DEBUG"] is False


# --------------------------------------------------------------------- DEBUG


def test_debug_falso_por_padrao(monkeypatch):
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert _resolver_debug("development") is False
    assert _resolver_debug("production") is False


def test_debug_ligado_somente_em_development(monkeypatch):
    monkeypatch.setenv("FLASK_DEBUG", "true")
    assert _resolver_debug("development") is True
    assert _resolver_debug("production") is False


def test_debug_explicito_em_producao_falha_na_inicializacao():
    with pytest.raises(RuntimeError, match="DEBUG não pode estar ligado"):
        create_app(ConfigDebugProducao)


def test_validar_configuracao_aceita_producao_sem_debug():
    validar_configuracao(
        {"APP_ENV": "production", "DEBUG": False, "SECRET_KEY": CHAVE_VALIDA}
    )


def test_flask_env_e_alias_legado(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("FLASK_ENV", "staging")
    assert _resolver_app_env() == "staging"

    monkeypatch.setenv("APP_ENV", "production")
    assert _resolver_app_env() == "production"


# --------------------------------------------------------- servidor de dev


def test_bind_com_debug_fica_em_loopback():
    assert escolher_bind_dev({"DEBUG": True, "APP_ENV": "development"}) == (
        "127.0.0.1",
        PORTA_PADRAO,
        True,
    )


def test_bind_development_sem_debug_mantem_a_rede():
    assert escolher_bind_dev({"DEBUG": False, "APP_ENV": "development"}) == (
        "0.0.0.0",
        PORTA_PADRAO,
        False,
    )


def test_bind_fora_de_development_recusa_o_servidor_embarcado():
    with pytest.raises(RuntimeError) as erro:
        escolher_bind_dev({"DEBUG": False, "APP_ENV": "production"})

    assert "waitress" in str(erro.value)
    assert MENSAGEM_PRODUCAO in str(erro.value)
