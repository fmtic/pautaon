"""Trata as contas cujo hash vazou nos dumps do histórico (S1/E5).

Contexto: os dumps versionados (`instance/database.db`, `instance/database.db.bak`,
`instance/backups/database-antes-initdb-2026-09-29.db` e
`backup_20260923_194945.sql`) carregam e-mails e hashes de senha de usuários
**reais**. Decisão do usuário: redefinir essas contas em vez de reescrever o
histórico.

Dois modos:

  * ``--modo first_login`` (padrão histórico): marca ``first_login=True`` nas
    contas com senha local cujo hash é idêntico ao do dump;
  * ``--modo reset`` (decisão de 30/10/2026): substitui o hash por um hash de
    senha aleatória gerada e descartada (ninguém sabe a senha), marca
    ``first_login=True`` e incrementa ``session_version`` — a conta não entra
    com a senha antiga nem com a nova, e as sessões abertas caem. Não envia
    e-mail e não usa ``ADMIN_DEFAULT_PASSWORD``; o acesso volta só por reset
    administrativo (ou LDAP, quando for o caso).

Regras de segurança (valem nos dois modos):

  * lê os blobs do histórico com `git cat-file` (somente leitura) e nunca
    escreve no Git;
  * **nenhum** e-mail, hash ou CPF é impresso: o relatório traz só CONTAGENS;
  * os bancos `pautaon` e `pautaon_ensaio` são consultados com SELECT;
  * dry-run por padrão; `--aplicar` no banco principal exige
    `--autorizar-principal`;
  * contas só-LDAP (sem senha local) e inativas **nunca** são tocadas;
  * antes de aplicar, grava um backup `.sql` em `instance/backups/` com o
    valor anterior de `password`, `first_login` e `session_version` (falha de
    backup aborta); o arquivo contém hashes e por isso é restrito e avisado;
  * gera em `.tmp/` (fora do Git) o `.sql` com os UPDATEs por e-mail para a
    instância de produção; o relatório informa o caminho, nunca o conteúdo.
    No modo reset saem duas variantes: ``_com_sessao`` (produção já com a
    coluna ``session_version``) e ``_sem_sessao`` (produção anterior à
    migration `b5c6d7e8f9a0`).

Uso:
    python scripts/forcar_troca_contas_expostas.py
    python scripts/forcar_troca_contas_expostas.py --modo reset --banco ensaio \
        --aplicar
    python scripts/forcar_troca_contas_expostas.py --modo reset --banco principal \
        --aplicar --autorizar-principal
    python scripts/forcar_troca_contas_expostas.py --url sqlite:///teste.db
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from werkzeug.security import generate_password_hash

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

#: Dumps versionados conhecidos por carregar hashes de usuários reais.
DUMPS = (
    "instance/database.db",
    "instance/database.db.bak",
    "instance/backups/database-antes-initdb-2026-09-29.db",
    "backup_20260923_194945.sql",
)

#: Banco principal e o nome do espelho de ensaio.
BANCO_PRINCIPAL = "pautaon"
BANCO_ENSAIO = "pautaon_ensaio"

DIR_BACKUP = RAIZ / "instance" / "backups"
DIR_SAIDA = RAIZ / ".tmp"


# --------------------------------------------------------------------------- git


def _git(*args: str, repo: Path = RAIZ) -> bytes:
    """Executa git no repositório indicado (somente leitura)."""
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, check=True
    ).stdout


def commits_que_tocaram(caminho: str, repo: Path = RAIZ) -> list[str]:
    return _git("rev-list", "--all", "--", caminho, repo=repo).decode().split()


def blob_do_commit(commit: str, caminho: str, repo: Path = RAIZ) -> bytes | None:
    """Bytes do arquivo naquele commit, ou ``None`` se ele não existir lá."""
    existe = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{caminho}"],
        cwd=repo,
        capture_output=True,
    )
    if existe.returncode != 0:
        return None
    return _git("cat-file", "blob", f"{commit}:{caminho}", repo=repo)


# --------------------------------------------------------------------- extração


def _desescapar_copy(valor: str) -> str:
    """Desfaz os escapes do formato COPY (texto) do PostgreSQL."""
    if valor == "\\N":
        return ""
    return (
        valor.replace("\\\\", "\\")
        .replace("\\t", "\t")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
    )


def pares_copy(texto: str) -> set[tuple[str, str]]:
    """Pares (e-mail, hash) dos blocos ``COPY ... FROM stdin`` da tabela user."""
    pares: set[tuple[str, str]] = set()
    linhas = texto.splitlines()
    i = 0
    while i < len(linhas):
        cabecalho = re.match(
            r"^COPY\s+(?P<tabela>.+?)\s*\((?P<colunas>.*?)\)\s+FROM\s+stdin;",
            linhas[i],
            re.IGNORECASE,
        )
        if not cabecalho:
            i += 1
            continue

        tabela = cabecalho.group("tabela").strip().split(".")[-1].strip('"')
        colunas = [c.strip().strip('"') for c in cabecalho.group("colunas").split(",")]
        i += 1

        usar = tabela == "user" and "email" in colunas and "password" in colunas
        indice_email = colunas.index("email") if "email" in colunas else -1
        indice_senha = colunas.index("password") if "password" in colunas else -1

        while i < len(linhas) and linhas[i] != "\\.":
            if usar:
                campos = linhas[i].split("\t")
                if len(campos) > max(indice_email, indice_senha):
                    email = _desescapar_copy(campos[indice_email]).strip().lower()
                    senha = _desescapar_copy(campos[indice_senha]).strip()
                    if email and senha:
                        pares.add((email, senha))
            i += 1
        i += 1
    return pares


def pares_sqlite(dados: bytes) -> set[tuple[str, str]]:
    """Pares (e-mail, hash) da tabela ``user`` de um dump SQLite."""
    pares: set[tuple[str, str]] = set()
    with tempfile.TemporaryDirectory() as tmp:
        caminho = Path(tmp) / "dump.db"
        caminho.write_bytes(dados)
        conexao = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
        try:
            cursor = conexao.execute(
                "SELECT email, password FROM user "
                "WHERE email IS NOT NULL AND password IS NOT NULL AND password <> ''"
            )
            for email, senha in cursor:
                if email and senha:
                    pares.add((str(email).strip().lower(), str(senha).strip()))
        except sqlite3.DatabaseError:
            return set()
        finally:
            conexao.close()
    return pares


def pares_do_blob(caminho: str, dados: bytes) -> set[tuple[str, str]]:
    if caminho.lower().endswith(".sql"):
        return pares_copy(dados.decode("utf-8", "replace"))
    return pares_sqlite(dados)


def coletar_dos_dumps(
    caminhos: tuple[str, ...] = DUMPS, repo: Path = RAIZ
) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Mapa e-mail -> hashes vistos no histórico e a contagem por dump."""
    mapa: dict[str, set[str]] = {}
    resumo: dict[str, int] = {}
    for caminho in caminhos:
        pares: set[tuple[str, str]] = set()
        for commit in commits_que_tocaram(caminho, repo):
            dados = blob_do_commit(commit, caminho, repo)
            if dados:
                pares |= pares_do_blob(caminho, dados)
        resumo[caminho] = len(pares)
        for email, senha in pares:
            mapa.setdefault(email, set()).add(senha)
    return mapa, resumo


