"""
================================================================================
VERIFICAR_H3E_LEITORES.PY - Ensaio dos leitores de dias/horário pela grade (H3e)
================================================================================

Compara, no banco informado (scratch `pautaon_ensaio`), o que cada leitor
migrado no H3e exibe AGORA (grade) com o texto que exibia ANTES (projeção
escalar), oferta por oferta:

    leitor                         ANTES (escalar)              DEPOIS (grade)
    dashboard (resumo)             turma.dias_semana /          GradeExibicao da
                                   turma.hora_*                 oferta
    dashboard (pendência por data) oferta.hora_* (par único)     intervalo_do_dia
                                                                 (weekday da data)
    aluno (histórico)              turma.dias_semana /          grade da oferta
                                   turma.hora_*
    ficha do aluno                 _dias_horario(turma)         _dias_horario(turma,
                                                                 oferta)
    conselho (painel/fechamento)   turma.dias_semana /          grade da oferta
                                   turma.hora_*
    frequência (seletor)           turma.hora_*                 grade da oferta

Regra de aceite:
    - oferta cuja grade ESPELHA a projeção escalar (caso uniforme): 0
      divergências em todos os leitores;
    - oferta com grade NÃO uniforme ou sem grade (legado): divergência é
      legítima e é listada à parte, com o motivo — nunca silenciada.

Uso:
    python scripts/verificar_h3e_leitores.py                  # banco do .env
    python scripts/verificar_h3e_leitores.py --banco pautaon_ensaio

Somente LEITURA: nenhum INSERT/UPDATE/DELETE. Exit 0 = conforme; exit 1 =
divergência inesperada ou head errada.
================================================================================
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

load_dotenv(ROOT / ".env")

HEAD_ESPERADA = "5730d7c594ba"


def _aplicar_banco(nome: str) -> None:
    """Troca só o nome do banco no DATABASE_URL (senha nunca é exibida)."""
    bruto = os.environ.get("DATABASE_URL") or ""
    if not bruto:
        raise SystemExit("DATABASE_URL ausente: rode a partir da raiz do projeto.")
    url = make_url(bruto)
    os.environ["DATABASE_URL"] = url.set(database=nome).render_as_string(
        hide_password=False
    )


def _par(valor_ini: time | None, valor_fim: time | None) -> str | None:
    if valor_ini is None or valor_fim is None:
        return None
    return f"{valor_ini:%H:%M} às {valor_fim:%H:%M}"


def _par_curto(valor_ini: time | None, valor_fim: time | None) -> str | None:
    if valor_ini is None or valor_fim is None:
        return None
    return f"{valor_ini:%H:%M}–{valor_fim:%H:%M}"


def _csv_dias(texto: str | None) -> str | None:
    if not texto:
        return None
    return texto.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensaio dos leitores H3e.")
    parser.add_argument(
        "--banco",
        default=None,
        help="nome do banco a usar (padrão: o do DATABASE_URL)",
    )
    args = parser.parse_args()
    if args.banco:
        _aplicar_banco(args.banco)

    from sqlalchemy import select, text
    from sqlalchemy.orm import configure_mappers, selectinload

    from app import create_app
    from app.database import db
    from app.models import Turma, TurmaCurso
    from app.relatorios.painel_pedagogico.ficha_aluno import _dias_horario
    from app.services.turma_curso_horario import (
        grades_para_exibicao,
        grades_por_oferta,
        intervalo_do_dia,
    )
    from app.services.turma_curso import datas_esperadas_oferta

    app = create_app()
    falhas = 0
    legitimos = 0
    leituras = 0

    def _falha(msg: str) -> None:
        nonlocal falhas
        falhas += 1
        print(f"FALHA: {msg}")

    with app.app_context():
        configure_mappers()

        head = db.session.execute(
            text("select version_num from alembic_version")
        ).scalar()
        if head != HEAD_ESPERADA:
            _falha(f"head Alembic {head!r} ≠ esperada {HEAD_ESPERADA!r}")

        turmas = (
            db.session.execute(
                select(Turma)
                .options(
                    selectinload(Turma.ofertas_curso).selectinload(
                        TurmaCurso.horarios
                    )
                )
                .where(Turma.ativo.is_(True))
                .order_by(Turma.id)
            )
            .unique()
            .scalars()
            .all()
        )
        ofertas = (
            db.session.execute(
                select(TurmaCurso)
                .options(
                    selectinload(TurmaCurso.turma),
                    selectinload(TurmaCurso.horarios),
                )
                .where(TurmaCurso.ativo.is_(True))
                .order_by(TurmaCurso.id)
            )
            .scalars()
            .all()
        )
        grades = grades_por_oferta(ofertas)
        exibicao = grades_para_exibicao(ofertas, grades=grades)

        print(f"turmas ativas: {len(turmas)} | ofertas ativas: {len(ofertas)}")
        print("-" * 78)

        for oferta in ofertas:
            turma = oferta.turma
            grade = exibicao.get(oferta.id)
            if grade is None:
                _falha(f"oferta {oferta.id}: sem GradeExibicao")
                continue

            linhas = grades.get(oferta.id) or []
            ativas_da_turma = [o for o in getattr(turma, "ofertas_curso", ()) if o.ativo]
            # Turma com 2+ ofertas: o leitor ANTIGO (aluno/ficha/conselho) mostrava
            # o par escalar da TURMA em todas as ofertas; agora cada oferta mostra
            # a própria grade — divergência esperada e legítima.
            multi = len(ativas_da_turma) >= 2
            escalar_dias = _csv_dias(turma.dias_semana) if turma else None
            escalar_hora = _par(
                oferta.hora_inicio or (turma.hora_inicio if turma else None),
                oferta.hora_fim or (turma.hora_fim if turma else None),
            )
            escalar_hora_turma = _par(
                turma.hora_inicio if turma else None,
                turma.hora_fim if turma else None,
            )

            # 1) Dashboard (resumo) e aluno/conselho/transferir: grade x escalar.
            leituras += 2
            if grade.dias_texto != escalar_dias:
                if multi:
                    legitimos += 1
                    print(
                        f"OK(multi): oferta {oferta.id} dias {grade.dias_texto!r} "
                        f"≠ par da turma {escalar_dias!r} (antes era único na turma)"
                    )
                else:
                    _falha(
                        f"oferta {oferta.id}: dias {grade.dias_texto!r} ≠ "
                        f"escalar {escalar_dias!r}"
                    )
            if grade.texto_horario != (escalar_hora or ""):
                if multi:
                    legitimos += 1
                    print(
                        f"OK(multi): oferta {oferta.id} horário "
                        f"{grade.texto_horario!r} ≠ par da oferta/turma "
                        f"{escalar_hora!r}"
                    )
                else:
                    _falha(
                        f"oferta {oferta.id}: horário {grade.texto_horario!r} ≠ "
                        f"escalar {escalar_hora!r}"
                    )

            # 2) Dashboard (pendências por data): intervalo do weekday x escalar.
            datas = datas_esperadas_oferta(oferta, None)
            for data in datas:
                leituras += 1
                intervalo = intervalo_do_dia(oferta, data)
                esperado = (
                    oferta.hora_inicio or (turma.hora_inicio if turma else None),
                    oferta.hora_fim or (turma.hora_fim if turma else None),
                )
                if intervalo is None:
                    if linhas:
                        _falha(
                            f"oferta {oferta.id}: data {data} sem intervalo na grade"
                        )
                    continue
                if intervalo != esperado and grade.uniforme:
                    _falha(
                        f"oferta {oferta.id}: data {data} intervalo {intervalo} ≠ "
                        f"escalar {esperado}"
                    )
            if not linhas:
                legitimos += 1
                print(
                    f"OK(legado): oferta {oferta.id} sem grade — leitores usam "
                    "a projeção escalar (logger.warning)"
                )

            # 3) Ficha do aluno: _dias_horario(turma, oferta) x _dias_horario(turma).
            leituras += 1
            depois = _dias_horario(turma, oferta)
            antes = _dias_horario(turma)
            if depois != antes:
                if multi:
                    legitimos += 1
                    print(
                        f"OK(multi): ficha da oferta {oferta.id} {depois!r} ≠ "
                        f"{antes!r} (antes usava o par da turma)"
                    )
                else:
                    _falha(
                        f"oferta {oferta.id}: ficha {depois!r} ≠ {antes!r}"
                    )

            # 4) Conselho (painel/fechamento): grade x par escalar da TURMA.
            leituras += 1
            conselho_antes = (
                f"{escalar_dias} | {escalar_hora_turma}"
                if escalar_dias and escalar_hora_turma
                else None
            )
            conselho_depois = (
                f"{grade.dias_texto} | {grade.texto_horario}"
                if grade.dias_texto and grade.texto_horario
                else None
            )
            if conselho_depois != conselho_antes:
                if multi:
                    legitimos += 1
                else:
                    _falha(
                        f"oferta {oferta.id}: conselho {conselho_depois!r} ≠ "
                        f"{conselho_antes!r}"
                    )

        print("-" * 78)
        print(
            f"leituras comparadas: {leituras} | divergências inesperadas: "
            f"{falhas} | divergências legítimas (multi-oferta/legado): {legitimos}"
        )

    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
