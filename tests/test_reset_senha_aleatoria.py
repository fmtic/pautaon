from __future__ import annotations

import re
import pytest
from flask import session
from app.database import db
from app.models import User
from app.models.enums import UserRole
from app.services.auth_service import (
    generate_secure_random_password,
    validate_password_strength,
)
from _helpers import login_as


def _criar_usuario(email: str, role: str = "professor", is_ad_user: bool = False, nome: str = "Usuario Teste") -> User:
    user = User(
        name=nome,
        email=email,
        role=role,
        is_active=True,
        is_ad_user=is_ad_user,
        first_login=False,
    )
    if not is_ad_user:
        user.set_password("SenhaAntiga!123")
    db.session.add(user)
    db.session.commit()
    return user


class TestGeradorSenhaAleatoria:
    def test_senha_atende_todos_requisitos_de_complexidade(self):
        for _ in range(50):
            senha = generate_secure_random_password(12)
            assert len(senha) == 12
            assert validate_password_strength(senha) == []
            assert re.search(r"[A-Z]", senha)
            assert re.search(r"[a-z]", senha)
            assert re.search(r"\d", senha)
            assert re.search(r"""[!@#$%^&*()\-_=+\[\]{};:'",.<>?/\\|`~]""", senha)

    def test_senha_garante_comprimento_minimo_de_8(self):
        senha_curta = generate_secure_random_password(4)
        assert len(senha_curta) >= 8
        assert validate_password_strength(senha_curta) == []

    def test_senhas_geradas_sao_distintas(self):
        senhas = {generate_secure_random_password(14) for _ in range(30)}
        assert len(senhas) == 30


class TestResetSenhaAdmin:
    def test_admin_reseta_senha_com_geracao_aleatoria(self, app, client, monkeypatch):
        admin = _criar_usuario("admin.reset@teste.invalid", role="admin", nome="Admin Teste")
        alvo = _criar_usuario("alvo.reset@teste.invalid", role="professor", nome="Professor Alvo")

        emails_enviados = []
        monkeypatch.setattr("app.auth.send_email", lambda **kwargs: emails_enviados.append(kwargs))

        login_as(client, admin)

        resp = client.post(f"/usuarios/resetar/{alvo.id}")
        assert resp.status_code == 302

        # Verifica se o banco foi atualizado
        usuario_db = db.session.get(User, alvo.id)
        assert usuario_db.first_login is True
        assert usuario_db.session_version == 1

        # Verifica envio de e-mail
        assert len(emails_enviados) == 1
        corpo = emails_enviados[0]["body_html"]
        assert emails_enviados[0]["recipients"] == [alvo.email]

        # Extrai a senha temporária do e-mail ou do flash
        with client.session_transaction() as sess:
            flash_messages = sess.get("_flashes", [])
            mensagens_texto = " ".join(msg for _, msg in flash_messages)
            assert "resetada com sucesso" in mensagens_texto
            assert "Nova senha temporária gerada:" in mensagens_texto

        # Acessa o painel admin e verifica que o banner de senha gerada é exibido
        resp_painel = client.get("/admin/painel")
        assert resp_painel.status_code == 200
        html = resp_painel.get_data(as_text=True)
        assert "Senha Temporária Redefinida com Sucesso!" in html
        assert alvo.name in html
        assert alvo.email in html

        # Busca a senha temporária dentro do card e testa login do usuário alvo com ela
        match = re.search(r'id="campoSenhaGerada"[^>]*value="([^"]+)"', html)
        assert match is not None
        senha_gerada = match.group(1)
        assert usuario_db.check_password(senha_gerada) is True
        assert validate_password_strength(senha_gerada) == []

    def test_reset_bloqueia_usuario_ldap(self, app, client):
        admin = _criar_usuario("admin.ldap@teste.invalid", role="admin")
        ldap_user = _criar_usuario("alvo.ldap@teste.invalid", is_ad_user=True)

        login_as(client, admin)
        resp = client.post(f"/usuarios/resetar/{ldap_user.id}")
        assert resp.status_code == 302

        with client.session_transaction() as sess:
            flash_messages = sess.get("_flashes", [])
            textos = " ".join(msg for _, msg in flash_messages)
            assert "LDAP" in textos

    def test_reset_bloqueia_usuario_nao_admin(self, app, client):
        professor = _criar_usuario("prof.comum@teste.invalid", role="professor")
        alvo = _criar_usuario("alvo.comum@teste.invalid", role="professor")

        login_as(client, professor)
        resp = client.post(f"/usuarios/resetar/{alvo.id}")
        assert resp.status_code == 403