# ----------------------------------------------------------------- classificação


@dataclass
class Contagem:
    """Números de um banco — nada aqui identifica pessoa alguma."""

    total: int = 0
    com_senha_local: int = 0
    so_ldap: int = 0
    inativas: int = 0
    mesmo_hash: int = 0
    ja_marcadas: int = 0
    candidatas: list[int] = field(default_factory=list)
    hashes_por_id: dict[int, str] = field(default_factory=dict)


def classificar(
    linhas: list[tuple],
    mapa: dict[str, set[str]],
    *,
    incluir_ja_marcadas: bool = False,
) -> Contagem:
    """Compara as linhas de ``user`` com os pares vazados do histórico.

    ``linhas`` são tuplas ``(id, email, password, is_active, is_ad_user,
    first_login[, session_version])``. Candidata = conta ativa, com senha
    local e hash atual entre os vazados para aquele e-mail (a senha nunca foi
    trocada).

    ``incluir_ja_marcadas`` é o critério do modo ``reset``: conta que já está
    com ``first_login=True`` mas ainda guarda o hash vazado continua entrando,
    porque a senha vazada *autentica* — ``first_login`` só pede a troca
    depois do login. O modo ``first_login`` mantém o filtro antigo (não
    remarca quem já estava marcado).
    """
    contagem = Contagem()
    for linha in linhas:
        user_id, email, senha, ativo, is_ad, first_login = linha[:6]
        contagem.total += 1
        if not ativo:
            contagem.inativas += 1

        senha = (senha or "").strip()
        if not senha:
            if is_ad:
                contagem.so_ldap += 1
            continue

        contagem.com_senha_local += 1
        if first_login:
            contagem.ja_marcadas += 1

        hashes = mapa.get((email or "").strip().lower())
        if hashes and senha in hashes:
            contagem.mesmo_hash += 1
            # Só conta ATIVA entra na lista de trabalho. "Só-LDAP" (sem senha
            # local) já saiu no `continue` acima; `is_ad_user` com senha local
            # NÃO é só-LDAP — o login tenta o hash local antes do AD, então a
            # senha vazada autentica e precisa ser redefinida. Inativa nunca é
            # tocada (regra do E5).
            if ativo and (incluir_ja_marcadas or not first_login):
                contagem.candidatas.append(int(user_id))
                contagem.hashes_por_id[int(user_id)] = senha
    return contagem


