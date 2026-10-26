"""
================================================================================
VERIFICAR_H3C_CH.PY - Ensaio da C.H. por ocorrência (H3c)
================================================================================

Compara, no banco apontado por `DATABASE_URL` (scratch `pautaon_ensaio`):

    ANTES  (escalar, pré-H3c)   C.H. aula = par único da oferta/turma;
                                C.H. total = aula × datas de aula da oferta.
    DEPOIS (grade, H3c)         C.H. aula = duração uniforme da grade (None se
                                não uniforme); C.H. total = soma da duração da
                                grade em cada ocorrência válida.

Para cada turma com 2+ ofertas ativas imprime: total antigo, total novo (tempo
físico — união dos intervalos por data), total da oferta principal, soma dos
totais das ofertas e a causa da diferença; confere
`principal <= novo <= soma`.

Para turma com UMA oferta de grade uniforme exige `antigo == novo` — qualquer
divergência é FALHA e o script para com exit 1. Também lista C.H. aula/total
das ofertas reais, oferta a oferta.

Uso:
    python scripts/verificar_h3c_ch.py

Somente LEITURA: nenhum INSERT/UPDATE/DELETE. Exit 0 = tudo conforme;
exit 1 = alguma checagem falhou.
================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import create_app
from app.models import Turma, TurmaCurso
from app.services.turma_curso import datas_aula_oferta
from app.services.turma_curso_horario import (
    cargas_horarias_ofertas_em_lote,
    cargas_horarias_turmas_em_lote,
    grade_uniforme,
    resumo_grade,
)
from app.utils.formatters import formatar_ch
from app.utils.logica import _blocked_dates_str

TURMA_DESTAQUE = 9
HEAD_ESPERADA = "5730d7c594ba"


def _linha(status: str, msg: str) -> bool:
    """Imprime uma linha de checagem e retorna True se foi falha."""
    print(f"{status}: {msg}")
    return status == "FALHA"


def _aula_escalar(ini, fim) -> int | None:
    """Minutos de um par de horários (None se ausente ou fim <= início)."""
    if ini is None or fim is None:
        return None
    minutos = (fim.hour * 60 + fim.minute) - (ini.hour * 60 + ini.minute)
    return minutos if minutos > 0 else None


def _aula_escalar_oferta(oferta: TurmaCurso) -> int | None:
    """C.H. aula ANTIGA da oferta: par próprio, herdando o da turma."""
    ini, fim = oferta.hora_inicio, oferta.hora_fim
    if oferta.turma is not None:
        ini = ini or oferta.turma.hora_inicio
        fim = fim or oferta.turma.hora_fim
    return _aula_escalar(ini, fim)


def _total_antigo_oferta(oferta: TurmaCurso) -> int | None:
    """C.H. total ANTIGA da oferta: aula escalar × datas de aula."""
    aula = _aula_escalar_oferta(oferta)
    if aula is None:
        return None
    blocked = _blocked_dates_str(oferta.turma) if oferta.turma is not None else set()
    datas = datas_aula_oferta(oferta, blocked=blocked)
    return aula * len(datas) if datas else None


def _total_antigo_turma(turma: Turma) -> int | None:
    """C.H. total ANTIGA da turma: aula escalar da turma × dias efetivos."""
    aula = _aula_escalar(turma.hora_inicio, turma.hora_fim)
    dias = turma.dias_aula_efetivos()
    return aula * dias if aula and dias else None


def _fmt(minutos: int | None) -> str:
    return formatar_ch(minutos)


def _causa(antigo, novo, principal, soma, ofertas) -> str:
    """Texto curto explicando a diferença entre ANTIGO e NOVO."""
    partes = [f"{len(ofertas)} oferta(s) ativa(s)"]
    if soma is not None and novo is not None:
        if soma > novo:
            partes.append(
                f"-{_fmt(soma - novo)} de sobreposição deduplicada por data"
            )
        else:
            partes.append("datas/horários disjuntos: tempo físico soma as ofertas")

    nao_uniforme = [o for o in ofertas if not grade_uniforme(o)]
    if nao_uniforme:
        partes.append("grade não uniforme: não há um par único de aula")
    if antigo is not None and novo is not None and antigo != novo:
        partes.append("antes: par escalar único × dias da união")
    if principal is not None and principal != novo:
        partes.append("total da principal ≠ total da turma")
    return "; ".join(partes)


def main() -> int:
    app = create_app()
    falhas = 0
    with app.app_context():
        from sqlalchemy import text

        from app.database import db

        head = db.session.execute(text("select version_num from alembic_version")).scalar()
        if head != HEAD_ESPERADA:
            falhas += _linha(
                "FALHA",
                f"head Alembic {head!r} ≠ esperada {HEAD_ESPERADA!r} — banco errado",
            )

        turmas = db.session.execute(
            select(Turma).order_by(Turma.id)
        ).scalars().all()
        ofertas = db.session.execute(
            select(TurmaCurso)
            .options(
                selectinload(TurmaCurso.turma),
                selectinload(TurmaCurso.horarios),
            )
            .where(TurmaCurso.ativo.is_(True))
            .order_by(TurmaCurso.id)
        ).scalars().all()
        por_turma: dict[int, list[TurmaCurso]] = {}
        for oferta in ofertas:
            por_turma.setdefault(oferta.turma_id, []).append(oferta)
        carga_turma = cargas_horarias_turmas_em_lote(turmas)
        carga_oferta = cargas_horarias_ofertas_em_lote(ofertas)

        print("=" * 100)
        print(f"ENSAIO H3c — C.H. por ocorrência | banco: {db.engine.url.database}")
        print(f"head Alembic: {head}")
        print("=" * 100)

        # --- 1. Turmas com 2+ ofertas ---------------------------------------
        multi = [t for t in turmas if len(por_turma.get(t.id, [])) >= 2]
        print(
            f"\n[1] Turmas com 2+ ofertas ativas: {len(multi)} "
            f"(de {len(turmas)} turmas, {len(ofertas)} ofertas ativas)\n"
        )
        cabecalho = (
            f"{'turma':>7} {'ofertas':>7} {'antigo':>9} {'novo':>9} "
            f"{'principal':>10} {'soma':>9} {'causa'}"
        )
        print(cabecalho)
        print("-" * len(cabecalho))
        for turma in multi:
            ativas = por_turma.get(turma.id, [])
            antigo = _total_antigo_turma(turma)
            novo = carga_turma[turma.id].carga_horaria_total
            principal = None
            principal_oferta = next((o for o in ativas if o.principal), ativas[0])
            if principal_oferta is not None:
                principal = carga_oferta[principal_oferta.id].carga_horaria_total
            soma = sum(
                (carga_oferta[o.id].carga_horaria_total or 0) for o in ativas
            ) or None
            print(
                f"{turma.id:>7} {len(ativas):>7} {_fmt(antigo):>9} {_fmt(novo):>9} "
                f"{_fmt(principal):>10} {_fmt(soma):>9} "
                f"{_causa(antigo, novo, principal, soma, ativas)}"
            )
            if novo is None:
                falhas += _linha("FALHA", f"turma {turma.id} sem C.H. total")
                continue
            if principal is not None and principal > novo:
                falhas += _linha(
                    "FALHA",
                    f"turma {turma.id}: principal ({_fmt(principal)}) > novo ({_fmt(novo)})",
                )
            if soma is not None and novo > soma:
                falhas += _linha(
                    "FALHA",
                    f"turma {turma.id}: novo ({_fmt(novo)}) > soma das ofertas ({_fmt(soma)})",
                )
            if principal is not None and soma is not None and principal <= novo <= soma:
                print(
                    f"        OK: turma {turma.id} principal {_fmt(principal)} <= "
                    f"novo {_fmt(novo)} <= soma {_fmt(soma)}"
                )
            if turma.id == TURMA_DESTAQUE:
                aula = _aula_escalar(turma.hora_inicio, turma.hora_fim)
                print(
                    f"        ↳ TURMA {TURMA_DESTAQUE} (destaque): antigo {_fmt(antigo)} "
                    f"→ novo {_fmt(novo)} "
                    f"({'+' if (novo or 0) >= (antigo or 0) else '-'}"
                    f"{_fmt(abs((novo or 0) - (antigo or 0)))})"
                )
                print(
                    f"          antigo = {_fmt(aula)} (par escalar da turma) × "
                    f"{turma.dias_aula_efetivos()} dias da união"
                )
                print(
                    f"          novo   = {len(ativas)} ofertas por data, "
                    f"soma {_fmt(soma)}"
                    + (
                        f" − {_fmt((soma or 0) - novo)} de sobreposição"
                        if soma is not None and soma > novo
                        else ""
                    )
                )
                for item in ativas:
                    print(
                        f"            oferta {item.id}: "
                        f"{_fmt(carga_oferta[item.id].carga_horaria_total)}"
                        f" — {resumo_grade(item) or '(sem grade)'}"
                    )
                print(f"          causa: {_causa(antigo, novo, principal, soma, ativas)}")

        # --- 2. Turmas de UMA oferta uniforme: antigo == novo ----------------
        unicas = [t for t in turmas if len(por_turma.get(t.id, [])) == 1]
        uniformes = [
            t for t in unicas if grade_uniforme(por_turma.get(t.id, [])[0])
        ]
        print(
            f"\n[2] Turmas com 1 oferta: {len(unicas)} "
            f"— grade uniforme (exige antigo == novo): {len(uniformes)}\n"
        )
        for turma in sorted(unicas, key=lambda t: t.id):
            oferta = por_turma.get(turma.id, [])[0]
            antigo = _total_antigo_turma(turma)
            novo = carga_turma[turma.id].carga_horaria_total
            uniforme = grade_uniforme(oferta)
            if not uniforme:
                print(
                    f"        turma {turma.id}: grade NÃO uniforme — antigo {_fmt(antigo)} "
                    f"× novo {_fmt(novo)} (mudança prevista pelo contrato)"
                )
                continue
            if antigo != novo:
                falhas += _linha(
                    "FALHA",
                    f"turma {turma.id} (1 oferta uniforme) divergiu: "
                    f"antigo {_fmt(antigo)} × novo {_fmt(novo)} — PARE",
                )
                continue
            print(
                f"OK: turma {turma.id} (1 oferta uniforme) antigo == novo == "
                f"{_fmt(novo)}"
            )

        # --- 3. Ofertas reais: C.H. aula/total ANTES × DEPOIS ----------------
        print(f"\n[3] Ofertas ativas: {len(ofertas)} — C.H. aula/total antes × depois\n")
        cabecalho = (
            f"{'oferta':>7} {'turma':>6} {'aula ant.':>10} {'aula dep.':>10} "
            f"{'total ant.':>11} {'total dep.':>11}  grade"
        )
        print(cabecalho)
        print("-" * len(cabecalho))
        for oferta in sorted(ofertas, key=lambda o: o.id):
            carga = carga_oferta[oferta.id]
            print(
                f"{oferta.id:>7} {oferta.turma_id:>6} "
                f"{_fmt(_aula_escalar_oferta(oferta)):>10} "
                f"{_fmt(carga.carga_horaria_aula):>10} "
                f"{_fmt(_total_antigo_oferta(oferta)):>11} "
                f"{_fmt(carga.carga_horaria_total):>11}  "
                f"{resumo_grade(oferta) or '(sem grade)'}"
            )

        print()
        if falhas:
            print(f"RESULTADO: {falhas} falha(s).")
            return 1
        print("RESULTADO: todas as checagens passaram.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
