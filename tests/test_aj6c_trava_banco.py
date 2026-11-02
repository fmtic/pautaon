"""AJ6-C — Testes da Trava de Banco de Testes.

Garante que:
1. Se DATABASE_URL no ambiente apontar para PostgreSQL, a suíte se recusa
   a rodar imediatamente (pytest_sessionstart aborta com erro claro).
2. O app de testes e fixtures padrão utilizam estritamente o driver 'sqlite'.
3. O ambiente padrão de teste neutraliza DATABASE_URL do .env para que chamadas
   create_app() sem config explícita usem sqlite e não banco persistente.
"""

import os
import subprocess
import sys

from app import create_app, db


def test_trava_aborta_suite_quando_database_url_aponta_para_postgres():
    """Simula DATABASE_URL postgresql no ambiente e prova que a suíte aborta."""
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql://usuario_fake:senha_fake@localhost:5432/pautaon_fake"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_aj6a_painel_fumaca.py",
        "-k",
        "test_painel_sem_periodo_200",
    ]

    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    saida = proc.stdout + proc.stderr
    assert proc.returncode != 0, (
        "A suíte deveria ter abortado com retorno não-zero quando DATABASE_URL é PostgreSQL!"
    )
    assert "trava de banco de teste disparada (AJ6-C)" in saida or "ABORTAR" in saida, (
        f"Mensagem de trava esperada não encontrada na saída:\n{saida}"
    )
    assert "PostgreSQL" in saida or "postgres" in saida.lower()


def test_app_fixture_garante_driver_sqlite(app):
    """Garante que a fixture app ativa sempre o driver SQLite."""
    with app.app_context():
        assert db.engine.url.drivername == "sqlite"
        assert db.engine.dialect.name == "sqlite"


def test_trava_nao_vaza_credenciais_na_saida():
    """AJ6-C rodada 2: a mensagem de aborto jamais imprime a DATABASE_URL.

    Roda a suíte em subprocesso com ``DATABASE_URL`` apontando para um
    PostgreSQL fictício cujo usuário e senha são marcadores únicos. Prova que:

    1. a suíte aborta (retorno não-zero, mensagem da trava presente);
    2. o usuário e a senha fictícios não aparecem em stdout nem stderr;
    3. o resumo exibido traz apenas driver e nome do banco.
    """
    usuario_ficticio = "USUARIO-VAZA-TESTE-x9q"
    senha_ficticia = "SENHA-VAZA-TESTE-k3w"
    env = os.environ.copy()
    env["DATABASE_URL"] = (
        f"postgresql+psycopg://{usuario_ficticio}:{senha_ficticia}"
        "@db.example.invalid:5432/pautaon_sonda"
    )

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_aj6a_painel_fumaca.py",
        "-k",
        "test_painel_sem_periodo_200",
    ]

    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    saida = proc.stdout + proc.stderr
    assert proc.returncode != 0, "A suíte deveria abortar com DATABASE_URL PostgreSQL."
    assert "ABORTAR" in saida, f"Mensagem da trava não encontrada na saída:\n{saida}"
    # A regra anti-leak vale para toda a saída do processo, não só a linha:
    assert usuario_ficticio not in saida, (
        " vazamento: usuário da DATABASE_URL apareceu na saída do pytest!"
    )
    assert senha_ficticia not in saida, (
        " vazamento: senha da DATABASE_URL apareceu na saída do pytest!"
    )
    # O resumo seguro deve aparecer: driver + nome do banco, sem credenciais.
    assert "postgresql+psycopg/pautaon_sonda" in saida, (
        "Mensagem deveria mostrar apenas driver e nome do banco."
    )


def test_create_app_sem_override_recebe_sqlite_em_teste():
    """Garante que create_app() padrão em ambiente de testes herda SQLite."""
    # Como conftest.py neutralizou DATABASE_URL no os.environ para sqlite:///:memory:
    app_padrao = create_app()
    with app_padrao.app_context():
        assert db.engine.url.drivername == "sqlite"
        assert ":memory:" in str(db.engine.url) or "sqlite" in db.engine.url.drivername