# ---------------------------------------------------------------------- bancos


def resolver_url(banco: str) -> str:
    """DSN do banco pedido, derivado do ``DATABASE_URL`` (sem alterar o .env)."""
    valor = os.getenv("DATABASE_URL")
    if not valor:
        texto = (RAIZ / ".env").read_text(encoding="utf-8")
        achado = re.search(r"^DATABASE_URL=(.+)$", texto, re.MULTILINE)
        if not achado:
            raise SystemExit("DATABASE_URL ausente no .env")
        valor = achado.group(1).strip().strip('"').strip("'")
    base, _sep, nome = valor.rpartition("/")
    if banco == BANCO_ENSAIO:
        return f"{base}/{BANCO_ENSAIO}"
    return f"{base}/{nome or BANCO_PRINCIPAL}"


def nome_do_banco(url: str) -> str:
    return url.rpartition("/")[2] or "?"


def consultar(url: str, com_versao: bool | None = None) -> list[tuple]:
    """SELECT das contas (nunca escreve).

    A coluna ``session_version`` é incluída quando existir (ou quando
    ``com_versao`` for forçado); sem ela a tupla tem 6 posições, como antes.
    """
    from sqlalchemy import create_engine, text

    if com_versao is None:
        com_versao = coluna_existe(url)
    colunas = 'id, email, password, is_active, is_ad_user, first_login'
    if com_versao:
        colunas += ', session_version'

    engine = create_engine(url)
    try:
        with engine.connect() as conexao:
            return list(
                conexao.execute(text(f'SELECT {colunas} FROM "user"')).all()
            )
    finally:
        engine.dispose()


def coluna_existe(url: str, tabela: str = "user", coluna: str = "session_version") -> bool:
    """``True`` quando a coluna existe no banco alvo (produção pode não ter)."""
    from sqlalchemy import create_engine, inspect

    engine = create_engine(url)
    try:
        return coluna in {
            info["name"] for info in inspect(engine).get_columns(tabela)
        }
    except Exception:
        return False
    finally:
        engine.dispose()


