"""AJ24 / AJ24-B — admin vincula conta Google pendente a usuário existente.

Cobre: UI no painel admin, transferência atômica de ``google_id``/``google_email``
sem mover registros do alvo, varredura estrita de FKs (com a exceção de
``log_acao.usuario_id`` no AJ24-B), validações de alvo, permissão/CSRF, rollback
e auditoria. Nenhuma migration é necessária: as colunas já existem (ver
migration ``6a8df39d``).
"""

from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest
from google_auth_oauthlib.flow import Flow
from sqlalchemy import Column, ForeignKey, Integer, Table, func, select

from app import db
from app.models import Aluno, Frequencia, LogAcao, Turma, Unidade, User
from app.models.enums import UserRole
from app.services.vinculo_google_admin import (
    logs_a_reapontar,
    referencias_a_usuario,
    vincular_conta_google_pendente,
)

ORIGEM_EMAIL = "fabianomotta@projetograel.org.br"
ALVO_EMAIL = "fabianomotta@pgrael.local"
GOOGLE_ID = "aid-google-aj24-123"


def _criar_usuario(
    email,
    role,
    *,
    nome=None,
    ativo=True,
    google_id=None,
    google_email=None,
    unidade=None,
    is_ad=False,
):
    usuario = User(
        name=nome or email.split("@")[0],
        email=email,
        role=role,
        is_active=ativo,
        is_ad_user=is_ad,
        first_login=False,
        google_id=google_id,
        google_email=google_email,
    )
    if unidade is not None:
        usuario.unidade_id = unidade.id
    db.session.add(usuario)
    db.session.commit()
    return usuario


