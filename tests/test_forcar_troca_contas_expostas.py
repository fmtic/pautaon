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
from werkzeug.security import check_password_hash, generate_password_hash

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
        "is_active INTEGER, is_ad_user INTEGER, first_login INTEGER, "
        "session_version INTEGER NOT NULL DEFAULT 0)"
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
    # vazada + inativa + ja (a "ja" já está marcada e a "trocada" trocou a senha)
    assert contagem.mesmo_hash == 3
    # E5: só conta ATIVA com senha local entra na lista de trabalho — a inativa
    # (id 4) tem o mesmo hash, mas não é tocada. Antes a lista era [1, 4].
    assert contagem.candidatas == [1]


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
    assert estados[4] == 0  # inativa: intocada desde a regra do E5
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
    assert texto.count("UPDATE") == 1
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


# ------------------------------------------------------------------- reset E5

SENHA_DO_DUMP = "SenhaDoDump!123"
HASH_VAZADO = generate_password_hash(SENHA_DO_DUMP)


@pytest.fixture
def banco_reset(tmp_path):
    return _criar_sqlite(
        tmp_path / "reset.db",
        [
            (1, "vazada@example.invalid", HASH_VAZADO, 1, 0, 0),
            (2, "trocada@example.invalid", generate_password_hash("Outra!123"), 1, 0, 0),
            (3, "ldap@example.invalid", None, 1, 1, 0),
            (4, "inativa@example.invalid", HASH_VAZADO, 0, 0, 0),
            # Já marcada no Prompt B, mas a senha vazada continua autenticando.
            (6, "ja.marcada@example.invalid", HASH_VAZADO, 1, 0, 1),
            # Federada que também tem senha local: o login tenta o hash antes
            # do AD, então NÃO é "só-LDAP" e entra no reset.
            (7, "ad.com.senha@example.invalid", HASH_VAZADO, 1, 1, 0),
        ],
    )


@pytest.fixture
def mapa_reset():
    return {
        "vazada@example.invalid": {HASH_VAZADO},
        "inativa@example.invalid": {HASH_VAZADO},
        "ja.marcada@example.invalid": {HASH_VAZADO},
        "ad.com.senha@example.invalid": {HASH_VAZADO},
    }


def _por_id(url: str) -> dict[int, tuple]:
    return {linha[0]: linha for linha in script.consultar(url)}


def test_reset_inclui_conta_ja_marcada_com_hash_vazado(banco_reset, mapa_reset):
    """O modo reset pega quem já está `first_login=True` mas ainda tem o hash.

    `first_login` só exige a troca **depois** do login: a senha vazada
    continua autenticando. Por isso a lista do reset é maior que a do modo
    histórico, que não remarca quem já estava marcado.
    """
    linhas = script.consultar(_dsn(banco_reset))

    historico = script.classificar(linhas, mapa_reset)
    reset = script.classificar(linhas, mapa_reset, incluir_ja_marcadas=True)

    assert 6 not in historico.candidatas
    assert sorted(reset.candidatas) == [1, 6, 7]


def test_reset_troca_o_hash_e_revoga_a_sessao(banco_reset, mapa_reset):
    url = _dsn(banco_reset)
    linhas = script.consultar(url)
    contagem = script.classificar(linhas, mapa_reset, incluir_ja_marcadas=True)
    assert sorted(contagem.candidatas) == [1, 6, 7]

    assert script.aplicar_reset(url, contagem, linhas) == 3

    linha = _por_id(url)[1]
    assert linha[2] != HASH_VAZADO
    assert not check_password_hash(linha[2], SENHA_DO_DUMP)
    assert linha[5] == 1, "first_login ligado"
    assert linha[6] == 1, "session_version incrementado"


