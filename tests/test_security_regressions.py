import pytest
from werkzeug.exceptions import Forbidden

from app import create_app
from app.database import db
from app.models import User, Unidade, Aluno, Turma
from app.registros.shared import assert_unidade_context


@pytest.fixture
def app():
    test_app = create_app()
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost",
    })
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_pending_user_redirected_to_approval_screen(client, app):
    with app.app_context():
        user = User(
            name="Usuário Pendente",
            email="pendente@example.com",
            role="pendente",
            first_login=False,
        )
        user.set_password("Abc12345!")
        db.session.add(user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/aguardando-aprovacao")


def test_first_login_user_redirected_to_password_change(client, app):
    with app.app_context():
        user = User(
            name="Usuário Primeiro Acesso",
            email="primeiro@example.com",
            role="professor",
            first_login=True,
        )
        user.set_password("Abc12345!")
        db.session.add(user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/trocar-senha")


def test_change_password_requires_current_password(client, app):
    with app.app_context():
        user = User(
            name="Usuário Senha",
            email="senha@example.com",
            role="professor",
            first_login=False,
        )
        user.set_password("SenhaAtual!1")
        db.session.add(user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        resp = client.post(
            "/trocar-senha",
            data={
                "nova_senha": "NovaSenha!2",
                "confirma_senha": "NovaSenha!2",
                "senha_atual": "SenhaErrada!9",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/trocar-senha")

        updated = db.session.get(User, user.id)
        assert updated.check_password("SenhaAtual!1")
        assert not updated.check_password("NovaSenha!2")


def test_assert_unidade_context_rejects_missing_local_unidade():
    with pytest.raises(Forbidden):
        assert_unidade_context(10, None)


def test_historico_aluno_rejects_unrelated_professor(client, app):
    with app.app_context():
        unidade = Unidade(nome="Unidade A", ativo=True)
        db.session.add(unidade)
        db.session.commit()

        professor = User(
            name="Professor Sem Turma",
            email="professor_sem_turma@example.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        professor.set_password("Abc12345!")
        db.session.add(professor)
        db.session.commit()

        aluno = Aluno(nome="Aluno X", nome_social="Aluno", ativo=True, unidade_id=unidade.id)
        db.session.add(aluno)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(professor.id)
            sess["_fresh"] = True

        resp = client.get(f"/aluno/{aluno.id}/historico")
        assert resp.status_code == 403


def test_api_alunos_requires_authorized_role(client, app):
    with app.app_context():
        unidade = Unidade(nome="Unidade B", ativo=True)
        db.session.add(unidade)
        db.session.commit()

        professor = User(
            name="Professor Sem Acesso",
            email="professor_sem_acesso@example.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        professor.set_password("Abc12345!")
        db.session.add(professor)
        db.session.commit()

        turma = Turma(nome="Turma 7A", ativo=True, unidade_id=unidade.id)
        db.session.add(turma)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(professor.id)
            sess["_fresh"] = True

        resp = client.get(f"/api/alunos/{turma.id}")
        assert resp.status_code == 403


def test_mutating_routes_reject_get_requests(client):
    routes = [
        "/aluno/excluir/1",
        "/aluno/inativar/1",
        "/turma/desenturmar/1",
        "/periodo-letivo/inativar/1",
        "/periodo-letivo/ativar/1",
        "/servico-social/excluir-agendamento/1",
    ]

    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 405