def _cenario(app, *, com_referencias_no_alvo=True):
    """Cria admin, alvo (Professor/NIT) e pendente (Global) com identidade Google."""
    unidade = Unidade(nome="NIT AJ24", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    admin = _criar_usuario(
        "admin.aj24@teste.local", UserRole.ADMIN.value, nome="Admin AJ24", unidade=unidade
    )
    alvo = _criar_usuario(
        ALVO_EMAIL,
        UserRole.PROFESSOR.value,
        nome="Fabio Motta NIT",
        unidade=unidade,
        is_ad=True,
    )
    pendente = _criar_usuario(
        ORIGEM_EMAIL,
        UserRole.PENDENTE.value,
        nome="Fabio Motta Google",
        google_id=GOOGLE_ID,
        google_email=ORIGEM_EMAIL,
    )

    if com_referencias_no_alvo:
        turma = Turma(
            nome="Turma AJ24",
            turno="Manhã",
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            unidade_id=unidade.id,
            professor_id=alvo.id,
            ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        aluno = Aluno(nome="Aluno AJ24", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        db.session.add(
            Frequencia(
                aluno_id=aluno.id,
                turma_id=turma.id,
                data=date(2026, 2, 2),
                conceito="A",
                unidade_id=unidade.id,
                autor_id=alvo.id,
            )
        )
        db.session.add(
            LogAcao(
                usuario_id=alvo.id,
                usuario_nome=alvo.name,
                acao="Acesso via Google",
                detalhes="marcador=alvo-aj24",
                ip="127.0.0.1",
            )
        )
        db.session.commit()

    return admin, alvo, pendente, unidade


def _post_vinculo(client, origem_id, alvo_id, origem_email, alvo_email):
    return client.post(
        f"/usuarios/vincular-google/{origem_id}",
        data={
            "alvo_id": str(alvo_id),
            "origem_email": origem_email,
            "alvo_email": alvo_email,
            "confirmar": "1",
        },
        follow_redirects=True,
    )


def _configurar_google(app):
    app.config.update(
        GOOGLE_OAUTH_CLIENT_ID="cliente-aj24",
        GOOGLE_OAUTH_CLIENT_SECRET="segredo-aj24",
        GOOGLE_OAUTH_REDIRECT_URI="https://sistema.example.com/auth/google/callback",
        GOOGLE_OAUTH_ALLOWED_DOMAINS=["projetograel.org.br"],
        GOOGLE_OAUTH_REQUIRE_EMAIL_VERIFIED=True,
    )


def _simular_callback_google(monkeypatch):
    """Faz o callback devolver a identidade da pendente já unificada."""

    class FlowFalso:
        def __init__(self, config, scopes, state):
            self.credentials = SimpleNamespace(token="token-falso-aj24")
            self.redirect_uri = None
            self.code_verifier = None

        def fetch_token(self, **kwargs):
            return None

    class RespostaFalsa:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "sub": GOOGLE_ID,
                "email": ORIGEM_EMAIL,
                "email_verified": True,
                "name": "Fabio Motta Google",
            }

    monkeypatch.setattr(
        Flow,
        "from_client_config",
        classmethod(
            lambda cls, config, scopes, state: FlowFalso(config, scopes, state)
        ),
    )
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: RespostaFalsa())


def _criar_logs_na_pendente(pendente, acoes):
    """Sementes de log de acesso da pendente (o cenário real do AJ24-B)."""
    for indice, acao in enumerate(acoes, start=1):
        db.session.add(
            LogAcao(
                usuario_id=pendente.id,
                usuario_nome=pendente.name,
                acao=acao,
                detalhes=f"marcador=pendente-aj24-{indice}",
                ip="127.0.0.1",
            )
        )
    db.session.commit()


# ---------------------------------------------------------------------------
# UI / permissão / CSRF
# ---------------------------------------------------------------------------


def test_painel_admin_ofere_acao_e_alvos_validos(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, unidade = _cenario(app)
        _criar_usuario("inativo@teste.local", UserRole.PROFESSOR.value, ativo=False)
        _criar_usuario(
            "outro.google@teste.local",
            UserRole.PROFESSOR.value,
            google_id="outro-id",
            google_email="outro.google@teste.local",
        )
        ids = (admin.id, alvo.id, pendente.id, unidade.id)

    login_as(client, ids[0])
    html = client.get("/admin/painel").data.decode("utf-8")

    assert f'id="vincularGoogleModal{ids[2]}"' in html
    assert f'action="/usuarios/vincular-google/{ids[2]}"' in html
    assert ORIGEM_EMAIL in html
    select = re.search(
        rf'<select[^>]*id="alvoSelect{ids[2]}".*?</select>', html, re.DOTALL
    )
    assert select is not None
    opcoes = select.group(0)
    assert f'value="{ids[1]}"' in opcoes
    assert ALVO_EMAIL in opcoes
    assert "Fabio Motta NIT" in opcoes
    assert "Professor" in opcoes
    assert "NIT AJ24" in opcoes
    # Alvos inválidos não aparecem como opção do select (a listagem os mostra).
    assert "inativo@teste.local" not in opcoes
    assert "outro.google@teste.local" not in opcoes
    # O alvo não é renderizado como pendente com ação de vínculo.
    assert f'id="vincularGoogleModal{ids[1]}"' not in html


def test_nao_admin_recebe_403(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app)
        professor = _criar_usuario("prof.aj24@teste.local", UserRole.PROFESSOR.value)
        ids = (professor.id, alvo.id, pendente.id)

    login_as(client, ids[0])
    resposta = _post_vinculo(client, ids[2], ids[1], ORIGEM_EMAIL, ALVO_EMAIL)
    assert resposta.status_code == 403


def test_post_sem_token_csrf_e_recusado(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app)
        ids = (admin.id, alvo.id, pendente.id)

    login_as(client, ids[0])
    app.config["WTF_CSRF_ENABLED"] = True
    resposta = client.post(
        f"/usuarios/vincular-google/{ids[2]}",
        data={
            "alvo_id": str(ids[1]),
            "origem_email": ORIGEM_EMAIL,
            "alvo_email": ALVO_EMAIL,
            "confirmar": "1",
        },
    )
    assert resposta.status_code == 400


def test_sem_confirmacao_explicita_nao_vincula(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app)
        ids = (admin.id, alvo.id, pendente.id)

    login_as(client, ids[0])
    resposta = client.post(
        f"/usuarios/vincular-google/{ids[2]}",
        data={
            "alvo_id": str(ids[1]),
            "origem_email": ORIGEM_EMAIL,
            "alvo_email": ALVO_EMAIL,
        },
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "Confirme a vinculação" in resposta.data.decode("utf-8")
    with app.app_context():
        assert db.session.get(User, ids[2]).google_id == GOOGLE_ID
        assert db.session.get(User, ids[1]).google_id is None


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------


def test_unificacao_preserva_registros_e_identidade_do_alvo(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, unidade = _cenario(app)
        contagens_alvo_antes = referencias_a_usuario(alvo.id)
        assert contagens_alvo_antes  # frequência, turma e log continuam no alvo
        assert referencias_a_usuario(pendente.id) == {}
        ids = (admin.id, alvo.id, pendente.id)
        papel = alvo.role
        unidade_id = alvo.unidade_id
        senha = alvo.password
        is_ad = alvo.is_ad_user

    login_as(client, ids[0])
    resposta = _post_vinculo(client, ids[2], ids[1], ORIGEM_EMAIL, ALVO_EMAIL)
    assert resposta.status_code == 200
    assert "vinculada a" in resposta.data.decode("utf-8")

    with app.app_context():
        assert db.session.get(User, ids[2]) is None
        alvo_db = db.session.get(User, ids[1])
        assert alvo_db.google_id == GOOGLE_ID
        assert alvo_db.google_email == ORIGEM_EMAIL
        assert (alvo_db.role, alvo_db.unidade_id, alvo_db.password, alvo_db.is_ad_user) == (
            papel,
            unidade_id,
            senha,
            is_ad,
        )
        assert referencias_a_usuario(alvo.id) == contagens_alvo_antes


def test_login_google_seguinte_cai_no_alvo(app, client, monkeypatch):
    from _helpers import login_as

    _configurar_google(app)
    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app, com_referencias_no_alvo=False)
        ids = (admin.id, alvo.id, pendente.id)

    login_as(client, ids[0])
    resposta = _post_vinculo(client, ids[2], ids[1], ORIGEM_EMAIL, ALVO_EMAIL)
    assert resposta.status_code == 200

    with client.session_transaction() as sess:
        sess["google_oauth_state"] = "estado-aj24"
        sess["google_code_verifier"] = "verificador-aj24"
    _simular_callback_google(monkeypatch)

    resposta = client.get("/auth/google/callback?state=estado-aj24&code=codigo-aj24")
    assert resposta.status_code == 302
    with client.session_transaction() as sess:
        assert sess["_user_id"] == str(ids[1])

    with app.app_context():
        alvo_db = db.session.get(User, ids[1])
        assert alvo_db.role == UserRole.PROFESSOR.value
        assert alvo_db.google_email == ORIGEM_EMAIL
        assert alvo_db.email == ALVO_EMAIL  # login local/AD continua no e-mail antigo


def test_log_acao_registra_admin_origem_alvo_e_emails(app, client):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app)
        ids = (admin.id, alvo.id, pendente.id)

    login_as(client, ids[0])
    _post_vinculo(client, ids[2], ids[1], ORIGEM_EMAIL, ALVO_EMAIL)

    with app.app_context():
        logs = (
            db.session.execute(
                select(LogAcao).where(LogAcao.acao == "Alteração de Cadastros")
            )
            .scalars()
            .all()
        )
        assert len(logs) == 1
        log = logs[0]
        assert log.usuario_id == ids[0]
        assert log.usuario_nome == "Admin AJ24"
        assert f"origem_id={ids[2]}" in log.detalhes
        assert f"alvo_id={ids[1]}" in log.detalhes
        assert ORIGEM_EMAIL in log.detalhes
        assert ALVO_EMAIL in log.detalhes
        assert f"google_email={ORIGEM_EMAIL}" in log.detalhes
        assert "logs_reapontados=0" in log.detalhes
        assert "token" not in log.detalhes.lower()
        assert "secret" not in log.detalhes.lower()


# ---------------------------------------------------------------------------
# AJ24-B — reaponte de log_acao.usuario_id
# ---------------------------------------------------------------------------


def test_logs_da_pendente_sao_reapontados_e_contabilizados(app, client):
    from _helpers import login_as

    acoes = ("Acesso via Google", "Login Google", "Acesso via Google")
    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app, com_referencias_no_alvo=False)
        _criar_logs_na_pendente(pendente, acoes)
        ids = (admin.id, alvo.id, pendente.id)
        # A FK de log é a única fora da varredura estrita de recusa.
        assert "log_acao.usuario_id" not in referencias_a_usuario(ids[2])
        assert logs_a_reapontar(ids[2]) == len(acoes)

    login_as(client, ids[0])
    resposta = _post_vinculo(client, ids[2], ids[1], ORIGEM_EMAIL, ALVO_EMAIL)
    assert resposta.status_code == 200

    with app.app_context():
        movidos = db.session.execute(
            select(LogAcao)
            .where(LogAcao.detalhes.like("marcador=pendente-aj24-%"))
            .order_by(LogAcao.id)
        ).scalars().all()
        assert len(movidos) == len(acoes)
        assert {log.usuario_id for log in movidos} == {ids[1]}
        assert [log.acao for log in movidos] == list(acoes)
        assert db.session.execute(
            select(func.count())
            .select_from(LogAcao)
            .where(LogAcao.usuario_id == ids[2])
        ).scalar() == 0
        assert logs_a_reapontar(ids[2]) == 0
        assert logs_a_reapontar(ids[1]) == len(acoes)

        log_unificacao = db.session.execute(
            select(LogAcao).where(LogAcao.acao == "Alteração de Cadastros")
        ).scalars().one()
        assert f"admin_id={ids[0]}" in log_unificacao.detalhes
        assert f"origem_id={ids[2]}" in log_unificacao.detalhes
        assert f"alvo_id={ids[1]}" in log_unificacao.detalhes
        assert ORIGEM_EMAIL in log_unificacao.detalhes
        assert ALVO_EMAIL in log_unificacao.detalhes
        assert f"google_email={ORIGEM_EMAIL}" in log_unificacao.detalhes
        assert f"logs_reapontados={len(acoes)}" in log_unificacao.detalhes
        assert "token" not in log_unificacao.detalhes.lower()
        assert "secret" not in log_unificacao.detalhes.lower()


def test_relacao_logs_carregada_nao_anula_o_reaponte(app):
    """A relação ``User.logs`` carregada antes do UPDATE não pode anulá-lo."""
    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app, com_referencias_no_alvo=False)
        _criar_logs_na_pendente(pendente, ("Acesso via Google", "Login Google"))
        assert len(pendente.logs) == 2  # força o carregamento da relação

        vincular_conta_google_pendente(pendente.id, alvo.id, admin_id=admin.id)

        assert logs_a_reapontar(alvo.id) == 2
        assert logs_a_reapontar(pendente.id) == 0
        assert {log.usuario_id for log in alvo.logs} == {alvo.id}


