"""Remoção de ofertas criadas em teste que ficaram sem professor (E1).

Secador por oferta, na ordem das FKs. Regra de segurança (a mesma do
`saneamento_professor_oferta.py`):

  * dry-run por padrão; `--aplicar` escreve;
  * `--aplicar` só é aceito em banco cujo nome contém "ensaio", salvo
    `--autorizar-principal` (autorização expressa do usuário);
  * oferta com lançamento (`frequencia`, `registro_aula`, `conselho_classe` +
    `conselho_resposta` ligada) **não é removida**: o script reporta o bloqueio
    e segue para as outras — salvo com `--remover-lancamentos`, decisão
    explícita de remover também os lançamentos vinculados à oferta (nunca as
    linhas legadas com `turma_curso_id IS NULL`);
  * oferta com inscrição ativa só é removida com `--remover-inscricoes`
    (perda de matrícula precisa ser decisão explícita);
  * backup antes: `pg_dump` em `instance/backups/` (ver cabeçalho do relato).

Uso:
    python scripts/remover_ofertas_sem_lancamento.py --banco ensaio --ids 50
    python scripts/remover_ofertas_sem_lancamento.py --banco ensaio --ids 50 \\
        --aplicar --remover-inscricoes
    python scripts/remover_ofertas_sem_lancamento.py --banco principal --ids 19 \\
        --aplicar --autorizar-principal
    python scripts/remover_ofertas_sem_lancamento.py --banco principal --ids 16,17,18 \\
        --aplicar --autorizar-principal --remover-lancamentos --remover-inscricoes
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

BANCOS = ("principal", "ensaio")
# Tabelas que configuram "lançamento" e travam a remoção (regra da tarefa).
LANCAMENTOS = ("frequencia", "registro_aula", "conselho_classe")
# Ordem de remoção das dependências de `turma_curso` (RESTRICT/NO ACTION primeiro).
DEPENDENCIAS = LANCAMENTOS + ("inscricoes", "turma_curso_horario")
TABELAS_CONTADAS = DEPENDENCIAS + ("conselho_resposta", "turma_curso", "turma")


def _dsn(banco: str, nome_ensaio: str) -> str:
    """DSN do `.env` com o nome do banco trocado (credenciais preservadas)."""
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


def _contagens(db) -> dict[str, int]:
    from sqlalchemy import text

    return {
        t: int(db.session.execute(text(f"SELECT count(*) FROM {t}")).scalar())
        for t in TABELAS_CONTADAS
    }


def _vinculos(db, oferta_id: int) -> dict[str, int]:
    from sqlalchemy import text

    return {
        t: int(
            db.session.execute(
                text(f"SELECT count(*) FROM {t} WHERE turma_curso_id = :o"),
                {"o": oferta_id},
            ).scalar()
        )
        for t in DEPENDENCIAS
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Remove oferta sem lançamento (dry-run por padrão).",
    )
    parser.add_argument("--banco", default="ensaio", choices=BANCOS)
    parser.add_argument("--nome-ensaio", default="pautaon_ensaio")
    parser.add_argument(
        "--ids", required=True,
        help="IDs de oferta separados por vírgula (lista explícita, sem padrão)",
    )
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--autorizar-principal", action="store_true")
    parser.add_argument(
        "--remover-inscricoes", action="store_true",
        help="permite desfazer inscrições ativas ligadas à oferta",
    )
    parser.add_argument(
        "--remover-lancamentos", action="store_true",
        help="remove também os lançamentos vinculados à oferta (frequencia, "
             "registro_aula, conselho_classe + conselho_resposta); só toca "
             "linhas com turma_curso_id na lista — nunca as legadas NULL",
    )
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
    from app.models import Inscricao, Turma, TurmaCurso  # noqa: E402
    from sqlalchemy import text  # noqa: E402

    app = create_app(AlvoConfig)
    print(f"alvo: {_mascarar(dsn)}")
    print(f"modo: {'APLICAR' if args.aplicar else 'dry-run'}")
    print(f"ofertas indicadas: {ids}")

    with app.app_context():
        antes = _contagens(db)
        print("-- contagem antes --")
        for t, n in antes.items():
            print(f"   {t:22s} = {n}")

        removiveis, bloqueadas = [], []
        for oferta_id in ids:
            oferta = db.session.get(TurmaCurso, oferta_id)
            if oferta is None:
                print(f"oferta {oferta_id}: não existe (nada a fazer)")
                continue
            vinc = _vinculos(db, oferta_id)
            turma = db.session.get(Turma, oferta.turma_id)
            ativos = int(
                db.session.execute(
                    text(
                        "SELECT count(*) FROM inscricoes "
                        "WHERE turma_curso_id = :o AND ativo IS TRUE"
                    ),
                    {"o": oferta_id},
                ).scalar()
            )
            lanc = {t: vinc[t] for t in LANCAMENTOS if vinc[t]}
            sumario = (
                f"oferta {oferta.id} (turma {turma.id} - {turma.nome}, "
                f"curso {oferta.curso_id}, ativa={bool(oferta.ativo)}, "
                f"professor={oferta.professor_id}): {vinc}, ativas={ativos}"
            )
            if lanc and not args.remover_lancamentos:
                print(f"BLOQUEADA {sumario} -> tem lançamento, NÃO é removida "
                      "(use --remover-lancamentos para remover junto)")
                bloqueadas.append(oferta.id)
            elif lanc:
                print(f"REMOVÍVEL COM LANÇAMENTOS {sumario}")
                removiveis.append(oferta)
            elif ativos and not args.remover_inscricoes:
                print(
                    f"BLOQUEADA {sumario} -> tem inscrição ativa; "
                    "use --remover-inscricoes para remover"
                )
                bloqueadas.append(oferta.id)
            else:
                print(f"REMOVÍVEL {sumario}")
                removiveis.append(oferta)

        if not args.aplicar:
            print(
                f"dry-run: {len(removiveis)} removível(is), "
                f"{len(bloqueadas)} bloqueada(s) — nada foi alterado."
            )
            return 0
        if not removiveis:
            print("nada removível: nenhuma escrita feita.")
            return 0

        print("-- removendo --")
        for oferta in removiveis:
            # Lançamentos vinculados SOMENTE a esta oferta, na ordem das FKs:
            # conselho_resposta (filha) -> conselho_classe -> registro_aula
            # (registro_aula_tema cai em CASCADE) -> frequencia.
            if args.remover_lancamentos:
                n_res = db.session.execute(
                    text(
                        "DELETE FROM conselho_resposta WHERE conselho_id IN ("
                        "SELECT id FROM conselho_classe WHERE turma_curso_id = :o)"
                    ),
                    {"o": oferta.id},
                ).rowcount
                for t in LANCAMENTOS:
                    n = db.session.execute(
                        text(f"DELETE FROM {t} WHERE turma_curso_id = :o"),
                        {"o": oferta.id},
                    ).rowcount
                    print(f"   {t}: {n} linha(s) removida(s) da oferta {oferta.id}")
                if n_res:
                    print(f"   conselho_resposta: {n_res} linha(s) removida(s) (via conselho_classe)")
            # Incrições ativas/inativas da oferta (FK NO ACTION): saem primeiro.
            for inscricao in Inscricao.query.filter_by(
                turma_curso_id=oferta.id
            ).all():
                print(f"   inscricao {inscricao.id} (aluno {inscricao.aluno_id})")
                db.session.delete(inscricao)
            db.session.execute(
                text("DELETE FROM turma_curso_horario WHERE turma_curso_id = :o"),
                {"o": oferta.id},
            )
            turma_id = oferta.turma_id
            db.session.delete(oferta)
            db.session.flush()
            print(f"   oferta {oferta.id} removida (turma {turma_id})")
        db.session.commit()

        depois = _contagens(db)
        print("-- contagem depois --")
        for t in TABELAS_CONTADAS:
            delta = depois[t] - antes[t]
            print(f"   {t:22s} = {depois[t]} ({delta:+d})")

        restantes = db.session.execute(
            text(
                "SELECT tc.id, tc.turma_id, t.nome FROM turma_curso tc "
                "JOIN turma t ON t.id = tc.turma_id "
                "WHERE tc.ativo IS TRUE AND tc.professor_id IS NULL "
                "ORDER BY tc.id"
            )
        ).all()
        print("-- oferta ativa SEM professor depois do saneamento --")
        for r in restantes:
            print(f"   oferta {r.id} (turma {r.turma_id} - {r.nome})")
        if not restantes:
            print("   (nenhuma)")

        turmas_sem_oferta = db.session.execute(
            text(
                "SELECT t.id, t.nome FROM turma t "
                "WHERE t.ativo IS TRUE AND NOT EXISTS ("
                "  SELECT 1 FROM turma_curso tc WHERE tc.turma_id = t.id "
                "  AND tc.ativo IS TRUE) ORDER BY t.id"
            )
        ).all()
        print("-- turma ativa sem oferta ativa --")
        for r in turmas_sem_oferta:
            print(f"   turma {r.id} - {r.nome}")
        if not turmas_sem_oferta:
            print("   (nenhuma)")

        print(
            f"aplicado: {len(removiveis)} oferta(s) removida(s); "
            f"bloqueada(s): {bloqueadas or 'nenhuma'}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
