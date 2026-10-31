"""S1-06 — versão de sessão, revogação e limite absoluto.

Reproduz a prova do S1 §7.4 (cookie copiado continuava autenticando depois do
logout) e cobre os eventos que precisam derrubar as sessões abertas, a recusa
de sessão sem carimbo/geração antiga e o limite absoluto de 8 horas, que a
atividade não prorroga.
"""

import re
import time

import pytest
from sqlalchemy import event, func

from app import db
from app.models import LogAcao, Unidade, User
from app.services import sessao

from _helpers import login_as

SENHA = "SenhaForte!123"


def _usuario(email, role="professor", senha=SENHA, **campos):
    usuario = User(
        name="Usuario Teste",
        email=email,
        role=role,
        first_login=False,
        **campos,
    )
    if senha:
        usuario.set_password(senha)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def _clonar_cookie(origem, destino):
    """Copia o cookie de sessão — o "outro dispositivo" da prova do S1."""
    cookie = origem.get_cookie("session")
    destino.set_cookie("session", cookie.value, domain="localhost")


# ---------------------------------------------------------------------------
# Prova do S1 §7.4 e eventos que revogam
# ---------------------------------------------------------------------------


def test_cookie_copiado_nao_autentica_depois_do_logout(app, client):
    usuario = _usuario("vitima.sessao@example.invalid")
    login_as(client, usuario)
    assert client.get("/painel").status_code == 200

    outro = app.test_client()
    _clonar_cookie(client, outro)
    assert outro.get("/painel").status_code == 200, "pré-condição: cópia vale"

    assert client.post("/logout").status_code == 302

    recusado = outro.get("/painel")
    assert recusado.status_code == 302
    assert "/login" in recusado.headers["Location"]
    assert db.session.get(User, usuario.id).session_version == 1


def test_troca_de_senha_mantem_a_sessao_atual_e_derruba_a_outra(app, client):
    usuario = _usuario("troca.sessao@example.invalid")
    login_as(client, usuario)
    outro = app.test_client()
    login_as(outro, usuario)

    resposta = client.post(
        "/trocar-senha",
        data={
            "senha_atual": SENHA,
            "nova_senha": "OutraSenha!456",
            "confirma_senha": "OutraSenha!456",
        },
    )
    assert resposta.status_code == 302

    assert client.get("/painel").status_code == 200, "a sessão que trocou continua"
    assert outro.get("/painel").status_code == 302, "a outra sessão cai"


def test_reset_pelo_admin_derruba_as_sessoes_do_alvo(app, client, monkeypatch):
    admin = _usuario("admin.reset@example.invalid", role="admin")
    alvo = _usuario("alvo.reset@example.invalid")
    monkeypatch.setattr("app.auth.send_email", lambda **_: None)
    app.config["ADMIN_DEFAULT_PASSWORD"] = "Provisoria!123"

    login_as(client, alvo)
    assert client.get("/painel").status_code == 200

    admin_client = app.test_client()
    login_as(admin_client, admin)
    assert admin_client.post(f"/usuarios/resetar/{alvo.id}").status_code == 302

    assert client.get("/painel").status_code == 302
    assert db.session.get(User, alvo.id).session_version == 1


def test_mudanca_de_papel_derruba_e_edicao_sem_mudanca_nao(app, client):
    admin = _usuario("admin.papel@example.invalid", role="admin")
    alvo = _usuario("alvo.papel@example.invalid", role="professor")

    admin_client = app.test_client()
    login_as(admin_client, admin)
    login_as(client, alvo)
    assert client.get("/painel").status_code == 200

    # edição que não mexe no perfil de acesso: sessão continua
    assert admin_client.post(
        f"/usuarios/editar/{alvo.id}",
        data={
            "nome": "Nome Novo",
            "email": "alvo.papel@example.invalid",
            "role": "professor",
            "unidade_id": "",
        },
    ).status_code == 302
    assert client.get("/painel").status_code == 200

    # mudança de papel: sessão cai
    assert admin_client.post(
        f"/usuarios/editar/{alvo.id}",
        data={
            "nome": "Nome Novo",
            "email": "alvo.papel@example.invalid",
            "role": "pedagogico",
            "unidade_id": "",
        },
    ).status_code == 302
    assert client.get("/painel").status_code == 302


