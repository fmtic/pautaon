"""S1/E5: script de troca forçada das contas expostas nos dumps.

Tudo aqui usa dados sintéticos (``@example.invalid`` e hashes ``hashA``/``hashB``)
e um repositório git temporário: nada toca os dumps reais nem os bancos do
projeto.
"""

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "forcar_troca_contas_expostas.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("forcar_troca", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    # `@dataclass` consulta `sys.modules[cls.__module__]` ao criar a classe.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


script = _carregar()

COPY_SINTETICO = """--
-- PostgreSQL database dump
--
COPY public."user" (id, name, email, password) FROM stdin;
1\tUm\tvazada@example.invalid\thashA
2\tDois\ttrocada@example.invalid\thashB
3\tTres\tldap@example.invalid\t\\N
\\. 
COPY public.aluno (id, nome) FROM stdin;
9\tAluno qualquer
\\.
""".replace("\\t", "\t").replace("\\. ", "\\.")


def _criar_sqlite(caminho: Path, contas: list[tuple]) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.execute(
        "CREATE TABLE user (id INTEGER PRIMARY KEY, email TEXT, password TEXT, "
        "is_active INTEGER, is_ad_user INTEGER, first_login INTEGER)"
    )
    conexao.executemany(
        "INSERT INTO user (id, email, password, is_active, is_ad_user, first_login) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        contas,
    )
    conexao.commit()
    conexao.close()
    return caminho


@pytest.fixture
def banco(tmp_path):
    return _criar_sqlite(
        tmp_path / "teste.db",
        [
            (1, "vazada@example.invalid", "hashA", 1, 0, 0),
            (2, "trocada@example.invalid", "hashNovo", 1, 0, 0),
            (3, "ldap@example.invalid", None, 1, 1, 0),
            (4, "inativa@example.invalid", "hashA", 0, 0, 0),
            (5, "ja@example.invalid", "hashA", 1, 0, 1),
        ],
    )


@pytest.fixture
def mapa():
    return {
        "vazada@example.invalid": {"hashA"},
        "trocada@example.invalid": {"hashB"},
        "inativa@example.invalid": {"hashA"},
        "ja@example.invalid": {"hashA"},
        "sumiu@example.invalid": {"hashZ"},
    }


def _dsn(caminho: Path) -> str:
    return f"sqlite:///{caminho.as_posix()}"


# ------------------------------------------------------------------- extração


def test_pares_copy_extrai_email_e_hash():
    pares = script.pares_copy(COPY_SINTETICO)

    assert pares == {
        ("vazada@example.invalid", "hashA"),
        ("trocada@example.invalid", "hashB"),
    }


def test_pares_copy_ignora_outras_tabelas():
    pares = script.pares_copy(COPY_SINTETICO)

    assert all(email.endswith(".invalid") for email, _ in pares)
    assert not any("Aluno" in valor for par in pares for valor in par)


def test_pares_sqlite_le_a_tabela_user(tmp_path):
    caminho = _criar_sqlite(
        tmp_path / "d.db", [(1, "a@example.invalid", "hashA", 1, 0, 0)]
    )

    assert script.pares_sqlite(caminho.read_bytes()) == {
        ("a@example.invalid", "hashA")
    }


def test_pares_sqlite_com_arquivo_invalido_devolve_vazio():
    assert script.pares_sqlite(b"isto nao e um banco") == set()


def test_coletar_dos_dumps_le_o_historico(tmp_path):
    repo = tmp_path / "repo"
    (repo / "instance").mkdir(parents=True)
    _criar_sqlite(
        repo / "instance" / "database.db",
        [(1, "a@example.invalid", "hashA", 1, 0, 0)],
    )
    (repo / "backup.sql").write_text(COPY_SINTETICO, encoding="utf-8")

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=teste@example.invalid",
            "-c",
            "user.name=Teste",
            "commit",
            "-m",
            "dumps sinteticos",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    mapa, resumo = script.coletar_dos_dumps(
        ("instance/database.db", "backup.sql"), repo=repo
    )

    assert resumo == {"instance/database.db": 1, "backup.sql": 2}
    assert set(mapa) == {
        "a@example.invalid",
        "vazada@example.invalid",
        "trocada@example.invalid",
    }


def test_coletar_dos_dumps_sem_arquivo_nao_quebra(tmp_path):
    repo = tmp_path / "vazio"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)

    mapa, resumo = script.coletar_dos_dumps(("nao/existe.db",), repo=repo)

    assert mapa == {}
    assert resumo == {"nao/existe.db": 0}


