"""Saneamento do professor da OFERTA (G1 — P1c). Dry-run por padrão.

Toda oferta deve ter professor (regra G1). Antes de tornar o campo obrigatório no
serviço e na UI, este script mede e (opcionalmente) corrige o que ficou sem
professor.

Regra automática (só o que é seguro):
  * oferta com `professor_id` NULL cuja TURMA tem `professor_id` preenchido **e**
    cujo professor pertence à mesma unidade da turma → copia `turma.professor_id`;
  * todo o resto é apenas LISTADO (a instituição decide quem é o professor).

Uso (o padrão não escreve nada):
    python scripts/saneamento_professor_oferta.py                     # dry-run
    python scripts/saneamento_professor_oferta.py --banco ensaio      # dry-run
    python scripts/saneamento_professor_oferta.py --banco ensaio --aplicar
    python scripts/saneamento_professor_oferta.py --banco principal --aplicar \
        --autorizar-principal

Segurança:
  * `--aplicar` só é aceito em banco cujo nome contém "ensaio", salvo
    `--autorizar-principal` (autorização expressa do usuário);
  * a DSN é montada a partir do `.env` com **apenas o nome do banco** trocado e
    entregue via classe de configuração — `DATABASE_URL` do shell não é usada
    nem alterada;
  * a única escrita é `UPDATE turma_curso.professor_id`; idempotente: depois de
    aplicar, o grupo "copiável" fica vazio;
  * ofertas inativas entram só com `--incluir-inativas`.
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


def _dsn(banco: str) -> str:
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
        return f"{base}/{banco}"
    return valor


def _mascarar(dsn: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@]*@", r"\1***@", dsn)


def _nome_banco(dsn: str) -> str:
    return dsn.rpartition("/")[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Saneamento do professor da oferta (dry-run por padrão).",
    )
    parser.add_argument(
        "--banco", default="principal", choices=BANCOS,
        help="'principal' (pautaon) ou o nome de um banco de ensaio",
    )
    parser.add_argument(
        "--nome-ensaio", default="pautaon_ensaio",
        help="nome do banco de ensaio usado com --banco ensaio",
    )
    parser.add_argument(
        "--aplicar", action="store_true",
        help="grava as cópias seguras (sem isso, apenas relata)",
    )
    parser.add_argument(
        "--autorizar-principal", action="store_true",
        help="autorização expressa para aplicar no banco principal",
    )
    parser.add_argument(
        "--incluir-inativas", action="store_true",
        help="inclui ofertas inativas no levantamento",
    )
    args = parser.parse_args(argv)

    banco = args.nome_ensaio if args.banco == "ensaio" else "principal"
    dsn = _dsn(banco)
    alvo = _nome_banco(dsn)

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
    from app.models import Turma, TurmaCurso, User  # noqa: E402
    from sqlalchemy import select  # noqa: E402

    app = create_app(AlvoConfig)
    print(f"alvo: {_mascarar(dsn)}")
    print(f"modo: {'APLICAR' if args.aplicar else 'dry-run'}")

    with app.app_context():
        filtros = [TurmaCurso.professor_id.is_(None)]
        if not args.incluir_inativas:
            filtros.append(TurmaCurso.ativo.is_(True))
        linhas = db.session.execute(
            select(TurmaCurso, Turma)
            .join(Turma, Turma.id == TurmaCurso.turma_id)
            .where(*filtros)
            .order_by(Turma.unidade_id, TurmaCurso.turma_id, TurmaCurso.id)
        ).all()

        copiaveis, pendentes = [], []
        for oferta, turma in linhas:
            professor_da_turma = (
                db.session.get(User, turma.professor_id)
                if turma.professor_id
                else None
            )
            if professor_da_turma is not None and (
                professor_da_turma.unidade_id == turma.unidade_id
            ):
                copiaveis.append((oferta, turma, professor_da_turma))
            else:
                pendentes.append((oferta, turma))

        print(
            f"ofertas sem professor: {len(linhas)} "
            f"(copiáveis da turma: {len(copiaveis)}, "
            f"pendentes de decisão: {len(pendentes)})"
        )

        if copiaveis:
            print("-- cópia segura de turma.professor_id --")
            for oferta, turma, professor in copiaveis:
                print(
                    f"   oferta {oferta.id} (turma {turma.id}, "
                    f"unidade {turma.unidade_id}) -> {professor.name} "
                    f"({professor.email})"
                )
        if pendentes:
            print("-- pendentes: a turma não tem professor válido (decidir) --")
            for oferta, turma in pendentes:
                print(
                    f"   oferta {oferta.id} (turma {turma.id} - {turma.nome}, "
                    f"unidade {turma.unidade_id}, ativa={bool(oferta.ativo)}, "
                    f"professor_da_turma={turma.professor_id})"
                )

        if not args.aplicar:
            print("dry-run: nada foi alterado.")
            return 0

        if not copiaveis:
            print("nada a aplicar.")
            return 0

        for oferta, _turma, professor in copiaveis:
            oferta.professor_id = professor.id
        db.session.commit()
        print(f"aplicado: {len(copiaveis)} oferta(s) com professor copiado.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
