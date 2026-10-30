"""Papéis e CSRF dos períodos de conselho (S1-05).

`/informacoes`, `POST /api/conselho-periodo` e
`DELETE /api/conselho-periodo/<id>` passam a exigir os papéis de
Conselho > Data-Informações (admin, pedagógico, gerência, secretaria), a
validar a unidade do conselho e a exigir token CSRF.
"""

import re
from datetime import date

import pytest

from app import create_app, db
from app.models import PeriodoConselho, PeriodoLetivo, Unidade, User
from config import Config
from _helpers import login_as


class CSRFTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = True


@pytest.fixture
def app_csrf():
    """App com CSRF ligado e **sem** app_context empilhado durante as requests.

    O fixture `app` do conftest mantém o app context aberto; ali a sessão do
    Flask é compartilhada entre requests e o CSRF daria falso negativo.
    """
    app = create_app(CSRFTestConfig)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client_csrf(app_csrf):
    return app_csrf.test_client()


@pytest.fixture
def dados(app_csrf):
    with app_csrf.app_context():
        u1 = Unidade(nome="Unidade S1-05 A", ativo=True)
        u2 = Unidade(nome="Unidade S1-05 B", ativo=True)
        db.session.add_all([u1, u2])
        db.session.flush()

        p1 = PeriodoLetivo(
            nome="2026.1",
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            unidade_id=u1.id,
            ativo=True,
        )
        p2 = PeriodoLetivo(
            nome="2026.1",
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            unidade_id=u2.id,
            ativo=True,
        )
        db.session.add_all([p1, p2])
        db.session.flush()

        usuarios = {}
        for papel in ("admin", "pedagogico", "gerencia", "secretaria", "professor"):
            usuario = User(
                name=papel.title(),
                email=f"{papel}.s1-05@example.com",
                role=papel,
                unidade_id=u1.id,
                is_active=True,
                first_login=False,
            )
            db.session.add(usuario)
            usuarios[papel] = usuario
        db.session.flush()

        conselho_u1 = PeriodoConselho(
            nome="Conselho da unidade A",
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 2),
            periodo_letivo_id=p1.id,
            unidade_id=u1.id,
        )
        conselho_u2 = PeriodoConselho(
            nome="Conselho da unidade B",
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 2),
            periodo_letivo_id=p2.id,
            unidade_id=u2.id,
        )
        db.session.add_all([conselho_u1, conselho_u2])
        db.session.commit()

        return {
            "unidade_a": u1.id,
            "unidade_b": u2.id,
            "periodo_a": p1.id,
            "conselho_a": conselho_u1.id,
            "conselho_b": conselho_u2.id,
            "usuarios": {papel: usuario.id for papel, usuario in usuarios.items()},
        }


def _token(client_csrf, usuario_id, unidade_id, caminho="/informacoes"):
    login_as(client_csrf, usuario_id, unidade_id)
    pagina = client_csrf.get(caminho, follow_redirects=True)
    assert pagina.status_code == 200, pagina.status_code
    achado = re.search(
        r'<meta name="csrf-token" content="([^"]+)"', pagina.get_data(as_text=True)
    )
    assert achado, "meta csrf-token ausente"
    return achado.group(1)


@pytest.mark.parametrize("papel", ["admin", "pedagogico", "gerencia", "secretaria"])
def test_papeis_permitidos_acessam_informacoes(client_csrf, dados, papel):
    login_as(client_csrf, dados["usuarios"][papel], dados["unidade_a"])
    assert client_csrf.get("/informacoes").status_code == 200


def test_professor_recebe_403_em_informacoes(client_csrf, dados):
    login_as(client_csrf, dados["usuarios"]["professor"], dados["unidade_a"])
    assert client_csrf.get("/informacoes").status_code == 403


