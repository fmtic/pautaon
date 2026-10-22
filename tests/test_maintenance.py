import pytest

from app import create_app
from app.database import db
from app.models import ConfiguracaoSistema, User
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SERVER_NAME="localhost",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _create_user(app, role):
    with app.app_context():
        user = User(
            name=f"Usuário {role}",
            email=f"{role}@example.com",
            role=role,
            first_login=False,
        )
        user.set_password("SenhaLocal!123")
        db.session.add(user)
        db.session.commit()
        return user.id


def _authenticate(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_admin_can_enable_maintenance(client, app):
    admin_id = _create_user(app, "admin")
    _authenticate(client, admin_id)

    response = client.get("/admin/logs")
    assert response.status_code == 200
    assert b"SISTEMA ONLINE" in response.data

    response = client.post("/admin/manutencao/toggle")
    assert response.status_code == 302
    with app.app_context():
        setting = ConfiguracaoSistema.query.filter_by(
            chave="manutencao_ativa",
            unidade_id=None,
        ).one()
        assert setting.valor == "true"

    assert client.get("/admin/logs").status_code == 200


def test_maintenance_blocks_non_admin_users(client, app):
    user_id = _create_user(app, "professor")
    with app.app_context():
        db.session.add(
            ConfiguracaoSistema(
                chave="manutencao_ativa",
                valor="true",
                unidade_id=None,
            )
        )
        db.session.commit()
    _authenticate(client, user_id)

    response = client.get("/dashboard")
    assert response.status_code == 503
    assert "Estamos enfrentando problemas técnicos".encode() in response.data


def test_admin_can_disable_maintenance(client, app):
    admin_id = _create_user(app, "admin")
    with app.app_context():
        db.session.add(
            ConfiguracaoSistema(
                chave="manutencao_ativa",
                valor="true",
                unidade_id=None,
            )
        )
        db.session.commit()

    _authenticate(client, admin_id)
    response = client.post("/admin/manutencao/toggle")

    assert response.status_code == 302
    with app.app_context():
        setting = ConfiguracaoSistema.query.filter_by(
            chave="manutencao_ativa",
            unidade_id=None,
        ).one()
        assert setting.valor == "false"


def test_non_admin_cannot_toggle_maintenance(client, app):
    user_id = _create_user(app, "professor")
    _authenticate(client, user_id)

    assert client.post("/admin/manutencao/toggle").status_code == 403
