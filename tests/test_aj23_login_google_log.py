"""AJ23 — botão Google em "/" e log em arquivo (diagnóstico do callback OAuth).

Cobre: (1) ``/`` delegando ao ``auth.login`` e a flag ``google_login_habilitado``
em todos os caminhos de render do login; (2) handler de arquivo único,
configurável por ``LOG_DIR``, silencioso em ``TESTING`` e sem segredos no log.
"""

from __future__ import annotations

import logging

import pytest

from app import create_app, db
from config import Config

SECRET_TESTE = "chave-teste-aj23-com-mais-de-32-caracteres"
FORMATO_ESPERADO = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _ConfigBase(Config):
    SECRET_KEY = SECRET_TESTE
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


def _configurar_google(app, *, com_secret=True):
    app.config.update(
        GOOGLE_OAUTH_CLIENT_ID="cliente-teste-aj23",
        GOOGLE_OAUTH_CLIENT_SECRET="segredo-teste-aj23" if com_secret else None,
        GOOGLE_OAUTH_REDIRECT_URI="http://localhost/auth/google/callback",
    )


def _handlers_aj23(app):
    return [
        handler
        for handler in app.logger.handlers
        if getattr(handler, "_aj23_alvo", None) is not None
    ]


@pytest.fixture
def app_log(tmp_path):
    """App não-TESTING com LOG_DIR isolado, schema SQLite e handler instalado."""
    diretorio = tmp_path / "logs"

    class ConfigLog(_ConfigBase):
        LOG_DIR = str(diretorio)

    aplicativo = create_app(ConfigLog)
    aplicativo.config.update(TESTING=False)
    with aplicativo.app_context():
        db.create_all()
        yield aplicativo, diretorio
        db.session.remove()
        db.drop_all()
    for handler in list(aplicativo.logger.handlers):
        if getattr(handler, "_aj23_alvo", None) is not None:
            aplicativo.logger.removeHandler(handler)
            handler.close()


# ---------------------------------------------------------------------------
# 1. Botão Google em "/"
# ---------------------------------------------------------------------------


def test_home_redireciona_para_login(app, client):
    resposta = client.get("/")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/login")


def test_home_segue_redirect_e_mostra_botao_com_flag_ligada(app, client):
    _configurar_google(app)
    resposta = client.get("/", follow_redirects=True)
    assert resposta.status_code == 200
    html = resposta.data.decode("utf-8")
    assert 'href="/auth/google/login"' in html
    assert "E-mail Institucional" in html


def test_login_sem_configuracao_nao_mostra_botao(app, client):
    app.config.update(
        GOOGLE_OAUTH_CLIENT_ID=None,
        GOOGLE_OAUTH_CLIENT_SECRET=None,
        GOOGLE_OAUTH_REDIRECT_URI=None,
    )
    html = client.get("/login").data.decode("utf-8")
    assert 'href="/auth/google/login"' not in html
    assert "E-mail Institucional" not in html


def test_login_com_id_e_uri_sem_secret_nao_mostra_botao(app, client):
    _configurar_google(app, com_secret=False)
    html = client.get("/login").data.decode("utf-8")
    assert 'href="/auth/google/login"' not in html