def test_erro_depois_do_update_faz_rollback_dos_logs(app, monkeypatch):
    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app, com_referencias_no_alvo=False)
        _criar_logs_na_pendente(pendente, ("Acesso via Google", "Login Google"))
        ids = (admin.id, alvo.id, pendente.id)

        def _falha_depois_do_update(*args, **kwargs):
            raise RuntimeError("erro simulado depois do UPDATE")

        monkeypatch.setattr(
            "app.services.vinculo_google_admin._registrar_log",
            _falha_depois_do_update,
        )
        with pytest.raises(RuntimeError, match="depois do UPDATE"):
            vincular_conta_google_pendente(ids[2], ids[1], admin_id=ids[0])

        # O UPDATE dos logs e o DELETE da pendente foram desfeitos juntos.
        assert db.session.get(User, ids[2]) is not None
        assert db.session.get(User, ids[2]).google_id == GOOGLE_ID
        assert db.session.get(User, ids[1]).google_id is None
        assert logs_a_reapontar(ids[2]) == 2
        assert logs_a_reapontar(ids[1]) == 0
        assert db.session.execute(
            select(func.count())
            .select_from(LogAcao)
            .where(LogAcao.acao == "Alteração de Cadastros")
        ).scalar() == 0


# ---------------------------------------------------------------------------
# Recusas
# ---------------------------------------------------------------------------


