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

AJ6-C — Trava de banco de teste
---------------------------------
`config.py` chama `load_dotenv()` em nível de módulo, o que injetaria o
``DATABASE_URL`` do ``.env`` (PostgreSQL real) no ambiente antes de qualquer
``create_app()``. Para neutralizar:

1. Capturamos ``DATABASE_URL`` do OS **antes** de qualquer import.
2. Sobrescrevemos com SQLite — ``load_dotenv(override=False)`` não reverte.
3. ``pytest_configure`` aborta a suíte se o valor original era PostgreSQL.

Assim, qualquer ``create_app()`` sem override explícito de URI recebe SQLite
e **não** pode gravar no banco real.
"""

from pathlib import Path
from datetime import datetime
import os
import sys

# ── AJ6-C: captura e neutraliza DATABASE_URL ANTES de qualquer import ─────
# Deve ocorrer antes de `import pytest` e de `from app import ...`, pois o
# import de `app` dispara config.py → load_dotenv() que injetaria a URL real.
_DB_URL_ORIGINAL = os.environ.get("DATABASE_URL", "")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# ──────────────────────────────────────────────────────────────────────────

import pytest  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
_DIR_TESTES = Path(__file__).resolve().parent
if str(_DIR_TESTES) not in sys.path:
    sys.path.insert(0, str(_DIR_TESTES))

# A suíte fala HTTP com o `test_client` (não há TLS): com o padrão seguro do
# `SESSION_COOKIE_SECURE` (True, S1-09) o navegador de teste descartaria o
# cookie de sessão e todo login falharia. `setdefault` preserva um `APP_ENV`
# já declarado no ambiente.
os.environ.setdefault("APP_ENV", "development")

from app import create_app, db  # noqa: E402
from app.utils import logica as _logica, timezone as _tz  # noqa: E402
from config import Config  # noqa: E402
from _helpers import hoje_ref  # noqa: E402


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


#: Sentinela usada quando não é possível extrair driver/nome com segurança.
_URL_MASCARADA = "<url mascarada>"


def _resumo_url_banco(url: str) -> str:
    """AJ6-C rodada 2: resumo seguro de uma ``DATABASE_URL`` para logs.

    Devolve apenas ``driver + nome do banco`` (ex.: ``postgresql+psycopg/pautaon``)
    ou a sentinela ``<url mascarada>`` quando o parsing falha. Usuário, senha,
    host e porta jamais saem aqui — a mensagem de aborto da trava é impressa
    pelo pytest e não pode vazar credenciais.
    """
    if not url:
        return _URL_MASCARADA
    try:
        from sqlalchemy.engine import make_url

        parsed = make_url(url)
        banco = parsed.database or "<sem banco>"
        return f"{parsed.drivername}/{banco}"
    except Exception:
        return _URL_MASCARADA


def pytest_sessionstart(session):
    """AJ6-C: Aborta a suíte se DATABASE_URL no ambiente apontava para Postgres

    ou se o driver do engine não for sqlite. A mensagem mostra apenas o resumo
    mascarado (driver/banco) — nunca a URL completa com credenciais.
    """
    if "postgresql" in _DB_URL_ORIGINAL.lower() or "postgres" in _DB_URL_ORIGINAL.lower():
        pytest.exit(
            "ABORTAR — trava de banco de teste disparada (AJ6-C)!\n"
            f"DATABASE_URL no ambiente ({_resumo_url_banco(_DB_URL_ORIGINAL)}) aponta para PostgreSQL.\n"
            "A suíte de testes exige SQLite. Remova DATABASE_URL do ambiente antes de rodar pytest.",
            returncode=1,
        )

    # Valida que o app de teste instancia estritamente em SQLite
    test_app = create_app(SQLiteTestConfig)
    with test_app.app_context():
        driver = db.engine.url.drivername
        if not driver.startswith("sqlite"):
            pytest.exit(
                "ABORTAR — trava de banco de teste disparada (AJ6-C)!\n"
                f"Engine configurado com driver '{driver}' (esperado 'sqlite').\n"
                "Execução de testes contra banco não-SQLite é estritamente proibida.",
                returncode=1,
            )


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        assert db.engine.url.drivername.startswith("sqlite"), (
            f"Trava AJ6-C: driver '{db.engine.url.drivername}' não permitido. Exigido 'sqlite'."
        )
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


@pytest.fixture
def hoje_fixo(monkeypatch):
    """AJ4-B: congela o relógio do app no dia de referência (``hoje_ref``).

    Patcheia só os dois globais ``datetime`` por onde o "hoje" entra nos
    fluxos de calendário: ``app.utils.timezone`` (fonte de todo
    ``get_local_now``, inclusive os alias já importados alhures — o corpo
    consulta o global no momento da chamada) e ``app.utils.logica``
    (corte ``min(fim, datetime.now())`` de ``gerar_datas``). Não toca em
    ``app/**`` nem no runtime real: vale durante o teste, revertido pelo
    ``monkeypatch``.

    Use com as constantes ``hoje_ref()``/``dia_de_aula_ate()`` de
    ``_helpers``: a semente ancora no mesmo dia do relógio congelado.
    """
    ref = hoje_ref()

    class _DateTimeCongelado(datetime):
        @classmethod
        def now(cls, tz=None):
            base = cls(ref.year, ref.month, ref.day, 12, 0, 0)
            return base.replace(tzinfo=tz) if tz else base

        @classmethod
        def today(cls):
            return cls.now()

    monkeypatch.setattr(_tz, "datetime", _DateTimeCongelado)
    monkeypatch.setattr(_logica, "datetime", _DateTimeCongelado)
    return ref