def _backup_restauracao(url: str, linhas: list[tuple], destino: Path) -> None:
    """Grava o valor anterior de ``first_login`` para poder voltar atrás."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    partes = [
        f"-- Backup antes de forçar troca de senha ({nome_do_banco(url)})",
        f"-- gerado em {datetime.now().isoformat(timespec='seconds')}",
        "-- Restauração: valores anteriores de first_login por id.",
        "",
    ]
    for user_id, _email, _senha, _ativo, _is_ad, first_login in (
        linha[:6] for linha in linhas
    ):
        valor = "true" if first_login else "false"
        partes.append(f'UPDATE "user" SET first_login = {valor} WHERE id = {int(user_id)};')
    destino.write_text("\n".join(partes) + "\n", encoding="utf-8")


def aplicar(url: str, contagem: Contagem, linhas: list[tuple]) -> Contagem:
    """Define ``first_login=True`` apenas nas candidatas (hash do dump)."""
    from sqlalchemy import bindparam, create_engine, text

    if not contagem.candidatas:
        return contagem

    engine = create_engine(url)
    try:
        with engine.begin() as conexao:
            instrucao = text(
                'UPDATE "user" SET first_login = true '
                "WHERE id = :id AND password = :senha AND first_login = false"
            ).bindparams(bindparam("id"), bindparam("senha"))
            for user_id in contagem.candidatas:
                conexao.execute(
                    instrucao,
                    {"id": user_id, "senha": contagem.hashes_por_id[user_id]},
                )
    finally:
        engine.dispose()

    depois = classificar(consultar(url), {})
    contagem.ja_marcadas = depois.ja_marcadas
    return contagem


# ------------------------------------------------------------------------ reset


def _hash_inutilizavel() -> str:
    """Hash de uma senha aleatória gerada e descartada.

    Só o hash sai daqui: a senha em claro nunca é impressa, gravada nem
    devolvida, então ninguém — nem quem roda o script — consegue entrar com
    ela. É um hash de formato válido de propósito: um hash corrompido faria
    `check_password_hash` estourar no login em vez de responder `False`.
    """
    return generate_password_hash(secrets.token_urlsafe(48))


def aplicar_reset(
    url: str, contagem: Contagem, linhas: list[tuple], *, com_versao: bool | None = None
) -> int:
    """Substitui o hash das candidatas numa única transação.

    Cada linha vira ``password = <hash inutilizável>``, ``first_login = true``
    e — quando a coluna existe — ``session_version = session_version + 1``.
    O ``WHERE`` repete o hash vazado: conta que trocou a senha no meio do
    caminho não é sobrescrita. Devolve quantas linhas mudaram.
    """
    from sqlalchemy import bindparam, create_engine, text

    if not contagem.candidatas:
        return 0
    if com_versao is None:
        com_versao = coluna_existe(url)

    extras = ", session_version = session_version + 1" if com_versao else ""
    instrucao = text(
        'UPDATE "user" SET password = :novo, first_login = true'
        + extras
        + " WHERE id = :id AND password = :senha"
    ).bindparams(bindparam("novo"), bindparam("id"), bindparam("senha"))

    total = 0
    engine = create_engine(url)
    try:
        with engine.begin() as conexao:
            for user_id in contagem.candidatas:
                resultado = conexao.execute(
                    instrucao,
                    {
                        "novo": _hash_inutilizavel(),
                        "id": user_id,
                        "senha": contagem.hashes_por_id[user_id],
                    },
                )
                total += max(resultado.rowcount or 0, 0)
    finally:
        engine.dispose()
    return total


def _backup_reset(
    url: str,
    contagem: Contagem,
    linhas: list[tuple],
    destino: Path,
    *,
    com_versao: bool,
) -> None:
    """Backup `.sql` do estado anterior das contas que serão redefinidas.

    Contém hashes de senha — por isso o aviso no topo e a permissão restrita.
    O `session_version` anterior fica registrado, mas **não** é revertido:
    voltar o contador ressuscitaria as sessões revogadas.
    """
    por_id = {int(linha[0]): linha for linha in linhas}
    destino.parent.mkdir(parents=True, exist_ok=True)
    partes = [
        f"-- Backup antes do RESET das contas expostas ({nome_do_banco(url)})",
        f"-- gerado em {datetime.now().isoformat(timespec='seconds')}",
        "-- ATENCAO: este arquivo contem hashes de senha. Nao versionar, nao",
        "-- compartilhar e apagar depois de conferir a restauracao.",
        "-- Restaura password e first_login por id; o session_version anterior",
        "-- fica em comentario e NAO e revertido de proposito.",
        "",
    ]
    for user_id in contagem.candidatas:
        linha = por_id[user_id]
        senha = (linha[2] or "").replace("'", "''")
        first = "true" if linha[5] else "false"
        anterior = linha[6] if com_versao and len(linha) > 6 else "?"
        partes.append(f"-- id {user_id}: session_version anterior = {anterior}")
        partes.append(
            f'UPDATE "user" SET password = \'{senha}\', first_login = {first} '
            f"WHERE id = {int(user_id)};"
        )
    destino.write_text("\n".join(partes) + "\n", encoding="utf-8")
    try:
        os.chmod(destino, 0o600)
    except OSError:
        pass


def gerar_sql_reset(
    url: str,
    contagem: Contagem,
    linhas: list[tuple],
    destino: Path,
    *,
    com_versao: bool,
) -> Path | None:
    """`.sql` de reset para a produção, em duas variantes de schema.

    ``com_versao`` inclui ``session_version = session_version + 1`` (produção
    já migrada); sem ele o arquivo serve a instância que ainda não tem a
    coluna. Contém e-mail e hash antigo no ``WHERE`` — é material sensível:
    aplicar e apagar.
    """
    if not contagem.candidatas:
        return None
    por_id = {int(linha[0]): linha for linha in linhas}
    destino.parent.mkdir(parents=True, exist_ok=True)
    extras = ", session_version = session_version + 1" if com_versao else ""
    partes = [
        f"-- RESET das contas expostas ({nome_do_banco(url)})",
        f"-- gerado em {datetime.now().isoformat(timespec='seconds')}",
        "-- Contem e-mails e hashes (necessarios ao WHERE): aplicar e apagar.",
        "-- O hash novo e de uma senha aleatoria descartada: a conta so volta",
        "-- por reset administrativo (ou LDAP, quando for o caso).",
        "BEGIN;",
    ]
    for user_id in contagem.candidatas:
        linha = por_id[user_id]
        email = str(linha[1] or "").replace("'", "''")
        senha = contagem.hashes_por_id[user_id].replace("'", "''")
        partes.append(
            f'UPDATE "user" SET password = \'{_hash_inutilizavel()}\', '
            f"first_login = true{extras} "
            f"WHERE email = '{email}' AND password = '{senha}';"
        )
    partes.append("COMMIT;")
    destino.write_text("\n".join(partes) + "\n", encoding="utf-8")
    return destino


def gerar_sql_producao(
    url: str, contagem: Contagem, linhas: list[tuple], destino: Path
) -> Path | None:
    """Arquivo .sql com os UPDATEs por e-mail para a instância de produção.

    O agente não acessa produção: este arquivo é a entrega. Contém e-mail e
    hash (necessários ao WHERE) e fica em ``.tmp/``, fora do Git.
    """
    if not contagem.candidatas:
        return None
    por_id = {int(linha[0]): linha for linha in linhas}
    destino.parent.mkdir(parents=True, exist_ok=True)
    partes = [
        f"-- Forcar troca de senha ({nome_do_banco(url)})",
        f"-- gerado em {datetime.now().isoformat(timespec='seconds')}",
        "-- Aplicar na instancia de producao. O hash no WHERE garante que a",
        "-- conta so e marcada se a senha ainda for a que vazou no dump.",
        "BEGIN;",
    ]
    for user_id in contagem.candidatas:
        linha = por_id[user_id]
        email = str(linha[1] or "").replace("'", "''")
        senha = contagem.hashes_por_id[user_id].replace("'", "''")
        partes.append(
            f"UPDATE \"user\" SET first_login = true "
            f"WHERE email = '{email}' AND password = '{senha}';"
        )
    partes.append("COMMIT;")
    destino.write_text("\n".join(partes) + "\n", encoding="utf-8")
    return destino


# ------------------------------------------------------------------------ main


def _imprimir_contagem(nome: str, contagem: Contagem) -> None:
    print(f"== {nome} ==")
    print(f"  contas hoje:................ {contagem.total}")
    print(f"  com senha local:............ {contagem.com_senha_local}")
    print(f"  so LDAP (sem senha local):.. {contagem.so_ldap}")
    print(f"  inativas:................... {contagem.inativas}")
    print(f"  ja com first_login=True:.... {contagem.ja_marcadas}")
    print(f"  MESMO hash do dump:......... {contagem.mesmo_hash}")
    print(f"  a marcar agora:............. {len(contagem.candidatas)}")


def main(
    argv: list[str] | None = None,
    mapa: dict[str, set[str]] | None = None,
    backup_dir: Path | None = None,
) -> int:
    """Entrada do script.

    ``mapa`` e ``backup_dir`` existem para os testes (blobs sintéticos e destino
    temporário do backup); na linha de comando vêm do histórico do repositório
    e de ``instance/backups/``.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Forca a troca de senha das contas cujo hash vazou nos dumps "
            "(dry-run por padrao)."
        ),
    )
    parser.add_argument(
        "--banco",
        default="todos",
        choices=("todos", "principal", "ensaio"),
        help="banco alvo (padrao: os dois)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="DSN explicito (uso em ensaio/teste); processa apenas esse banco",
    )
    parser.add_argument(
        "--modo",
        choices=("first_login", "reset"),
        default="first_login",
        help=(
            "first_login (padrao historico) ou reset (hash aleatorio "
            "inutilizavel + first_login + revoga sessoes)"
        ),
    )
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--autorizar-principal", action="store_true")
    parser.add_argument(
        "--saida",
        default=None,
        help="diretorio do .sql de producao (padrao: .tmp/)",
    )
    parser.add_argument(
        "--backup-dir",
        default=None,
        help="diretorio do backup .sql (padrao: instance/backups/)",
    )
    args = parser.parse_args(argv)

    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    if mapa is None:
        mapa, resumo = coletar_dos_dumps()
        print("== dumps do historico (git cat-file, somente leitura) ==")
        for caminho, quantidade in resumo.items():
            print(f"  {caminho}: {quantidade} pares e-mail/hash")
        print(f"  total de e-mails distintos: {len(mapa)}")
        print()

    destino_backup = Path(args.backup_dir) if args.backup_dir else (
        backup_dir or DIR_BACKUP
    )

    if args.url:
        alvos = [args.url]
    elif args.banco == "principal":
        alvos = [resolver_url(BANCO_PRINCIPAL)]
    elif args.banco == "ensaio":
        alvos = [resolver_url(BANCO_ENSAIO)]
    else:
        alvos = [resolver_url(BANCO_PRINCIPAL), resolver_url(BANCO_ENSAIO)]

    saida = Path(args.saida) if args.saida else DIR_SAIDA
    codigo = 0
    for url in alvos:
        nome = nome_do_banco(url)
        linhas = consultar(url)
        contagem = classificar(
            linhas, mapa, incluir_ja_marcadas=(args.modo == "reset")
        )
        _imprimir_contagem(nome, contagem)

        if args.modo == "reset":
            base_sql = saida / f"reset_contas_producao_{nome}_{carimbo}"
            com = gerar_sql_reset(
                url, contagem, linhas, Path(f"{base_sql}_com_sessao.sql"),
                com_versao=True,
            )
            sem = gerar_sql_reset(
                url, contagem, linhas, Path(f"{base_sql}_sem_sessao.sql"),
                com_versao=False,
            )
            if com and sem:
                print(f"  arquivos para producao: {com.name} (com_sessao)")
                print(f"                     e: {sem.name} (sem_sessao)")
            else:
                print("  arquivos para producao: nao gerados (sem candidatas)")
        else:
            destino_sql = saida / f"forcar_troca_producao_{nome}_{carimbo}.sql"
            caminho_gerado = gerar_sql_producao(url, contagem, linhas, destino_sql)
            if caminho_gerado:
                print(f"  arquivo para producao: {caminho_gerado}")
            else:
                print("  arquivo para producao: nao gerado (sem candidatas)")
        print()

        if not args.aplicar:
            continue
        if nome != BANCO_ENSAIO and not args.autorizar_principal:
            print(
                f"RECUSADO: aplicar em '{nome}' exige --autorizar-principal.",
                file=sys.stderr,
            )
            codigo = 2
            continue

        if args.modo == "reset":
            com_versao = coluna_existe(url)
            backup = destino_backup / f"{nome}_pre_reset_contas_{carimbo}.sql"
            _backup_reset(url, contagem, linhas, backup, com_versao=com_versao)
            print(f"  backup ok: {backup.name} (contem hashes; apagar depois)")

            antes = contagem.mesmo_hash
            aplicadas = aplicar_reset(
                url, contagem, linhas, com_versao=com_versao
            )
            depois = classificar(
                consultar(url, com_versao),
                mapa,
                incluir_ja_marcadas=True,
            )
            print(f"  contas resetadas: {aplicadas}")
            print(f"  hash do dump ainda em uso: {antes} -> {depois.mesmo_hash}")
            print(f"  first_login=True agora: {depois.ja_marcadas}")
            print(f"  ainda a tratar: {len(depois.candidatas)}")
            print()
            continue

        backup = destino_backup / f"{nome}_pre_forcar_troca_{carimbo}.sql"
        _backup_restauracao(url, linhas, backup)
        print(f"  backup ok: {backup.name}")

        antes = contagem.ja_marcadas
        contagem = aplicar(url, contagem, linhas)
        print(f"  first_login=True: {antes} -> {contagem.ja_marcadas}")
        print(f"  contas marcadas: {contagem.ja_marcadas - antes}")
        print()

    if args.aplicar:
        print("Observacao: a instancia de producao nao foi tocada; aplique o .sql.")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