def test_mudanca_de_unidade_derruba_a_sessao(app, client):
    admin = _usuario("admin.unid@example.invalid", role="admin")
    unidade = Unidade(nome="Unidade Sessão")
    db.session.add(unidade)
    db.session.commit()
    alvo = _usuario("alvo.unid@example.invalid")

    admin_client = app.test_client()
    login_as(admin_client, admin)
    login_as(client, alvo)
    assert client.get("/painel").status_code == 200

    admin_client.post(
        f"/usuarios/editar/{alvo.id}",
        data={
            "nome": "Usuario Teste",
            "email": "alvo.unid@example.invalid",
            "role": "professor",
            "unidade_id": str(unidade.id),
        },
    )

    assert client.get("/painel").status_code == 302


def test_exclusao_derruba_a_sessao_do_alvo(app, client):
    admin = _usuario("admin.excl@example.invalid", role="admin")
    alvo = _usuario("alvo.excl@example.invalid")

    admin_client = app.test_client()
    login_as(admin_client, admin)
    login_as(client, alvo)
    assert client.get("/painel").status_code == 200

    assert admin_client.post(f"/usuarios/excluir/{alvo.id}").status_code == 302
    assert client.get("/painel").status_code == 302
    assert db.session.get(User, alvo.id) is None


def test_inativacao_revoga_pelo_servico(app, client):
    """Não existe rota de inativação: o teste cobre o mecanismo reutilizável."""
    usuario = _usuario("inativo.sessao@example.invalid")
    login_as(client, usuario)
    assert client.get("/painel").status_code == 200

    sessao.revogar_sessoes(usuario.id, "inativacao")

    assert client.get("/painel").status_code == 302


# ---------------------------------------------------------------------------
# Carimbo da sessão
# ---------------------------------------------------------------------------


def test_sessao_sem_carimbo_e_recusada(app, client):
    usuario = _usuario("sem.sv@example.invalid")
    with client.session_transaction() as sess:
        sess["_user_id"] = str(usuario.id)
        sess["_fresh"] = True

    resposta = client.get("/painel")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]

    aviso = client.get("/login")
    assert "encerrada por segurança" in aviso.get_data(as_text=True)


def test_sessao_com_geracao_antiga_e_recusada(app, client):
    usuario = _usuario("sv.antigo@example.invalid")
    login_as(client, usuario)
    with client.session_transaction() as sess:
        sess["sv"] = sess["sv"] + 1

    assert client.get("/painel").status_code == 302


def test_login_descarta_a_sessao_anonima(app, client):
    usuario = _usuario("fixacao@example.invalid")

    with client.session_transaction() as sess:
        sess["marca_anonima"] = "nao-deve-sobreviver"

    resposta = client.post(
        "/login", data={"email": usuario.email, "password": SENHA}
    )
    assert resposta.status_code == 302

    with client.session_transaction() as sess:
        assert "marca_anonima" not in sess
        assert sess["sv"] == 0
        assert isinstance(sess["iat"], int)


# ---------------------------------------------------------------------------
# Limite absoluto (independente de atividade)
# ---------------------------------------------------------------------------


def test_limite_absoluto_recusa_acima_de_8_horas(app, client, monkeypatch):
    usuario = _usuario("absoluto@example.invalid")
    login_as(client, usuario)
    agora = int(time.time())

    monkeypatch.setattr(sessao, "_agora", lambda: agora)
    with client.session_transaction() as sess:
        sess["iat"] = agora - (8 * 3600) - 60

    resposta = client.get("/painel")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]
    assert "expirou" in client.get("/login").get_data(as_text=True)


def test_limite_absoluto_aceita_7h59(app, client, monkeypatch):
    usuario = _usuario("absoluto.ok@example.invalid")
    login_as(client, usuario)
    agora = int(time.time())

    monkeypatch.setattr(sessao, "_agora", lambda: agora)
    with client.session_transaction() as sess:
        sess["iat"] = agora - (8 * 3600) + 60

    assert client.get("/painel").status_code == 200


def test_atividade_continua_nao_prorroga_o_limite(app, client, monkeypatch):
    usuario = _usuario("absoluto.ativo@example.invalid")
    login_as(client, usuario)
    agora = int(time.time())

    with client.session_transaction() as sess:
        sess["iat"] = agora

    # 7 horas de atividade: cada requisição renova o cookie, não o `iat`
    monkeypatch.setattr(sessao, "_agora", lambda: agora + 7 * 3600)
    assert client.get("/painel").status_code == 200

    # 8h01 depois do login, mesmo tendo trabalhado o tempo todo: recusada
    monkeypatch.setattr(sessao, "_agora", lambda: agora + 8 * 3600 + 60)
    assert client.get("/painel").status_code == 302