# --------------------------------------------------------------- classificação


def test_classificar_conta_os_casos(banco, mapa):
    contagem = script.classificar(script.consultar(_dsn(banco)), mapa)

    assert contagem.total == 5
    assert contagem.com_senha_local == 4
    assert contagem.so_ldap == 1
    assert contagem.inativas == 1
    assert contagem.ja_marcadas == 1
    # vazada + inativa (a "ja" já está marcada e as outras trocaram a senha)
    assert contagem.mesmo_hash == 3
    assert sorted(contagem.candidatas) == [1, 4]


def test_classificar_sem_mapa_nao_marca_ninguem(banco):
    contagem = script.classificar(script.consultar(_dsn(banco)), {})

    assert contagem.mesmo_hash == 0
    assert contagem.candidatas == []


# ------------------------------------------------------------------ aplicação


def test_aplicar_marca_somente_as_candidatas(banco, mapa):
    linhas = script.consultar(_dsn(banco))
    contagem = script.classificar(linhas, mapa)

    script.aplicar(_dsn(banco), contagem, linhas)

    estados = {
        linha[0]: linha[5] for linha in script.consultar(_dsn(banco))
    }
    assert estados[1] == 1  # vazada
    assert estados[4] == 1  # inativa, mesmo hash
    assert estados[2] == 0  # senha trocada
    assert estados[3] == 0  # sem senha local
    assert estados[5] == 1  # já estava marcada, não muda de novo


def test_gerar_sql_producao_usa_email_e_hash(banco, mapa, tmp_path):
    linhas = script.consultar(_dsn(banco))
    contagem = script.classificar(linhas, mapa)
    destino = tmp_path / "producao.sql"

    gerado = script.gerar_sql_producao(_dsn(banco), contagem, linhas, destino)

    assert gerado == destino
    texto = destino.read_text(encoding="utf-8")
    assert texto.count("UPDATE") == 2
    assert "vazada@example.invalid" in texto
    assert "hashA" in texto
    assert texto.startswith("--")
    assert "COMMIT;" in texto


def test_gerar_sql_producao_sem_candidatas_nao_cria_arquivo(banco, tmp_path):
    linhas = script.consultar(_dsn(banco))
    contagem = script.classificar(linhas, {})

    assert (
        script.gerar_sql_producao(_dsn(banco), contagem, linhas, tmp_path / "x.sql")
        is None
    )


# ----------------------------------------------------------------------- main


def test_main_dry_run_nao_altera_e_nao_imprime_dados(banco, mapa, tmp_path, capsys):
    saida = tmp_path / "sql"

    codigo = script.main(
        ["--url", _dsn(banco), "--saida", str(saida)], mapa=mapa
    )

    assert codigo == 0
    stdout = capsys.readouterr().out
    assert "vazada@example.invalid" not in stdout
    assert "hashA" not in stdout
    assert "contas hoje" in stdout
    assert list(saida.glob("forcar_troca_producao_*.sql"))
    estados = {linha[0]: linha[5] for linha in script.consultar(_dsn(banco))}
    assert estados[1] == 0  # dry-run não altera


def test_main_aplicar_exige_autorizacao_no_banco_principal(
    banco, mapa, tmp_path, capsys
):
    codigo = script.main(
        ["--url", _dsn(banco), "--aplicar", "--saida", str(tmp_path)],
        mapa=mapa,
        backup_dir=tmp_path / "backup",
    )

    assert codigo == 2
    assert "autorizar-principal" in capsys.readouterr().err
    estados = {linha[0]: linha[5] for linha in script.consultar(_dsn(banco))}
    assert estados[1] == 0


def test_main_aplicar_com_autorizacao_marca_e_faz_backup(
    banco, mapa, tmp_path
):
    backups = tmp_path / "backup"

    codigo = script.main(
        [
            "--url",
            _dsn(banco),
            "--aplicar",
            "--autorizar-principal",
            "--saida",
            str(tmp_path / "sql"),
            "--backup-dir",
            str(backups),
        ],
        mapa=mapa,
        backup_dir=backups,
    )

    assert codigo == 0
    estados = {linha[0]: linha[5] for linha in script.consultar(_dsn(banco))}
    assert estados[1] == 1
    assert estados[2] == 0

    arquivos = list(backups.glob("*_pre_forcar_troca_*.sql"))
    assert len(arquivos) == 1
    conteudo = arquivos[0].read_text(encoding="utf-8")
    # O backup guarda o valor anterior (false) para poder voltar atrás.
    assert 'first_login = false WHERE id = 1;' in conteudo
