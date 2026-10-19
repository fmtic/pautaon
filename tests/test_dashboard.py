import re
from datetime import date

import pytest

from app import create_app, db
from app.models import PeriodoLetivo, Unidade, User
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with test_app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _prepare_dashboard(app, client):
    with app.app_context():
        unidade_a = Unidade(nome="Unidade A")
        unidade_b = Unidade(nome="Unidade B")
        user = User(
            name="Administrador",
            email="admin@example.com",
            role="admin",
            first_login=False,
        )
        db.session.add_all([unidade_a, unidade_b, user])
        db.session.flush()

        periodos = [
            PeriodoLetivo(
                nome="Ativo A",
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 12, 31),
                unidade_id=unidade_a.id,
                ativo=True,
            ),
            PeriodoLetivo(
                nome="Inativo A",
                data_inicio=date(2025, 1, 1),
                data_fim=date(2025, 12, 31),
                unidade_id=unidade_a.id,
                ativo=False,
            ),
            PeriodoLetivo(
                nome="Ativo B",
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 12, 31),
                unidade_id=unidade_b.id,
                ativo=True,
            ),
            PeriodoLetivo(
                nome="Ativo Global",
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 12, 31),
                unidade_id=None,
                ativo=True,
            ),
        ]
        db.session.add_all(periodos)
        db.session.commit()
        user_id = user.id
        unidade_a_id = unidade_a.id

    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True

    return unidade_a_id


def _periodos_ativos_exibidos(response):
    match = re.search(
        rb'<div class="text-muted small">Per\xc3\xadodos Ativos</div>'
        rb'\s*<div class="fs-3 fw-bold lh-sm">(\d+)</div>',
        response.data,
    )
    assert match is not None
    return int(match.group(1))


def test_dashboard_conta_periodos_ativos_global_incluindo_sem_unidade(app, client):
    _prepare_dashboard(app, client)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert _periodos_ativos_exibidos(response) == 3


def test_dashboard_filtra_periodos_ativos_pela_unidade_selecionada(app, client):
    unidade_a_id = _prepare_dashboard(app, client)
    with client.session_transaction() as session:
        session["unidade_id"] = unidade_a_id

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert _periodos_ativos_exibidos(response) == 1