# ---------------------------------------------------------------------------
# Custo e auditoria
# ---------------------------------------------------------------------------


def test_requisicao_autenticada_faz_um_select_em_user(app, client):
    usuario = _usuario("custo.sessao@example.invalid")
    login_as(client, usuario)
    # O fixture mantém um AppContext (e a sessão SQLAlchemy) aberto: sem isto o
    # identity map devolveria o usuário do `login_as` e o SELECT real sumiria
    # do teste. Em produção cada request tem sessão própria.
    db.session.expunge_all()

    consultas = []
    engine = db.engine

    def _escuta(conn, cursor, statement, parametros, contexto, muitos):
        baixo = statement.lower()
        if baixo.lstrip().startswith("select") and (
            'from "user"' in baixo or "from user" in baixo
        ):
            consultas.append(statement)

    event.listen(engine, "before_cursor_execute", _escuta)
    try:
        assert client.get("/painel").status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _escuta)

    assert len(consultas) == 1, consultas


def test_revogacao_gera_um_unico_log_e_nenhum_de_alteracao(app, client, monkeypatch):
    admin = _usuario("admin.log@example.invalid", role="admin")
    alvo = _usuario("alvo.log@example.invalid")
    monkeypatch.setattr("app.auth.send_email", lambda **_: None)
    app.config["ADMIN_DEFAULT_PASSWORD"] = "Provisoria!123"

    login_as(client, admin)
    ultimo = db.session.query(func.max(LogAcao.id)).scalar() or 0
    client.post(f"/usuarios/resetar/{alvo.id}")

    novos = LogAcao.query.filter(LogAcao.id > ultimo).all()
    acoes = [log.acao for log in novos]
    assert "Sessões revogadas" in acoes
    assert not any(acao.startswith("Alterar User") for acao in acoes)

    revogacao = next(log for log in novos if log.acao == "Sessões revogadas")
    assert f"usuario_id={alvo.id}" in revogacao.detalhes
    assert "@" not in revogacao.detalhes


def test_logout_nao_gera_log_extra(app, client):
    usuario = _usuario("logout.log@example.invalid")
    login_as(client, usuario)

    ultimo = db.session.query(func.max(LogAcao.id)).scalar() or 0
    client.post("/logout")

    acoes = [log.acao for log in LogAcao.query.filter(LogAcao.id > ultimo).all()]
    assert acoes == ["Logoff"]


# ---------------------------------------------------------------------------
# S1-16 — logout só por POST
# ---------------------------------------------------------------------------


def test_get_logout_nao_encerra_a_sessao(app, client):
    usuario = _usuario("get.logout@example.invalid")
    login_as(client, usuario)

    resposta = client.get("/logout")
    assert resposta.status_code == 302
    assert "/painel" in resposta.headers["Location"]
    assert db.session.get(User, usuario.id).session_version == 0
    assert client.get("/painel").status_code == 200


def test_get_logout_anonimo_vai_para_o_login(client):
    resposta = client.get("/logout")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_post_logout_desloga_revoga_e_redireciona(app, client):
    usuario = _usuario("post.logout@example.invalid")
    login_as(client, usuario)

    resposta = client.post("/logout")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]
    assert db.session.get(User, usuario.id).session_version == 1
    assert client.get("/painel").status_code == 302


def test_post_logout_sem_token_e_recusado(app, client):
    usuario = _usuario("csrf.logout@example.invalid")
    login_as(client, usuario)
    app.config["WTF_CSRF_ENABLED"] = True

    assert client.post("/logout").status_code == 400
    assert db.session.get(User, usuario.id).session_version == 0


def test_post_logout_com_token_funciona(app, client):
    usuario = _usuario("token.logout@example.invalid")
    login_as(client, usuario)
    app.config["WTF_CSRF_ENABLED"] = True

    html = client.get("/painel").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    resposta = client.post("/logout", data={"csrf_token": token})
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]
    assert db.session.get(User, usuario.id).session_version == 1


def test_menu_tem_formulario_de_logout(app, client):
    usuario = _usuario("menu.logout@example.invalid", role="admin")
    login_as(client, usuario)

    html = client.get("/painel").get_data(as_text=True)
    assert 'action="/logout"' in html
    assert 'name="csrf_token"' in html
    assert 'href="/logout"' not in html
