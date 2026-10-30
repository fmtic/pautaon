"""Força a troca de senha das contas cujo hash vazou nos dumps do histórico (S1/E5).

Contexto: os dumps versionados (`instance/database.db`, `instance/database.db.bak`,
`instance/backups/database-antes-initdb-2026-09-29.db` e
`backup_20260923_194945.sql`) carregam e-mails e hashes de senha de usuários
**reais**. Decisão do usuário: forçar a redefinição dessas contas em vez de
reescrever o histórico.

Regras de segurança:

  * lê os blobs do histórico com `git cat-file` (somente leitura) e nunca
    escreve no Git;
  * **nenhum** e-mail, hash ou CPF é impresso: o relatório traz só CONTAGENS;
  * os bancos `pautaon` e `pautaon_ensaio` são consultados com SELECT;
  * dry-run por padrão; `--aplicar` grava `first_login=True` apenas nas contas
    com senha local cujo hash é **idêntico** ao do dump (ou seja, senha nunca
    trocada) e não altera mais nada;
  * `--aplicar` no banco principal exige `--autorizar-principal`;
  * antes de aplicar, grava um backup `.sql` com o valor anterior de
    `first_login` em `instance/backups/` (falha de backup aborta);
  * gera em `.tmp/` (fora do Git) um `.sql` com os UPDATEs por e-mail para a
    instância de produção, que o agente não acessa; o relatório informa o
    caminho, nunca o conteúdo.

Uso:
    python scripts/forcar_troca_contas_expostas.py
    python scripts/forcar_troca_contas_expostas.py --banco ensaio --aplicar
    python scripts/forcar_troca_contas_expostas.py --banco principal --aplicar \\
        --autorizar-principal
    python scripts/forcar_troca_contas_expostas.py --url sqlite:///teste.db
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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


def classificar(linhas: list[tuple], mapa: dict[str, set[str]]) -> Contagem:
    """Compara as linhas de ``user`` com os pares vazados do histórico.

    ``linhas`` são tuplas ``(id, email, password, is_active, is_ad_user,
    first_login)``. Candidata = tem senha local E o hash atual está entre os
    hashes vazados para aquele e-mail (a senha nunca foi trocada).
    """
    contagem = Contagem()
    for user_id, email, senha, ativo, is_ad, first_login in linhas:
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
            if not first_login:
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


def consultar(url: str) -> list[tuple]:
    """SELECT das contas (nunca escreve)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    try:
        with engine.connect() as conexao:
            return list(
                conexao.execute(
                    text(
                        'SELECT id, email, password, is_active, is_ad_user, '
                        'first_login FROM "user"'
                    )
                ).all()
            )
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
    for user_id, _email, _senha, _ativo, _is_ad, first_login in linhas:
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
        contagem = classificar(linhas, mapa)
        _imprimir_contagem(nome, contagem)

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