def test_flag_presente_no_rerender_apos_post_invalido(app, client):
    _configurar_google(app)
    resposta = client.post(
        "/login",
        data={"email": "sem-conta@teste.local", "password": "senha-errada"},
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    html = resposta.data.decode("utf-8")
    assert 'href="/auth/google/login"' in html
    assert "E-mail Institucional" in html


def test_home_autenticado_mantem_comportamento_de_auth_login(app, client):
    from _helpers import login_as
    from app.models import User
    from app.models.enums import UserRole

    with app.app_context():
        usuario = User(
            name="Admin AJ23",
            email="admin.aj23@teste.local",
            password="",
            role=UserRole.ADMIN.value,
            is_active=True,
            first_login=False,
            is_ad_user=True,
        )
        db.session.add(usuario)
        db.session.commit()
        login_as(client, usuario)

    redirecionamento = client.get("/")
    assert redirecionamento.status_code == 302
    assert redirecionamento.headers["Location"].endswith("/login")
    assert client.get("/login").status_code == 200


# ---------------------------------------------------------------------------
# 2. Log em arquivo
# ---------------------------------------------------------------------------


def test_create_app_duas_vezes_nao_duplica_handler(app_log):
    _, diretorio = app_log

    class ConfigDuas(_ConfigBase):
        LOG_DIR = str(diretorio)

    primeira = create_app(ConfigDuas)
    segunda = create_app(ConfigDuas)

    assert primeira.logger is segunda.logger
    handlers = _handlers_aj23(primeira)
    assert len(handlers) == 1
    assert handlers[0].baseFilename == str(diretorio / "app.log")


def test_handler_configurado_conforme_especificacao(app_log):
    _, diretorio = app_log
    handlers = _handlers_aj23(app_log[0])
    assert len(handlers) == 1

    handler = handlers[0]
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 5
    assert handler.encoding == "utf-8"
    assert handler.level == logging.INFO
    assert handler.formatter._fmt == FORMATO_ESPERADO
    # delay=True: create_app sozinho não cria o arquivo.
    assert not (diretorio / "app.log").exists()


def test_log_info_gravado_com_formato(app_log):
    aplicativo, diretorio = app_log
    with aplicativo.app_context():
        aplicativo.logger.info("evento %s", "aj23")

    conteudo = (diretorio / "app.log").read_text(encoding="utf-8")
    assert "INFO app: evento aj23" in conteudo


def test_testing_por_config_nao_cria_pasta_nem_arquivo(tmp_path):
    diretorio = tmp_path / "logs_testing"

    class ConfigTesting(_ConfigBase):
        TESTING = True
        LOG_DIR = str(diretorio)

    aplicativo = create_app(ConfigTesting)
    with aplicativo.app_context():
        aplicativo.logger.error("nao deve gravar")

    assert not diretorio.exists()
    assert not (diretorio / "app.log").exists()


def test_testing_ligado_apos_create_app_nao_cria_arquivo(tmp_path):
    diretorio = tmp_path / "logs_tarde"

    class ConfigTarde(_ConfigBase):
        LOG_DIR = str(diretorio)

    aplicativo = create_app(ConfigTarde)
    aplicativo.config["TESTING"] = True
    with aplicativo.app_context():
        aplicativo.logger.error("nao deve gravar")

    assert not (diretorio / "app.log").exists()


def test_callback_com_excecao_grava_tipo_mensagem_e_traceback_sem_segredos(
    app_log, monkeypatch
):
    from google_auth_oauthlib.flow import Flow

    aplicativo, diretorio = app_log
    segredo = "segredo-cliente-aj23-4444"
    codigo = "codigo-aj23-5555"
    token = "token-aj23-6666"
    senha = "senha-aj23-7777"
    _configurar_google(aplicativo)
    aplicativo.config["GOOGLE_OAUTH_CLIENT_SECRET"] = segredo

    def _fetch_token_que_falha(self, **kwargs):
        raise RuntimeError(
            "falha: client_secret="
            + segredo
            + ", code="
            + codigo
            + ", access_token="
            + token
            + ", senha="
            + senha
            + ", url=http://servidor/auth/google/callback?code="
            + codigo
            + "&state=estado-valido"
        )

    monkeypatch.setattr(Flow, "fetch_token", _fetch_token_que_falha)

    cliente = aplicativo.test_client()
    with cliente.session_transaction() as sess:
        sess["google_oauth_state"] = "estado-valido"
        sess["google_code_verifier"] = "verificador-valido"

    resposta = cliente.get(
        "/auth/google/callback?code=" + codigo + "&state=estado-valido"
    )
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/login")

    arquivo = diretorio / "app.log"
    assert arquivo.exists()
    conteudo = arquivo.read_text(encoding="utf-8")
    assert "Falha no callback OAuth Google: RuntimeError:" in conteudo
    assert "Traceback (most recent call last)" in conteudo
    assert "?<query omitida>" in conteudo
    for secreto in (segredo, codigo, token, senha):
        assert secreto not in conteudo
    assert "?code=" not in conteudo


def test_mascara_segredos_em_chaves_json_e_url(app):
    from app.utils.logging_seguro import mascarar_para_log

    app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = "segredo-exato-aj23"
    texto = (
        'req=http://servidor/auth/google/callback?code=ABC123&state=XYZ '
        '"client_secret": "segredo-exato-aj23", token=TOKEN999, '
        "senha=SENHA888"
    )
    resultado = mascarar_para_log(texto)

    for secreto in ("ABC123", "segredo-exato-aj23", "TOKEN999", "SENHA888"):
        assert secreto not in resultado
    assert "?<query omitida>" in resultado
    assert "client_secret" in resultado
