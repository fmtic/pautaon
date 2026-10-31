"""Fixtures compartilhadas da suíte (MER §12.16 / L5-E2).

Antes deste arquivo cada teste criava o próprio `app`/`client`: o censo de
30/10/2026 encontrou **58** definições em **15** grupos. Só os grupos
**idênticos** migraram para cá:

    - `app`     : 14 arquivos (o corpo canônico, sem `SERVER_NAME`);
    - `client`  : 14 arquivos (todos idênticos);
    - `app_com_servidor`: variante com `SERVER_NAME="localhost"` e asserção de
      dialeto, usada por `test_conselho_oferta.py` e mais 2 arquivos — ela é
      wrappada localmente (`def app(app_com_servidor)`) para não mudar
      comportamento.

As **outras 13 variantes** continuam locais por divergirem de propósito
(student sem `WTF_CSRF_ENABLED`, config inline, `UPLOAD_FOLDER` temporário,
migrations) — a lista está em `docs/Relatórios/L5_LimpezaTurmasHarness.md`.

Nada aqui muda o comportamento dos testes: banco SQLite em memória, schema via
`db.create_all()`, teardown com `db.session.remove()` + `db.drop_all()`.
"""

from pathlib import Path
import os
import sys

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# A suíte fala HTTP com o `test_client` (não há TLS): com o padrão seguro do
# `SESSION_COOKIE_SECURE` (True, S1-09) o navegador de teste descartaria o
# cookie de sessão e todo login falharia. `setdefault` preserva um `APP_ENV`
# já declarado no ambiente.
os.environ.setdefault("APP_ENV", "development")

from app import create_app, db  # noqa: E402
from config import Config  # noqa: E402


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def app_com_servidor():
    """Variante de `app` com `SERVER_NAME` (e guarda de dialeto SQLite).

    Idêntica à cópia local que `test_conselho_oferta.py` mantinha, onde o
    `SERVER_NAME="localhost"` é usado por testes de URL absoluta.
    """
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with test_app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def _limpar_login_controle(app):
    yield
    with app.app_context():
        try:
            from app.models import LoginControle
            LoginControle.query.delete()
            db.session.commit()
        except Exception:
            db.session.rollback()


@pytest.fixture
def client(app):
    return app.test_client()
