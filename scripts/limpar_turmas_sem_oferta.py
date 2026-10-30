"""Remoção FÍSICA de turmas de teste que ficaram sem oferta (L5/E1).

Decisão do usuário (30/10/2026): as turmas 12, 13 e 14 do principal e a 34 do
ensaio são dados de teste e saem **fisicamente**, junto com as 2 frequências
legadas da turma 13 (`turma_curso_id IS NULL`).

Regras de segurança (mesmo padrão de `remover_ofertas_sem_lancamento.py`):

  * dry-run por padrão; `--aplicar` escreve;
  * `--aplicar` só é aceito em banco cujo nome contém "ensaio", salvo
    `--autorizar-principal` (autorização expressa do usuário);
  * `--aplicar` faz **backup antes** (`pg_dump` em `instance/backups/` com o
    nome `<banco>_pre_limpeza_turmas.sql`); falha de backup aborta;
  * a lista de turmas é **explícita** (`--ids`), sem padrão;
  * cada turma é recusada (e a execução para) se tiver **qualquer oferta**
    (`turma_curso`, ativa ou não) ou **qualquer vínculo** além de `frequencia`
    com `turma_curso_id IS NULL` — a única linha aceita é a legada listada;
  * contagem por tabela antes e depois, com validação do delta esperado:
    só `frequencia` (−N) e `turma` (−len(ids)) podem mudar; qualquer outra
    diferença aborta antes do commit.

Uso:
    python scripts/limpar_turmas_sem_oferta.py --banco ensaio --ids 34
    python scripts/limpar_turmas_sem_oferta.py --banco ensaio --ids 34 --aplicar
    python scripts/limpar_turmas_sem_oferta.py --banco principal --ids 12,13,14 \\
        --aplicar --autorizar-principal
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

BANCOS = ("principal", "ensaio")

#: Tabelas contadas antes/depois (prova de que nada além do previsto mudou).
TABELAS_CONTADAS = (
    "turma",
    "turma_curso",
    "turma_curso_horario",
    "inscricoes",
    "frequencia",
    "registro_aula",
    "conselho_classe",
    "conselho_resposta",
    "transferencia",
    "dia_bloqueado_turma",
    "tema_aula",
    "log_acao",
)

#: Vínculos por `turma_id` que a turma alvo PODE ter (só frequência legada).
VINCULOS_ACEITOS = {"frequencia"}

#: FKs que apontam para `turma` (descobertas dinamicamente no banco alvo).
FKS_SQL = """
SELECT rel.relname AS tabela,
       att.attname AS coluna,
       con.conname AS fk
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_class ref ON ref.oid = con.confrelid
JOIN unnest(con.conkey) AS k(attnum) ON true
JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = k.attnum
WHERE con.contype = 'f' AND ref.relname = 'turma'
ORDER BY rel.relname, att.attname
"""


def _dsn(banco: str, nome_ensaio: str) -> str:
    valor = os.getenv("DATABASE_URL")
    if not valor:
        texto = (RAIZ / ".env").read_text(encoding="utf-8")
        achado = re.search(r"^DATABASE_URL=(.+)$", texto, re.MULTILINE)
        if not achado:
            raise SystemExit("DATABASE_URL ausente no .env")
        valor = achado.group(1).strip().strip('"').strip("'")
    base, _sep, _nome = valor.rpartition("/")
    if banco != "principal":
        return f"{base}/{nome_ensaio}"
    return valor


def _mascarar(dsn: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@]*@", r"\1***@", dsn)


def _backup(dsn: str, destino: Path) -> None:
    """pg_dump do banco alvo (mesmo padrão dos scripts de saneamento)."""
    m = re.match(
        r"postgresql\+psycopg://([^:]+):([^@]*)@([^:/]+):(\d+)/(.+)$", dsn
    )
    if not m:
        raise SystemExit("DATABASE_URL em formato inesperado para o backup")
    user, pw, host, porta, dbnome = m.groups()
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pg_dump", "-h", host, "-p", porta, "-U", user, "-d", dbnome,
         "-f", str(destino)],
        env=dict(os.environ, PGPASSWORD=pw),
        check=True,
    )
    print(f"backup ok: {destino.name} ({destino.stat().st_size} bytes)")


def _contagens(db) -> dict[str, int]:
    from sqlalchemy import text

    return {
        t: int(db.session.execute(text(f"SELECT count(*) FROM {t}")).scalar())
        for t in TABELAS_CONTADAS
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove turmas sem oferta (dry-run por padrão).",
    )
    parser.add_argument("--banco", default="ensaio", choices=BANCOS)
    parser.add_argument("--nome-ensaio", default="pautaon_ensaio")
    parser.add_argument(
        "--ids", required=True,
        help="IDs de turma separados por vírgula (lista explícita, sem padrão)",
    )
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--autorizar-principal", action="store_true")
    args = parser.parse_args(argv)

    ids = [int(x) for x in args.ids.split(",") if x.strip()]
    banco = args.nome_ensaio if args.banco == "ensaio" else "principal"
    dsn = _dsn(banco, args.nome_ensaio)
    alvo = dsn.rpartition("/")[2]

    if args.aplicar and "ensaio" not in alvo and not args.autorizar_principal:
        print(
            f"RECUSADO: aplicar em '{alvo}' exige --autorizar-principal "
            "(o banco principal só é tocado com autorização expressa).",
            file=sys.stderr,
        )
        return 2

    from config import Config  # import tardio: precisa do sys.path acima

    class AlvoConfig(Config):
        SQLALCHEMY_DATABASE_URI = dsn

    from app import create_app, db  # noqa: E402
    from sqlalchemy import text  # noqa: E402

    app = create_app(AlvoConfig)
    print(f"alvo: {_mascarar(dsn)}")
    print(f"modo: {'APLICAR' if args.aplicar else 'dry-run'}")
    print(f"turmas indicadas: {ids}")

    with app.app_context():
        fks = db.session.execute(text(FKS_SQL)).all()
        antes = _contagens(db)
        print("-- contagem antes --")
        for t, n in antes.items():
            print(f"   {t:22s} = {n}")

        # ---------------- triagem (nada é escrito aqui) ----------------
        plano: list[dict] = []
        problemas: list[str] = []
        for turma_id in ids:
            turma = db.session.execute(
                text("SELECT id, nome, ativo FROM turma WHERE id = :t"),
                {"t": turma_id},
            ).mappings().first()
            if turma is None:
                print(f"turma {turma_id}: não existe (nada a fazer)")
                continue

            ofertas = db.session.execute(
                text("SELECT id FROM turma_curso WHERE turma_id = :t ORDER BY id"),
                {"t": turma_id},
            ).scalars().all()
            vinc = {}
            for fk in fks:
                n = int(
                    db.session.execute(
                        text(
                            f'SELECT count(*) FROM "{fk.tabela}" '
                            f'WHERE "{fk.coluna}" = :t'
                        ),
                        {"t": turma_id},
                    ).scalar()
                )
                if n:
                    vinc[fk.tabela] = vinc.get(fk.tabela, 0) + n

            legadas = int(
                db.session.execute(
                    text(
                        "SELECT count(*) FROM frequencia "
                        "WHERE turma_id = :t AND turma_curso_id IS NULL"
                    ),
                    {"t": turma_id},
                ).scalar()
            )
            com_oferta = int(
                db.session.execute(
                    text(
                        "SELECT count(*) FROM frequencia "
                        "WHERE turma_id = :t AND turma_curso_id IS NOT NULL"
                    ),
                    {"t": turma_id},
                ).scalar()
            )

            inesperados = {
                t: n for t, n in vinc.items()
                if t not in VINCULOS_ACEITOS
            }
            resumo = (
                f"turma {turma_id} ({turma['nome']}, ativa={bool(turma['ativo'])}): "
                f"ofertas={len(ofertas)} vinculos={vinc or 'nenhum'} "
                f"freq_legada={legadas} freq_com_oferta={com_oferta}"
            )
            if ofertas:
                problemas.append(f"{resumo} -> tem oferta (esperado turma SEM oferta)")
                print(f"RECUSADA {resumo}")
                continue
            if inesperados:
                problemas.append(f"{resumo} -> vínculo fora do esperado {inesperados}")
                print(f"RECUSADA {resumo}")
                continue
            if com_oferta:
                problemas.append(f"{resumo} -> frequência com oferta (esperado só legado)")
                print(f"RECUSADA {resumo}")
                continue

            freqs = db.session.execute(
                text(
                    "SELECT id, aluno_id, data, conceito, autor_id "
                    "FROM frequencia WHERE turma_id = :t ORDER BY id"
                ),
                {"t": turma_id},
            ).mappings().all()
            print(f"REMOVÍVEL {resumo}")
            for f in freqs:
                print(
                    f"   frequencia {f['id']}: aluno={f['aluno_id']} "
                    f"data={f['data']} conceito={f['conceito']} "
                    f"autor={f['autor_id']}"
                )
            plano.append(
                {"id": turma_id, "nome": turma["nome"], "freqs": [f["id"] for f in freqs]}
            )

        if problemas:
            print("-- BLOQUEIO --")
            for p in problemas:
                print(f"   {p}")
            print("nada foi alterado (triagem recusou o plano).")
            return 3

        total_freq = sum(len(p["freqs"]) for p in plano)
        if not args.aplicar:
            print(
                f"dry-run: {len(plano)} turma(s) removível(is), "
                f"{total_freq} frequência(s) legada(s) — nada foi alterado."
            )
            return 0
        if not plano:
            print("nada removível: nenhuma escrita feita.")
            return 0

        destino = RAIZ / "instance" / "backups" / f"{alvo}_pre_limpeza_turmas.sql"
        _backup(dsn, destino)

        print("-- removendo --")
        removidas = 0
        for item in plano:
            tid = item["id"]
            # Ordem das FKs: filhas primeiro. As tabelas com vínculo foram
            # recusadas na triagem; as instruções existem para o caso de
            # vínculo aparecer entre a triagem e a escrita (mesma transação).
            n_resp = db.session.execute(
                text(
                    "DELETE FROM conselho_resposta WHERE conselho_id IN ("
                    "SELECT id FROM conselho_classe WHERE turma_id = :t)"
                ),
                {"t": tid},
            ).rowcount
            for tabela, coluna in (
                ("conselho_classe", "turma_id"),
                ("registro_aula", "turma_id"),
                ("frequencia", "turma_id"),
                ("inscricoes", "turma_id"),
                ("transferencia", "turma_origem_id"),
                ("transferencia", "turma_destino_id"),
                ("dia_bloqueado_turma", "turma_id"),
                ("tema_aula", "turma_id"),
            ):
                n = db.session.execute(
                    text(f'DELETE FROM "{tabela}" WHERE "{coluna}" = :t'),
                    {"t": tid},
                ).rowcount
                if n:
                    print(f"   {tabela}.{coluna}: {n} linha(s) da turma {tid}")
            if n_resp:
                print(f"   conselho_resposta: {n_resp} linha(s) da turma {tid}")
            n_tc = db.session.execute(
                text("DELETE FROM turma_curso WHERE turma_id = :t"), {"t": tid}
            ).rowcount
            if n_tc:
                print(f"   turma_curso: {n_tc} oferta(s) da turma {tid}")
            n = db.session.execute(
                text("DELETE FROM turma WHERE id = :t"), {"t": tid}
            ).rowcount
            print(f"   turma {tid} ({item['nome']}): {n} linha removida")
            removidas += n

        # Validação do delta ANTES do commit: só frequencia e turma podem mudar.
        depois_previsto = dict(antes)
        depois_previsto["frequencia"] -= total_freq
        depois_previsto["turma"] -= removidas
        atuais = _contagens(db)
        divergencias = {
            t: (atuais[t], depois_previsto[t])
            for t in TABELAS_CONTADAS
            if atuais[t] != depois_previsto[t]
        }
        if divergencias:
            db.session.rollback()
            print("-- DELTA INESPERADO (rollback) --")
            for t, (agora, previsto) in divergencias.items():
                print(f"   {t}: agora={agora} previsto={previsto}")
            return 4

        db.session.commit()
        print("-- contagem depois --")
        for t in TABELAS_CONTADAS:
            delta = atuais[t] - antes[t]
            print(f"   {t:22s} = {atuais[t]} ({delta:+d})")

        restantes = db.session.execute(
            text("SELECT id FROM turma WHERE id = ANY(:ids)"),
            {"ids": ids},
        ).scalars().all()
        print(f"-- turmas alvo ainda existentes: {restantes or 'nenhuma'}")

        sem_oferta = db.session.execute(
            text(
                "SELECT t.id, t.nome FROM turma t WHERE t.ativo IS TRUE "
                "AND NOT EXISTS (SELECT 1 FROM turma_curso tc "
                "  WHERE tc.turma_id = t.id AND tc.ativo IS TRUE) ORDER BY t.id"
            )
        ).all()
        print("-- turma ativa SEM oferta ativa depois da limpeza --")
        for r in sem_oferta:
            print(f"   turma {r.id} - {r.nome}")
        if not sem_oferta:
            print("   (nenhuma)")

        print(
            f"aplicado: {len(plano)} turma(s) removida(s), "
            f"{total_freq} frequência(s) legada(s); backup em {destino.name}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