def test_recusa_quando_pendente_tem_referencias_em_outra_tabela(app, client):
    """AJ24-B: log sozinho não recusa; qualquer outra FK continua recusando."""
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, unidade = _cenario(app)
        db.session.add(
            Turma(
                nome="Turma da pendente",
                turno="Manhã",
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 12, 31),
                unidade_id=unidade.id,
                professor_id=pendente.id,
                ativo=True,
            )
        )
        _criar_logs_na_pendente(pendente, ("Acesso via Google",))
        db.session.commit()
        ids = (admin.id, alvo.id, pendente.id)
        logs_alvo_antes = logs_a_reapontar(alvo.id)

    login_as(client, ids[0])
    resposta = _post_vinculo(client, ids[2], ids[1], ORIGEM_EMAIL, ALVO_EMAIL)
    html = resposta.data.decode("utf-8")
    assert "possui registros vinculados" in html
    assert "turma.professor_id=1" in html  # formato tabela.coluna=contagem
    assert "log_acao.usuario_id" not in html  # eximida da recusa
    with app.app_context():
        assert db.session.get(User, ids[2]) is not None
        assert db.session.get(User, ids[2]).google_id == GOOGLE_ID
        assert db.session.get(User, ids[1]).google_id is None
        # Nada foi movido: o log segue na pendente e o alvo não ganhou linhas.
        assert logs_a_reapontar(ids[2]) == 1
        assert logs_a_reapontar(ids[1]) == logs_alvo_antes