def test_reset_nao_toca_ldap_trocada_nem_inativa(banco_reset, mapa_reset):
    url = _dsn(banco_reset)
    antes = _por_id(url)
    linhas = script.consultar(url)
    script.aplicar_reset(url, script.classificar(linhas, mapa_reset), linhas)
    depois = _por_id(url)

    for user_id in (2, 3, 4):
        assert depois[user_id][2] == antes[user_id][2]
        assert depois[user_id][5] == antes[user_id][5]
        assert depois[user_id][6] == antes[user_id][6]


def test_reset_backup_tem_aviso_e_valores_anteriores(banco_reset, mapa_reset, tmp_path):
    url = _dsn(banco_reset)
    linhas = script.consultar(url)
    contagem = script.classificar(linhas, mapa_reset)
    destino = tmp_path / "backup.sql"

    script._backup_reset(url, contagem, linhas, destino, com_versao=True)

    texto = destino.read_text(encoding="utf-8")
    assert "ATENCAO" in texto and "hashes de senha" in texto
    assert HASH_VAZADO in texto
    assert 'first_login = false WHERE id = 1;' in texto
    assert "session_version anterior = 0" in texto


def test_reset_dry_run_nao_altera_e_gera_duas_variantes(
    banco_reset, mapa_reset, tmp_path, capsys
):
    saida = tmp_path / "sql"

    codigo = script.main(
        ["--url", _dsn(banco_reset), "--modo", "reset", "--saida", str(saida)],
        mapa=mapa_reset,
    )

    assert codigo == 0
    stdout = capsys.readouterr().out
    assert "vazada@example.invalid" not in stdout
    assert HASH_VAZADO not in stdout
    assert _por_id(_dsn(banco_reset))[1][2] == HASH_VAZADO, "dry-run não altera"

    arquivos = sorted(p.name for p in saida.glob("reset_contas_producao_*"))
    assert len(arquivos) == 2
    com = (saida / arquivos[0]).read_text(encoding="utf-8")
    sem = (saida / arquivos[1]).read_text(encoding="utf-8")
    assert arquivos[0].endswith("_com_sessao.sql")
    assert arquivos[1].endswith("_sem_sessao.sql")
    assert "session_version = session_version + 1" in com
    assert "session_version" not in sem


def test_reset_aplicar_exige_autorizacao(banco_reset, mapa_reset, tmp_path, capsys):
    codigo = script.main(
        [
            "--url",
            _dsn(banco_reset),
            "--modo",
            "reset",
            "--aplicar",
            "--saida",
            str(tmp_path / "sql"),
        ],
        mapa=mapa_reset,
        backup_dir=tmp_path / "bak",
    )

    assert codigo == 2
    assert "autorizar-principal" in capsys.readouterr().err
    assert _por_id(_dsn(banco_reset))[1][2] == HASH_VAZADO


def test_reset_aplicar_com_autorizacao_faz_backup_e_conta(
    banco_reset, mapa_reset, tmp_path, capsys
):
    backups = tmp_path / "bak"

    codigo = script.main(
        [
            "--url",
            _dsn(banco_reset),
            "--modo",
            "reset",
            "--aplicar",
            "--autorizar-principal",
            "--saida",
            str(tmp_path / "sql"),
            "--backup-dir",
            str(backups),
        ],
        mapa=mapa_reset,
        backup_dir=backups,
    )

    assert codigo == 0
    stdout = capsys.readouterr().out
    assert "contas resetadas: 3" in stdout
    # Vazada, já marcada e AD-com-senha saem do hash antigo (4 -> 1); a
    # inativa permanece porque a regra do E5 manda não tocar conta inativa.
    assert "hash do dump ainda em uso: 4 -> 1" in stdout
    assert "vazada@example.invalid" not in stdout

    assert len(list(backups.glob("*_pre_reset_contas_*.sql"))) == 1
    linha = _por_id(_dsn(banco_reset))[1]
    assert not check_password_hash(linha[2], SENHA_DO_DUMP)
    assert linha[5] == 1
    assert linha[6] == 1