class TestCadastroUsuarioSenhaInicial:
    def test_cadastrar_usuario_gerando_senha_inicial_automatica(self, app, client, monkeypatch):
        admin = _criar_usuario("admin.cad@teste.invalid", role="admin")
        emails_enviados = []
        monkeypatch.setattr("app.auth.send_email", lambda **kwargs: emails_enviados.append(kwargs))

        login_as(client, admin)
        resp = client.post(
            "/admin/cadastrar",
            data={
                "nome": "Novo Usuario Automatico",
                "email": "novo.auto@teste.invalid",
                "role": "secretaria",
                "gerar_senha_inicial": "1",
                "password": "",
            },
        )
        assert resp.status_code == 302

        novo = db.session.query(User).filter_by(email="novo.auto@teste.invalid").first()
        assert novo is not None
        assert novo.name == "Novo Usuario Automatico"
        assert novo.first_login is True

        assert len(emails_enviados) == 1
        assert emails_enviados[0]["recipients"] == ["novo.auto@teste.invalid"]

        # Verifica flash
        with client.session_transaction() as sess:
            flash_messages = sess.get("_flashes", [])
            textos = " ".join(msg for _, msg in flash_messages)
            assert "Senha inicial gerada:" in textos

        # Verifica renderização no painel
        resp_painel = client.get("/admin/painel")
        html = resp_painel.get_data(as_text=True)
        assert "Senha Inicial Temporária Gerada com Sucesso!" in html
        assert "novo.auto@teste.invalid" in html

        match = re.search(r'id="campoSenhaGerada"[^>]*value="([^"]+)"', html)
        assert match is not None
        senha_gerada = match.group(1)
        assert novo.check_password(senha_gerada) is True
        assert validate_password_strength(senha_gerada) == []

    def test_cadastrar_usuario_com_senha_manual_forte(self, app, client, monkeypatch):
        admin = _criar_usuario("admin.manual@teste.invalid", role="admin")
        monkeypatch.setattr("app.auth.send_email", lambda **_: None)

        login_as(client, admin)
        resp = client.post(
            "/admin/cadastrar",
            data={
                "nome": "Novo Usuario Manual",
                "email": "novo.manual@teste.invalid",
                "role": "professor",
                "password": "SenhaForte!2026",
            },
        )
        assert resp.status_code == 302

        novo = db.session.query(User).filter_by(email="novo.manual@teste.invalid").first()
        assert novo is not None
        assert novo.check_password("SenhaForte!2026") is True
        assert novo.first_login is True

    def test_cadastrar_usuario_com_senha_manual_fraca_rejeita(self, app, client):
        admin = _criar_usuario("admin.fraco@teste.invalid", role="admin")

        login_as(client, admin)
        resp = client.post(
            "/admin/cadastrar",
            data={
                "nome": "Novo Usuario Fraco",
                "email": "novo.fraco@teste.invalid",
                "role": "professor",
                "password": "fraca",
            },
        )
        assert resp.status_code == 302

        novo = db.session.query(User).filter_by(email="novo.fraco@teste.invalid").first()
        assert novo is None

        with client.session_transaction() as sess:
            flash_messages = sess.get("_flashes", [])
            textos = " ".join(msg for _, msg in flash_messages)
            assert "A senha deve ter no mínimo 8 caracteres." in textos