def test_professor_recebe_403_no_post_e_no_delete(client_csrf, dados):
    # O token vem do painel do professor: o CSRF é avaliado antes do papel.
    token = _token(
        client_csrf, dados["usuarios"]["professor"], dados["unidade_a"], "/painel"
    )

    resposta = client_csrf.post(
        "/api/conselho-periodo",
        json={
            "nome": "Tentativa",
            "data_inicio": "2026-06-01",
            "data_fim": "2026-06-02",
            "periodo_letivo_id": dados["periodo_a"],
        },
        headers={"X-CSRFToken": token},
    )
    assert resposta.status_code == 403
    assert (
        client_csrf.delete(
            f"/api/conselho-periodo/{dados['conselho_a']}",
            headers={"X-CSRFToken": token},
        ).status_code
        == 403
    )


def test_anonimo_e_redirecionado_para_login(client_csrf, dados):
    resposta = client_csrf.get("/informacoes")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_post_sem_token_csrf_e_recusado(client_csrf, dados):
    login_as(client_csrf, dados["usuarios"]["admin"], dados["unidade_a"])

    resposta = client_csrf.post(
        "/api/conselho-periodo",
        json={
            "nome": "Sem token",
            "data_inicio": "2026-06-01",
            "data_fim": "2026-06-02",
            "periodo_letivo_id": dados["periodo_a"],
        },
    )
    assert resposta.status_code == 400
    assert "application/json" not in resposta.headers.get("Content-Type", "")


def test_delete_sem_token_csrf_e_recusado(client_csrf, dados):
    login_as(client_csrf, dados["usuarios"]["admin"], dados["unidade_a"])

    resposta = client_csrf.delete(f"/api/conselho-periodo/{dados['conselho_a']}")
    assert resposta.status_code == 400
    assert "application/json" not in resposta.headers.get("Content-Type", "")


def test_post_com_token_cria_periodo(client_csrf, dados):
    token = _token(client_csrf, dados["usuarios"]["pedagogico"], dados["unidade_a"])

    resposta = client_csrf.post(
        "/api/conselho-periodo",
        json={
            "nome": "Conselho criado no teste",
            "data_inicio": "2026-07-01",
            "data_fim": "2026-07-03",
            "periodo_letivo_id": dados["periodo_a"],
        },
        headers={"X-CSRFToken": token},
    )

    assert resposta.status_code == 200
    assert resposta.get_json() == {"success": True}


def test_delete_com_token_remove_periodo(client_csrf, dados):
    token = _token(client_csrf, dados["usuarios"]["secretaria"], dados["unidade_a"])

    resposta = client_csrf.delete(
        f"/api/conselho-periodo/{dados['conselho_a']}",
        headers={"X-CSRFToken": token},
    )

    assert resposta.status_code == 200
    assert resposta.get_json() == {"success": True}


def test_escrita_em_conselho_de_outra_unidade_recebe_403(client_csrf, dados):
    token = _token(client_csrf, dados["usuarios"]["admin"], dados["unidade_a"])

    resposta = client_csrf.post(
        "/api/conselho-periodo",
        json={
            "id": dados["conselho_b"],
            "nome": "Invasão",
            "data_inicio": "2026-06-01",
            "data_fim": "2026-06-02",
            "periodo_letivo_id": dados["periodo_a"],
        },
        headers={"X-CSRFToken": token},
    )
    assert resposta.status_code == 403


def test_exclusao_de_conselho_de_outra_unidade_recebe_403(client_csrf, dados):
    token = _token(client_csrf, dados["usuarios"]["admin"], dados["unidade_a"])

    resposta = client_csrf.delete(
        f"/api/conselho-periodo/{dados['conselho_b']}",
        headers={"X-CSRFToken": token},
    )
    assert resposta.status_code == 403


def test_exclusao_de_conselho_inexistente_recebe_404(client_csrf, dados):
    token = _token(client_csrf, dados["usuarios"]["admin"], dados["unidade_a"])

    resposta = client_csrf.delete(
        "/api/conselho-periodo/999999",
        headers={"X-CSRFToken": token},
    )
    assert resposta.status_code == 404

