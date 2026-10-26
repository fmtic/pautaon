"""
================================================================================
VERIFICAR_H3D_FILTROS.PY - Ensaio dos filtros/listagem pela grade (H3d)
================================================================================

Compara, no banco informado (scratch `pautaon_ensaio`), o conjunto de turmas
retornado pelos filtros de dia e de horário ANTES x DEPOIS da migração:

    ANTES  (pré-H3d)  dois EXISTS independentes:
                      dia   -> COALESCE(oferta.dias_semana, turma.dias_semana)
                               ILIKE '%dia%'
                      hora  -> COALESCE(oferta.hora_inicio, turma.hora_inicio)
                               == horário (igualdade na HORA DE INÍCIO)
                      dia + hora podiam casar em ofertas/linhas diferentes.

    DEPOIS (grade)    um único EXISTS em `turma_curso_horario` (oferta ativa):
                      dia/hora precisam casar na MESMA linha; turma sem oferta
                      ativa com grade cai no comparador escalar antigo.

Também confere a agregação de dias da Turma (união das ofertas ativas pela
grade x união do CSV projetado) e a C.H. por aula da turma (valor ou "varia").

Regra de aceite:
    - combinações REAIS (dia, hora de início de uma linha da grade): 0
      divergências;
    - varredura completa (todos os dias 0–5 × horários de início e de fim):
      divergências apenas por REMOÇÃO (falso-positivo do comparador antigo,
      previsto pelo contrato). Qualquer ADIÇÃO é FALHA.

Uso:
    python scripts/verificar_h3d_filtros.py                    # banco do .env
    python scripts/verificar_h3d_filtros.py --banco pautaon_ensaio

Somente LEITURA: nenhum INSERT/UPDATE/DELETE. Exit 0 = conforme; exit 1 =
alguma checagem falhou.
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

from sqlalchemy import and_, func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

HEAD_ESPERADA = "5730d7c594ba"
DIAS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")


def _aplicar_banco(nome: str) -> None:
    """Troca só o nome do banco no DATABASE_URL (senha nunca é exibida)."""
    bruto = os.environ.get("DATABASE_URL") or ""
    if not bruto:
        raise SystemExit("DATABASE_URL ausente: rode a partir da raiz do projeto.")
    url = make_url(bruto)
    os.environ["DATABASE_URL"] = url.set(database=nome).render_as_string(
        hide_password=False
    )


def _fmt_hora(valor: time | None) -> str | None:
    return f"{valor:%H:%M}" if valor is not None else None


def _linha(status: str, msg: str) -> bool:
    print(f"{status}: {msg}")
    return status == "FALHA"


def main() -> int:  # noqa: C901 - ensaio linear, um bloco por checagem
    parser = argparse.ArgumentParser(description="Ensaio dos filtros H3d.")
    parser.add_argument(
        "--banco",
        default=None,
        help="nome do banco a usar (padrão: o do DATABASE_URL)",
    )
    args = parser.parse_args()
    if args.banco:
        _aplicar_banco(args.banco)

    from app import create_app
    from app.database import db
    from app.models import Turma, TurmaCurso
    from app.registros.turmas import (
        _filtro_por_oferta,
        _resumo_ofertas,
        aplicar_filtros_turmas,
    )
    from app.services.turma_curso_horario import (
        cargas_horarias_ofertas_em_lote,
        cargas_horarias_turmas_em_lote,
        grades_para_exibicao,
        grades_por_oferta,
    )
    from app.utils.dias_semana import csv_para_weekdays, token_para_weekday

    app = create_app()
    falhas = 0
    with app.app_context():
        from sqlalchemy import text
        from sqlalchemy.orm import configure_mappers, selectinload

        # O backref `Turma.ofertas_curso` só existe depois de configurar os
        # mappers; sem isso o `selectinload` levanta AttributeError.
        configure_mappers()

        head = db.session.execute(
            text("select version_num from alembic_version")
        ).scalar()
        if head != HEAD_ESPERADA:
            falhas += _linha(
                "FALHA",
                f"head Alembic {head!r} ≠ esperada {HEAD_ESPERADA!r} — banco errado",
            )

        turmas = (
            db.session.execute(
                select(Turma)
                .options(
                    selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.horarios)
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
        carga_turma = cargas_horarias_turmas_em_lote(turmas)
        carga_oferta = cargas_horarias_ofertas_em_lote(ofertas)
        exibicao = grades_para_exibicao(ofertas, carga_oferta, grades)

        base_antes = select(Turma).where(Turma.ativo.is_(True))
        base_depois = select(Turma).where(Turma.ativo.is_(True))

        def _cond_antiga(dia: str | None, horario: time | None):
            """Condições do comparador ANTIGO (EXISTS independentes)."""
            conds = []
            if dia:
                conds.append(
                    _filtro_por_oferta(
                        func.coalesce(
                            TurmaCurso.dias_semana, Turma.dias_semana
                        ).ilike(f"%{dia}%"),
                        Turma.dias_semana.ilike(f"%{dia}%"),
                    )
                )
            if horario is not None:
                conds.append(
                    _filtro_por_oferta(
                        func.coalesce(
                            TurmaCurso.hora_inicio, Turma.hora_inicio
                        )
                        == horario,
                        Turma.hora_inicio == horario,
                    )
                )
            return and_(*conds) if conds else None

        def _conjunto(stmt) -> set[int]:
            return set(db.session.execute(stmt).scalars().all())

        def _antes(dia, horario) -> set[int]:
            cond = _cond_antiga(dia, horario)
            if cond is None:
                return _conjunto(base_antes)
            return _conjunto(base_antes.where(cond))

        def _depois(dia, horario) -> set[int]:
            filtros = {}
            if dia:
                filtros["dia"] = dia
            if horario is not None:
                filtros["horario_inicio"] = _fmt_hora(horario)
            return _conjunto(aplicar_filtros_turmas(base_depois, filtros))

        print("=" * 100)
        print(f"ENSAIO H3d — filtros/listagem pela grade | banco: {db.engine.url.database}")
        print(f"head Alembic: {head}")
        print(f"turmas ativas: {len(turmas)} | ofertas ativas: {len(ofertas)}")
        print("=" * 100)

        # --- 1. Combinações REAIS (linha da grade): 0 divergências ------------
        reais = set()
        for oferta in ofertas:
            for linha in grades.get(oferta.id, []):
                reais.add((linha.dia_semana, linha.hora_inicio))
        reais = sorted(reais)
        print(f"\n[1] Combinações reais (dia, hora de início): {len(reais)}")
        divergencias_reais = 0
        for dia_num, horario in reais:
            dia = DIAS[dia_num]
            antes, depois = _antes(dia, horario), _depois(dia, horario)
            if antes != depois:
                divergencias_reais += 1
                print(
                    f"    {dia} {_fmt_hora(horario)}: antes {sorted(antes)} ≠ "
                    f"depois {sorted(depois)}"
                )
        if divergencias_reais:
            falhas += _linha(
                "FALHA", f"{divergencias_reais} divergência(s) em combinações reais"
            )
        else:
            print("    OK: 0 divergências em todas as combinações reais.")

        # --- 2. Varredura: dias isolados, horários isolados, dia + horário ----
        candidatos = sorted(
            {l.hora_inicio for o in ofertas for l in grades.get(o.id, [])}
            | {l.hora_fim for o in ofertas for l in grades.get(o.id, [])}
            | {t.hora_inicio for t in turmas if t.hora_inicio}
            | {t.hora_fim for t in turmas if t.hora_fim}
        )
        removidas, adicionadas = [], []
        for dia_num in range(6):
            dia = DIAS[dia_num]
            antes, depois = _antes(dia, None), _depois(dia, None)
            for turma_id in antes - depois:
                removidas.append((f"dia {dia}", turma_id))
            for turma_id in depois - antes:
                adicionadas.append((f"dia {dia}", turma_id))
        for horario in candidatos:
            antes, depois = _antes(None, horario), _depois(None, horario)
            for turma_id in antes - depois:
                removidas.append((f"hora {_fmt_hora(horario)}", turma_id))
            for turma_id in depois - antes:
                adicionadas.append((f"hora {_fmt_hora(horario)}", turma_id))
        for dia_num in range(6):
            dia = DIAS[dia_num]
            for horario in candidatos:
                antes, depois = _antes(dia, horario), _depois(dia, horario)
                for turma_id in antes - depois:
                    removidas.append((f"{dia} + {_fmt_hora(horario)}", turma_id))
                for turma_id in depois - antes:
                    adicionadas.append((f"{dia} + {_fmt_hora(horario)}", turma_id))

        print(
            f"\n[2] Varredura completa: {6 * len(candidatos)} combinações dia+horário "
            f"({len(candidatos)} horários candidatos)"
        )
        if removidas:
            print(
                f"    remoções (falso-positivo antigo, previstas): {len(removidas)}"
            )
            for rotulo, turma_id in removidas[:20]:
                print(f"      - turma {turma_id} em {rotulo}")
        if adicionadas:
            falhas += _linha(
                "FALHA",
                f"{len(adicionadas)} ADIÇÃO(ões) — a grade não pode casar mais que o "
                f"comparador antigo: {adicionadas[:10]}",
            )
        if not removidas and not adicionadas:
            print("    OK: 0 divergências na varredura (conjuntos idênticos).")

        # --- 3. Agregação de dias por turma ----------------------------------
        print(f"\n[3] Agregação de dias por turma: {len(turmas)} turmas\n")
        cabecalho = f"{'turma':>7} {'nome':<22} {'antes (CSV)':<34} {'depois (grade)'}"
        print(cabecalho)
        print("-" * len(cabecalho))
        for turma in turmas:
            ativas = [o for o in turma.ofertas_curso if o.ativo]
            antes_dias = set()
            for oferta in ativas:
                antes_dias.update(
                    csv_para_weekdays(oferta.dias_semana or turma.dias_semana)
                )
            if not ativas:
                antes_dias.update(csv_para_weekdays(turma.dias_semana))
            resumo = _resumo_ofertas(turma, grades)
            depois_dias = {token_para_weekday(d) for d in resumo["dias"]}
            rotulo_antes = (
                ", ".join(DIAS[d] for d in sorted(antes_dias)) or "(vazio)"
            )
            rotulo_depois = ", ".join(DIAS[d] for d in sorted(depois_dias)) or "(vazio)"
            print(f"{turma.id:>7} {turma.nome[:22]:<22} {rotulo_antes:<34} {rotulo_depois}")
            # Diferença só é aceita quando alguma oferta ativa é NÃO uniforme
            # (a projeção CSV não representa a grade por dia).
            if antes_dias != depois_dias:
                nao_uniformes = [
                    o.id for o in ativas
                    if exibicao.get(o.id) is not None and exibicao[o.id].por_dia_texto
                ]
                if nao_uniformes:
                    print(
                        f"        previsto: oferta(s) não uniforme {nao_uniformes} — "
                        f"a união passa a vir da grade"
                    )
                else:
                    falhas += _linha(
                        "FALHA",
                        f"turma {turma.id}: dias divergiram sem oferta não uniforme",
                    )

        # --- 4. C.H. por aula / min_ch_aula ----------------------------------
        print("\n[4] C.H. por aula e min_ch_aula (decisão H3d)\n")
        cabecalho = (
            f"{'turma':>7} {'ofertas':>7} {'aula turma':>11} {'min_ch_aula':>12}  oferta: aula"
        )
        print(cabecalho)
        print("-" * len(cabecalho))
        for turma in turmas:
            carga = carga_turma[turma.id]
            detalhes = []
            for oferta in sorted(
                (o for o in turma.ofertas_curso if o.ativo), key=lambda o: o.id
            ):
                exib = exibicao.get(oferta.id)
                aula = carga_oferta[oferta.id].carga_horaria_aula
                if exib is not None and exib.ch_aula_varia:
                    valor = "varia"
                elif aula is not None:
                    valor = f"{aula}min"
                else:
                    valor = "—"
                detalhes.append(f"{oferta.id}: {valor}")
            print(
                f"{turma.id:>7} {carga.ofertas_ativas:>7} "
                f"{str(carga.carga_horaria_aula) + 'min':>11} "
                f"{str(carga.min_ch_aula) + 'min':>12}  {', '.join(detalhes) or '—'}"
            )

        # --- 5. Textos de exibição -------------------------------------------
        print("\n[5] Texto de exibição por oferta (listagem/detalhe/impressão)\n")
        for oferta in sorted(ofertas, key=lambda o: o.id):
            exib = exibicao[oferta.id]
            print(
                f"    oferta {oferta.id} (turma {oferta.turma_id}): "
                f"dias={exib.dias_texto!r} "
                f"par={exib.hora_inicio or '--:--'}–{exib.hora_fim or '--:--'} "
                f"por_dia={exib.por_dia_texto!r} "
                f"ch_aula={'varia' if exib.ch_aula_varia else exib.ch_aula_min}"
            )

        print()
        if falhas:
            print(f"RESULTADO: {falhas} falha(s).")
            return 1
        print("RESULTADO: todas as checagens passaram.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
