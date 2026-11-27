"""AJ23-B — callback OAuth: authorization_response vem do redirect_uri configurado.

A requisição de teste chega por ``http`` (como em produção, onde o TLS termina
antes do app); a URL entregue ao ``fetch_token`` deve começar com o
``GOOGLE_OAUTH_REDIRECT_URI`` https e preservar a query devolvida pelo Google.
"""

from __future__ import annotations

import logging

from google_auth_oauthlib.flow import Flow

from app.auth import (
    _GOOGLE_SCOPES,
    _authorization_response_oauth,
)

REDIRECT_URI = "https://sistema.example.com/auth/google/callback"


def _configurar(app):
    app.config.update(
        GOOGLE_OAUTH_CLIENT_ID="cliente-teste-aj23b",
        GOOGLE_OAUTH_CLIENT_SECRET="segredo-teste-aj23b",
        GOOGLE_OAUTH_REDIRECT_URI=REDIRECT_URI,
    )


def _preparar_sessao(client, state="estado-valido"):
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = state
        sess["google_code_verifier"] = "verificador-valido"


def _instalar_flow(monkeypatch, *, excecao=None):
    """Troca ``Flow.from_client_config`` por um fake que captura a chamada."""
    capturado = {}

    class FlowFalso:
        def __init__(self, config, scopes, state):
            capturado["config"] = config
            capturado["scopes"] = scopes
            capturado["state"] = state
            capturado["instancia"] = self

        def fetch_token(self, *, authorization_response):
            capturado["authorization_response"] = authorization_response
            if excecao is not None:
                raise excecao

    monkeypatch.setattr(
        Flow,
        "from_client_config",
        classmethod(
            lambda cls, config, scopes, state: FlowFalso(config, scopes, state)
        ),
    )
    return capturado


# ---------------------------------------------------------------------------
# Helper puro
# ---------------------------------------------------------------------------


def test_sem_query_devolve_apenas_redirect_uri():
    assert _authorization_response_oauth(REDIRECT_URI, b"") == REDIRECT_URI


def test_com_query_preserva_exatamente_a_query_e_a_ordem():
    qs = b"state=estado-valido&code=CODIGO123&scope=openid"
    assert (
        _authorization_response_oauth(REDIRECT_URI, qs)
        == REDIRECT_URI + "?state=estado-valido&code=CODIGO123&scope=openid"
    )


# ---------------------------------------------------------------------------
# Callback sobre request http
# ---------------------------------------------------------------------------


def test_callback_http_gera_authorization_response_https_e_mantem_invariantes(
    app, client, monkeypatch
):
    _configurar(app)
    capturado = _instalar_flow(monkeypatch, excecao=RuntimeError("parada controlada"))
    _preparar_sessao(client)

    resposta = client.get(
        "/auth/google/callback?state=estado-valido&code=CODIGO123"
    )

    assert resposta.status_code == 302
    assert capturado["authorization_response"] == (
        REDIRECT_URI + "?state=estado-valido&code=CODIGO123"
    )
    # Nada do request.http aparece na URL entregue ao authlib.
    assert capturado["authorization_response"].startswith("https://")
    assert "http://localhost" not in capturado["authorization_response"]
    # State, PKCE, redirect_uri e escopos longos permanecem intactos.
    assert capturado["state"] == "estado-valido"
    assert capturado["instancia"].code_verifier == "verificador-valido"
    assert capturado["instancia"].redirect_uri == REDIRECT_URI
    assert capturado["scopes"] == _GOOGLE_SCOPES
    assert capturado["config"]["web"]["client_id"] == "cliente-teste-aj23b"
    with client.session_transaction() as sess:
        assert "google_code_verifier" not in sess


def test_state_divergente_continua_recusado_sem_chamar_fetch_token(
    app, client, monkeypatch
):
    _configurar(app)
    capturado = _instalar_flow(monkeypatch)
    _preparar_sessao(client, state="estado-esperado")

    resposta = client.get(
        "/auth/google/callback?state=estado-diferente&code=CODIGO123",
        follow_redirects=True,
    )

    assert resposta.status_code == 200
    assert "Não foi possível validar o acesso com Google" in resposta.data.decode(
        "utf-8"
    )
    assert capturado == {}


def test_excecao_no_callback_continua_logada_com_tipo_mensagem_e_flash(
    app, client, monkeypatch, caplog
):
    _configurar(app)
    segredo = "segredo-vazamento-aj23b-9999"
    codigo = "codigo-vazamento-aj23b-8888"
    capturado = _instalar_flow(
        monkeypatch,
        excecao=RuntimeError("falha: code=" + codigo + " client_secret=" + segredo),
    )
    _preparar_sessao(client)

    with caplog.at_level(logging.ERROR, logger="app"):
        resposta = client.get(
            "/auth/google/callback?state=estado-valido&code=CODIGO123",
            follow_redirects=True,
        )

    assert resposta.status_code == 200
    html = resposta.data.decode("utf-8")
    assert "Não foi possível concluir o acesso com Google." in html
    registrado = caplog.records[0]
    mensagem = registrado.getMessage()
    assert "Falha no callback OAuth Google: RuntimeError:" in mensagem
    assert "Traceback" in caplog.text  # logger.exception continua anexando o traceback
    # A mensagem é sanitizada na origem; o handler de arquivo (AJ23) mascara
    # também a linha de exceção do traceback antes de gravar no app.log.
    assert segredo not in mensagem
    assert codigo not in mensagem
    assert capturado["authorization_response"] == (
        REDIRECT_URI + "?state=estado-valido&code=CODIGO123"
    )
