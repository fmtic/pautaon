"""AJ17-C — sinalizar contas Google, desvincular no painel e revisar mensagens.

Cobre: selo discreto/pendente no painel, bloco somente leitura na conta do
próprio usuário, ausência de N+1, vazamento de identificadores no HTML,
segurança da ação (perfil, CSRF, unidade, confirmação), bloqueio sem senha/AD,
idempotência, auditoria nova e o ciclo completo de troca de conta Google
(desvincular → nova conta pendente → AJ24 → login com a conta nova), inclusive
com e-mail Google igual ao local e com a conta antiga voltando ao fluxo normal.
"""

from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest
from google_auth_oauthlib.flow import Flow
from sqlalchemy import event, func, select

from app import db
from app.models import Aluno, Frequencia, LogAcao, Turma, Unidade, User
from app.models.enums import UserRole
from app.services.desvincular_google_admin import (
    ACAO_DESVINCULAR_GOOGLE,
    desvincular_conta_google,
)

SENHA = "SenhaLocal!123"
EMAIL_ADMIN = "admin.aj17c@teste.local"
EMAIL_ALVO = "alvo.aj17c@teste.local"
EMAIL_OUTRO = "outro.aj17c@teste.local"
SUB_ANTIGO = "sub-antigo-aj17c"
EMAIL_GOOGLE_ANTIGO = "antigo@google.example"
SUB_ADMIN = "sub-admin-aj17c"
EMAIL_GOOGLE_ADMIN = "admin@google.example"
SUB_NOVO = "sub-novo-aj17c"
EMAIL_GOOGLE_NOVO = "novo@google.example"


def _criar_usuario(
    email,
    role,
    *,
    nome=None,
    unidade=None,
    senha=None,
    is_ad=False,
    ativo=True,
    google_id=None,
    google_email=None,
):
    usuario = User(
        name=nome or email.split("@")[0],
        email=email,
        role=role,
        unidade_id=unidade.id if unidade is not None else None,
        is_ad_user=is_ad,
        is_active=ativo,
        first_login=False,
        google_id=google_id,
        google_email=google_email,
    )
    if senha:
        usuario.set_password(senha)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def _cenario(app, *, com_senha=True, is_ad=False, google_no_admin=False):
    unidade = Unidade(nome="Unidade AJ17-C", ativo=True)
    outra = Unidade(nome="Outra AJ17-C", ativo=True)
    db.session.add_all([unidade, outra])
    db.session.flush()

    admin = _criar_usuario(
        EMAIL_ADMIN,
        UserRole.ADMIN.value,
        nome="Admin AJ17-C",
        unidade=unidade,
        senha=None if google_no_admin else SENHA,
        google_id=SUB_ADMIN if google_no_admin else None,
        google_email=EMAIL_GOOGLE_ADMIN if google_no_admin else None,
    )
    alvo = _criar_usuario(
        EMAIL_ALVO,
        UserRole.PROFESSOR.value,
        nome="Alvo AJ17-C",
        unidade=unidade,
        senha=SENHA if com_senha else None,
        is_ad=is_ad,
        google_id=SUB_ANTIGO,
        google_email=EMAIL_GOOGLE_ANTIGO,
    )
    outro = _criar_usuario(
        EMAIL_OUTRO,
        UserRole.PROFESSOR.value,
        nome="Outro AJ17-C",
        unidade=outra,
        senha=SENHA,
        google_id="sub-outro-aj17c",
        google_email="outro@google.example",
    )
    return admin, alvo, outro, unidade, outra


def _post_desvincular(client, usuario_id, email, *, confirmar=True):
    dados = {"usuario_email": email}
    if confirmar:
        dados["confirmar"] = "1"
    return client.post(
        f"/usuarios/desvincular-google/{usuario_id}",
        data=dados,
        follow_redirects=True,
    )


def _configurar_google(app):
    app.config.update(
        GOOGLE_OAUTH_CLIENT_ID="cliente-aj17c",
        GOOGLE_OAUTH_CLIENT_SECRET="segredo-aj17c",
        GOOGLE_OAUTH_REDIRECT_URI="https://sistema.example.com/auth/google/callback",
        GOOGLE_OAUTH_ALLOWED_DOMAINS=["google.example"],
        GOOGLE_OAUTH_REQUIRE_EMAIL_VERIFIED=True,
    )