@pytest.mark.parametrize(
    "alterar_alvo",
    ["ja_vinculado", "pendente", "inativo", "igual_origem"],
)
def test_recusa_alvos_invalidos(app, client, alterar_alvo):
    from _helpers import login_as

    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app)
        if alterar_alvo == "ja_vinculado":
            alvo.google_id = "outro-google-id"
            alvo.google_email = "outro@teste.local"
        elif alterar_alvo == "pendente":
            alvo.role = UserRole.PENDENTE.value
        elif alterar_alvo == "inativo":
            alvo.is_active = False
        db.session.commit()
        alvo_id = pendente.id if alterar_alvo == "igual_origem" else alvo.id
        alvo_email = ORIGEM_EMAIL if alterar_alvo == "igual_origem" else ALVO_EMAIL
        ids = (admin.id, alvo.id, pendente.id, alvo_id)

    login_as(client, ids[0])
    resposta = _post_vinculo(client, ids[2], ids[3], ORIGEM_EMAIL, alvo_email)
    html = resposta.data.decode("utf-8")
    mensagens = {
        "ja_vinculado": "já possui vínculo",
        "pendente": "não pode ser pendente",
        "inativo": "precisa estar ativa",
        "igual_origem": "não pode ser a própria conta",
    }
    assert mensagens[alterar_alvo] in html
    with app.app_context():
        assert db.session.get(User, ids[2]) is not None
        alvo_db = db.session.get(User, ids[1])
        if alterar_alvo != "ja_vinculado":
            assert alvo_db.google_id is None


def test_servico_recusa_origem_sem_identidade_google(app):
    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app)
        pendente.google_id = None
        pendente.google_email = None
        db.session.commit()
        with pytest.raises(ValueError, match="identidade Google"):
            vincular_conta_google_pendente(
                pendente.id, alvo.id, admin_id=admin.id
            )


def test_erro_no_meio_faz_rollback_total(app, monkeypatch):
    with app.app_context():
        admin, alvo, pendente, _ = _cenario(app)
        ids = (admin.id, alvo.id, pendente.id)

        def _falha_no_log(*args, **kwargs):
            raise RuntimeError("erro simulado no meio da transação")

        monkeypatch.setattr(
            "app.services.vinculo_google_admin._registrar_log", _falha_no_log
        )
        with pytest.raises(RuntimeError, match="erro simulado"):
            vincular_conta_google_pendente(ids[2], ids[1], admin_id=ids[0])

        assert db.session.get(User, ids[2]) is not None
        origem_db = db.session.get(User, ids[2])
        assert origem_db.google_id == GOOGLE_ID
        assert db.session.get(User, ids[1]).google_id is None


def test_varredura_de_fk_usa_metadata_do_sqlalchemy(app):
    """Uma FK criada em runtime é vista sem tocar em lista manual de tabelas."""
    tabela = Table(
        "aj24_probe_fk",
        db.metadata,
        Column("id", Integer, primary_key=True),
        Column("user_id", Integer, ForeignKey("user.id")),
    )
    with app.app_context():
        _, _, pendente, _ = _cenario(app)
        try:
            tabela.create(bind=db.engine)
            db.session.execute(tabela.insert().values(id=1, user_id=pendente.id))
            db.session.commit()
            assert referencias_a_usuario(pendente.id)["aj24_probe_fk.user_id"] == 1
        finally:
            db.session.remove()
            tabela.drop(bind=db.engine, checkfirst=True)
            db.metadata.remove(tabela)