def _simular_callback(monkeypatch, sub, email, nome="Conta Google AJ17-C"):
    class FlowFalso:
        def __init__(self, config, scopes, state):
            self.credentials = SimpleNamespace(token="token-falso-aj17c")
            self.redirect_uri = None
            self.code_verifier = None

        def fetch_token(self, **kwargs):
            return None

    class RespostaFalsa:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "sub": sub,
                "email": email,
                "email_verified": True,
                "name": nome,
            }

    monkeypatch.setattr(
        Flow,
        "from_client_config",
        classmethod(
            lambda cls, config, scopes, state: FlowFalso(config, scopes, state)
        ),
    )
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: RespostaFalsa())


def _callback(client, state="estado-aj17c"):
    with client.session_transaction() as sess:
        sess["google_oauth_state"] = state
        sess["google_code_verifier"] = "verificador-aj17c"
    return client.get(f"/auth/google/callback?state={state}&code=codigo-aj17c")


def _linha(html, email):
    """Extrai a `<tr>` que contém o e-mail (cada usuário tem só uma linha)."""
    for linha in re.findall(r"<tr>.*?</tr>", html, re.DOTALL):
        if email in linha:
            return linha
    raise AssertionError(f"linha não encontrada para {email}")


def _alertas(html):
    trechos = re.findall(r'<div class="alert[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
    return [re.sub(r"<[^>]+>", " ", trecho).strip() for trecho in trechos]


def _contar_selects(client, caminho):
    """Número de comandos SELECT numa requisição (N+1 aparece como delta)."""
    contador = {"total": 0}

    def contar(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            contador["total"] += 1

    event.listen(db.engine, "before_cursor_execute", contar)
    try:
        resposta = client.get(caminho)
        assert resposta.status_code == 200
    finally:
        event.remove(db.engine, "before_cursor_execute", contar)
    return contador["total"]


# ---------------------------------------------------------------------------
# Sinalização nas telas
# ---------------------------------------------------------------------------


def test_painel_sinaliza_vinculado_pendente_e_nada_para_sem_vinculo(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, outro, unidade, _ = _cenario(app)
        pendente = _criar_usuario(
            "pendente@google.example",
            UserRole.PENDENTE.value,
            unidade=unidade,
            google_id="sub-pendente-aj17c",
            google_email="pendente@google.example",
        )
        sem_vinculo = _criar_usuario(
            "sem.google@teste.local", UserRole.PROFESSOR.value, unidade=unidade
        )
        ids = (
            admin.id,
            alvo.id,
            pendente.id,
            sem_vinculo.id,
            outro.id,
            unidade.id,
        )

    login_as(client, ids[0], ids[5])
    html = client.get("/admin/painel").data.decode("utf-8")

    linha_alvo = _linha(html, EMAIL_ALVO)
    assert "Google" in linha_alvo
    assert f'id="desvincularGoogleModal{ids[1]}"' in html
    assert f'action="/usuarios/desvincular-google/{ids[1]}"' in html
    # O badge Google é o gatilho do modal (um único por linha vinculada).
    assert f'data-bs-target="#desvincularGoogleModal{ids[1]}"' in linha_alvo
    assert linha_alvo.count('title="Desvincular Google"') == 1

    linha_pendente = _linha(html, "pendente@google.example")
    assert "Google · Pendente" in linha_pendente
    assert "bg-warning-subtle" in linha_pendente
    assert 'data-bs-target="#desvincularGoogleModal' not in linha_pendente

    linha_sem = _linha(html, "sem.google@teste.local")
    assert "Google" not in linha_sem
    assert f"desvincularGoogleModal{ids[3]}" not in html

    # O e-mail Google do alvo não é exibido na listagem; nada de outro usuário.
    assert EMAIL_GOOGLE_ANTIGO not in html
    assert "outro@google.example" not in html


def test_usuario_ve_apenas_a_propria_conta_google(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, outro, unidade, _ = _cenario(app)
        ids = (alvo.id, outro.id, unidade.id)

    login_as(client, ids[0], ids[2])
    html = client.get("/trocar-senha").data.decode("utf-8")
    assert "Conta Google: vinculada (" + EMAIL_GOOGLE_ANTIGO + ")" in html
    assert "outro@google.example" not in html
    assert "sub-outro-aj17c" not in html

    with app.app_context():
        alvo_db = db.session.get(User, ids[0])
        alvo_db.google_id = None
        alvo_db.google_email = None
        db.session.commit()

    html = client.get("/trocar-senha").data.decode("utf-8")
    assert "Conta Google: não vinculada" in html
    assert EMAIL_GOOGLE_ANTIGO not in html


def test_selo_google_nao_introduz_n_mais_1(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, unidade.id)

    login_as(client, ids[0], ids[1])
    com_um = _contar_selects(client, "/admin/painel")

    with app.app_context():
        for indice in range(29):
            _criar_usuario(
                f"usuario{indice}@teste.local",
                UserRole.PROFESSOR.value,
                unidade=unidade,
                google_id=f"sub-{indice}-aj17c",
                google_email=f"usuario{indice}@google.example",
            )

    com_trinta = _contar_selects(client, "/admin/painel")
    assert com_trinta == com_um, (com_um, com_trinta)


def test_html_nao_revela_identificador_google_nem_token(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[1])
    html_admin = client.get("/admin/painel").data.decode("utf-8")
    assert SUB_ANTIGO not in html_admin
    for marcador in (
        "google_id",
        "google_oauth_state",
        "google_code_verifier",
        "openidconnect",
        "Bearer ",
        "credentials",
    ):
        assert marcador not in html_admin

    _configurar_google(app)
    html_login = client.get("/login").data.decode("utf-8")
    assert SUB_ANTIGO not in html_login
    assert "google_oauth_state" not in html_login


def test_texto_sobre_botao_google_acompanha_a_flag(app, client):
    _configurar_google(app)
    html = client.get("/login").data.decode("utf-8")
    assert "E-mail Institucional" in html
    assert "Use sua conta Google institucional para entrar." in html

    app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = None
    html = client.get("/login").data.decode("utf-8")
    assert "E-mail Institucional" not in html
    assert "Use sua conta Google institucional para entrar." not in html


# ---------------------------------------------------------------------------
# Ação administrativa
# ---------------------------------------------------------------------------


def test_desvinculo_limpa_apenas_vinculo_e_mantem_sessao(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)
        turma = Turma(
            nome="Turma AJ17-C",
            turno="Manhã",
            data_inicio=None,
            data_fim=None,
            unidade_id=unidade.id,
            professor_id=alvo.id,
            ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        aluno = Aluno(nome="Aluno AJ17-C", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        db.session.add(
            Frequencia(
                aluno_id=aluno.id,
                turma_id=turma.id,
                data=date.fromisoformat("2026-10-29"),
                conceito="A",
                unidade_id=unidade.id,
                autor_id=alvo.id,
            )
        )
        db.session.commit()
        antes = (
            alvo.role,
            alvo.unidade_id,
            alvo.password,
            alvo.is_ad_user,
            alvo.first_login,
            alvo.session_version,
        )

    cliente_alvo = app.test_client()
    login_as(cliente_alvo, ids[1], ids[2])
    assert cliente_alvo.get("/trocar-senha").status_code == 200

    login_as(client, ids[0], ids[2])
    resposta = _post_desvincular(client, ids[1], EMAIL_ALVO)
    assert resposta.status_code == 200
    assert "Conta Google desvinculada." in resposta.data.decode("utf-8")

    with app.app_context():
        alvo_db = db.session.get(User, ids[1])
        assert alvo_db.google_id is None
        assert alvo_db.google_email is None
        assert (
            alvo_db.role,
            alvo_db.unidade_id,
            alvo_db.password,
            alvo_db.is_ad_user,
            alvo_db.first_login,
            alvo_db.session_version,
        ) == antes
        assert (
            db.session.execute(
                select(func.count()).select_from(Turma).where(Turma.professor_id == ids[1])
            ).scalar()
            == 1
        )
        assert (
            db.session.execute(
                select(func.count()).select_from(Frequencia).where(Frequencia.autor_id == ids[1])
            ).scalar()
            == 1
        )
        logs = (
            db.session.execute(
                select(LogAcao).where(LogAcao.acao == ACAO_DESVINCULAR_GOOGLE)
            )
            .scalars()
            .all()
        )
        assert len(logs) == 1
        log = logs[0]
        assert log.usuario_id == ids[0]
        assert log.usuario_nome == "Admin AJ17-C"
        assert f"usuario_id={ids[1]}" in log.detalhes
        assert EMAIL_ALVO in log.detalhes
        assert f"google_email={EMAIL_GOOGLE_ANTIGO}" in log.detalhes

    # A sessão do alvo continua válida: nada de revogação.
    html_alvo = cliente_alvo.get("/trocar-senha").data.decode("utf-8")
    assert "Conta Google: não vinculada" in html_alvo


def test_desvinculo_aceita_conta_ad_sem_senha_local(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app, com_senha=False, is_ad=True)
        ids = (admin.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[2])
    resposta = _post_desvincular(client, ids[1], EMAIL_ALVO)
    assert resposta.status_code == 200
    assert "Conta Google desvinculada." in resposta.data.decode("utf-8")
    with app.app_context():
        alvo_db = db.session.get(User, ids[1])
        assert alvo_db.google_id is None and alvo_db.google_email is None
        assert alvo_db.password is None and alvo_db.is_ad_user is True


@pytest.mark.parametrize("alvo_admin", [False, True])
def test_bloqueia_sem_senha_e_sem_ad_inclusive_admin(app, client, alvo_admin):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(
            app, com_senha=False, google_no_admin=alvo_admin
        )
        alvo_db = admin if alvo_admin else alvo
        ids = (admin.id, alvo_db.id, unidade.id)
        sub_esperado = SUB_ADMIN if alvo_admin else SUB_ANTIGO
        email_google_esperado = EMAIL_GOOGLE_ADMIN if alvo_admin else EMAIL_GOOGLE_ANTIGO

    login_as(client, ids[0], ids[2])
    resposta = _post_desvincular(client, ids[1], alvo_db.email)
    html = resposta.data.decode("utf-8")
    assert "Não foi possível desvincular." in html
    assert "Defina uma senha antes de tentar novamente." in html
    with app.app_context():
        alvo_final = db.session.get(User, ids[1])
        assert alvo_final.google_id == sub_esperado
        assert alvo_final.google_email == email_google_esperado
        assert (
            db.session.execute(
                select(func.count())
                .select_from(LogAcao)
                .where(LogAcao.acao == ACAO_DESVINCULAR_GOOGLE)
            ).scalar()
            == 0
        )


def test_idempotente_com_aviso_e_sem_novo_log(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[2])
    primeira = _post_desvincular(client, ids[1], EMAIL_ALVO)
    assert "Conta Google desvinculada." in primeira.data.decode("utf-8")

    segunda = _post_desvincular(client, ids[1], EMAIL_ALVO)
    assert "Esta conta já não estava vinculada ao Google. Nada foi alterado." in (
        segunda.data.decode("utf-8")
    )
    with app.app_context():
        assert (
            db.session.execute(
                select(func.count())
                .select_from(LogAcao)
                .where(LogAcao.acao == ACAO_DESVINCULAR_GOOGLE)
            ).scalar()
            == 1
        )
        assert db.session.get(User, ids[1]).session_version == 0


def test_nao_admin_recebe_403(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        professor = _criar_usuario(
            "professor.aj17c@teste.local", UserRole.PROFESSOR.value, unidade=unidade
        )
        ids = (professor.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[2])
    resposta = _post_desvincular(client, ids[1], EMAIL_ALVO)
    assert resposta.status_code == 403
    with app.app_context():
        assert db.session.get(User, ids[1]).google_id == SUB_ANTIGO


def test_post_sem_csrf_e_recusado(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[2])
    app.config["WTF_CSRF_ENABLED"] = True
    resposta = client.post(
        f"/usuarios/desvincular-google/{ids[1]}",
        data={"confirmar": "1", "usuario_email": EMAIL_ALVO},
    )
    assert resposta.status_code == 400
    with app.app_context():
        assert db.session.get(User, ids[1]).google_id == SUB_ANTIGO


@pytest.mark.parametrize("contexto", ["outra_unidade", "visao_global", "inexistente"])
def test_escopo_de_unidade_e_alvo_inexistente(app, client, contexto):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, outro, unidade, outra = _cenario(app)
        ids = (admin.id, alvo.id, outro.id, unidade.id, outra.id)

    if contexto == "outra_unidade":
        # Admin de uma unidade não atua sobre usuário de outra unidade.
        login_as(client, ids[0], ids[3])
        resposta = _post_desvincular(client, ids[2], EMAIL_OUTRO)
        assert resposta.status_code == 403
        with app.app_context():
            assert db.session.get(User, ids[1]).google_id == SUB_ANTIGO
            assert db.session.get(User, ids[2]).google_id == "sub-outro-aj17c"
        return

    if contexto == "visao_global":
        # Admin Global atua em qualquer unidade; o badge da outra unidade abre
        # o modal e o desvínculo é concluído.
        login_as(client, ids[0])
        html = client.get("/admin/painel").data.decode("utf-8")
        linha_outro = _linha(html, EMAIL_OUTRO)
        assert f'data-bs-target="#desvincularGoogleModal{ids[2]}"' in linha_outro
        resposta = _post_desvincular(client, ids[2], EMAIL_OUTRO)
        assert resposta.status_code == 200
        assert "Conta Google desvinculada." in resposta.data.decode("utf-8")
        with app.app_context():
            assert db.session.get(User, ids[2]).google_id is None
            assert db.session.get(User, ids[2]).google_email is None
        return

    login_as(client, ids[0], ids[3])
    resposta = _post_desvincular(client, 999999, EMAIL_ALVO)
    assert resposta.status_code == 403
    with app.app_context():
        assert db.session.get(User, ids[1]).google_id == SUB_ANTIGO


def test_confirmacao_e_email_sao_revalidados(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[2])

    sem_confirmar = _post_desvincular(client, ids[1], EMAIL_ALVO, confirmar=False)
    assert "Confirme a desvinculação antes de continuar." in sem_confirmar.data.decode(
        "utf-8"
    )

    email_trocado = _post_desvincular(client, ids[1], "_outro@teste.local")
    assert "Os dados da conta mudaram." in email_trocado.data.decode("utf-8")

    with app.app_context():
        assert db.session.get(User, ids[1]).google_id == SUB_ANTIGO


def test_mensagens_do_fluxo_sao_claras_e_sem_termos_tecnicos(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[2])

    html = _post_desvincular(client, ids[1], EMAIL_ALVO).data.decode("utf-8")
    html += _post_desvincular(client, ids[1], EMAIL_ALVO).data.decode("utf-8")

    with app.app_context():
        alvo_db = db.session.get(User, ids[1])
        alvo_db.google_id = SUB_ANTIGO
        alvo_db.google_email = EMAIL_GOOGLE_ANTIGO
        db.session.commit()

    html += client.get("/login").data.decode("utf-8")
    html += client.get("/trocar-senha").data.decode("utf-8")

    alertas = _alertas(html)
    assert any("Conta Google desvinculada." in alerta for alerta in alertas)
    assert any("já não estava vinculada" in alerta for alerta in alertas)
    for termo in ("OAuth", "state", "AJ17", "Traceback", "ValueError", "Token"):
        assert all(termo not in alerta for alerta in alertas), (termo, alertas)


def test_servico_recusa_conta_inexistente(app):
    with app.app_context():
        admin, _, _, _, _ = _cenario(app)
        with pytest.raises(ValueError, match="localizar a conta"):
            desvincular_conta_google(999999, admin_id=admin.id)


# ---------------------------------------------------------------------------
# Troca de conta Google (desvínculo → pendente → AJ24 → login novo)
# ---------------------------------------------------------------------------


def test_troca_por_conta_pendente_e_aprovacao_aj24(app, client, monkeypatch):
    from _helpers import login_as

    _configurar_google(app)
    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)

    cliente_admin = app.test_client()
    login_as(cliente_admin, ids[0], ids[2])
    assert "Conta Google desvinculada." in _post_desvincular(
        cliente_admin, ids[1], EMAIL_ALVO
    ).data.decode("utf-8")

    # Nova conta Google (e-mail diferente) cria uma pendente, sem 500.
    _simular_callback(monkeypatch, SUB_NOVO, EMAIL_GOOGLE_NOVO)
    resposta = _callback(client)
    assert resposta.status_code == 302
    with app.app_context():
        pendente = db.session.execute(
            select(User).where(User.google_id == SUB_NOVO)
        ).scalars().one()
        assert pendente.role == UserRole.PENDENTE.value
        pendente_id = pendente.id

    # A tela AJ24 oferece a pendente e o alvo já existente.
    html = cliente_admin.get("/admin/painel").data.decode("utf-8")
    assert f'id="vincularGoogleModal{pendente_id}"' in html
    assert f'action="/usuarios/vincular-google/{pendente_id}"' in html

    resposta = cliente_admin.post(
        f"/usuarios/vincular-google/{pendente_id}",
        data={
            "confirmar": "1",
            "origem_email": EMAIL_GOOGLE_NOVO,
            "alvo_id": str(ids[1]),
            "alvo_email": EMAIL_ALVO,
        },
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "Conta Google vinculada ao usuário escolhido." in resposta.data.decode(
        "utf-8"
    )

    with app.app_context():
        assert db.session.get(User, pendente_id) is None
        alvo_db = db.session.get(User, ids[1])
        assert alvo_db.google_id == SUB_NOVO
        assert alvo_db.google_email == EMAIL_GOOGLE_NOVO
        assert alvo_db.email == EMAIL_ALVO  # e-mail local não foi tocado
        assert alvo_db.password  # senha local intacta

    # A conta nova entra no alvo; a antiga volta ao fluxo normal sem 500.
    resposta = _callback(client)
    assert resposta.status_code == 302
    with client.session_transaction() as sess:
        assert sess["_user_id"] == str(ids[1])

    _simular_callback(monkeypatch, SUB_ANTIGO, EMAIL_GOOGLE_ANTIGO)
    resposta = _callback(client)
    assert resposta.status_code == 302
    assert "500" not in resposta.data.decode("utf-8")
    with app.app_context():
        antiga = db.session.execute(
            select(User).where(User.google_id == SUB_ANTIGO)
        ).scalars().one()
        assert antiga.role == UserRole.PENDENTE.value
        assert db.session.get(User, ids[1]).google_id == SUB_NOVO


def test_troca_com_email_google_igual_ao_local(app, client, monkeypatch):
    from _helpers import login_as

    _configurar_google(app)
    # Neste cenário o e-mail Google é o mesmo do cadastro local (domínio
    # institucional), então ele também precisa estar na lista de domínios.
    app.config["GOOGLE_OAUTH_ALLOWED_DOMAINS"] = ["google.example", "teste.local"]
    with app.app_context():
        admin, alvo, _, unidade, _ = _cenario(app)
        ids = (admin.id, alvo.id, unidade.id)

    login_as(client, ids[0], ids[2])
    assert "Conta Google desvinculada." in _post_desvincular(
        client, ids[1], EMAIL_ALVO
    ).data.decode("utf-8")

    # Mesmo e-mail do cadastro local: não cria pendente, exige confirmação.
    _simular_callback(monkeypatch, SUB_NOVO, EMAIL_ALVO)
    resposta = _callback(client)
    assert resposta.status_code == 302
    assert "/auth/google/confirmar-vinculo" in resposta.headers["Location"]

    html = client.get("/auth/google/confirmar-vinculo").data.decode("utf-8")
    assert "Vincular Conta Google" in html
    assert "Confirme sua senha" in html
    resposta = client.post(
        "/auth/google/confirmar-vinculo",
        data={"acao": "confirmar", "senha_atual": SENHA},
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    with client.session_transaction() as sess:
        assert sess["_user_id"] == str(ids[1])
    with app.app_context():
        assert db.session.get(User, ids[1]).google_id == SUB_NOVO
        assert (
            db.session.execute(
                select(func.count()).select_from(User).where(User.email == EMAIL_ALVO)
            ).scalar()
            == 1
        )

    # Login local continua funcionando e a conta Google antiga não quebra.
    cliente_local = app.test_client()
    resposta = cliente_local.post(
        "/login", data={"email": EMAIL_ALVO, "password": SENHA}
    )
    assert resposta.status_code == 302

    _simular_callback(monkeypatch, SUB_ANTIGO, EMAIL_GOOGLE_ANTIGO)
    resposta = _callback(cliente_local)
    assert resposta.status_code == 302
    with app.app_context():
        antiga = db.session.execute(
            select(User).where(User.google_id == SUB_ANTIGO)
        ).scalars().one()
        assert antiga.role == UserRole.PENDENTE.value
        assert antiga.id != ids[1]
        assert db.session.get(User, ids[1]).google_id == SUB_NOVO
