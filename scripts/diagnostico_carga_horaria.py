"""
================================================================================
DIAGNOSTICO_CARGA_HORARIA.PY - Conferência de Carga Horária de um curso
================================================================================

Reconstrói, a partir do banco, o cálculo de C.H. Total de um curso e cruza com
a função de produção (`calcular_carga_horaria_curso`) para validar se o valor
exibido na tabela de cursos está matematicamente correto.

Uso:
    python scripts/diagnostico_carga_horaria.py [nome_do_curso] [trecho_periodo]

    python scripts/diagnostico_carga_horaria.py
        -> busca 'nata' no curso e '2026.2' no período (padrões do caso da Natação)

    python scripts/diagnostico_carga_horaria.py natação 2026
        -> filtra curso contendo 'natação' e período contendo '2026'

Regra de negócio conferida:
    C.H. Total = C.H. Aula x dias de aula das turmas ATIVAS do curso no período,
    onde dias de aula = dias da semana da turma entre data_inicio e data_fim,
    EXCLUINDO os dias sem aula (DiaBloqueado) com exceções por turma (DiaBloqueadoTurma).
================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path para importar o pacote `app`
# mesmo quando executado como `python scripts/diagnostico_carga_horaria.py`.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.models.academico import PeriodoLetivo, Turma
from app.models.calendario import DiaBloqueado, DiaBloqueadoTurma
from app.models.pedagogico import Curso
from app.utils.logica import (
    _blocked_dates_str,
    calcular_carga_horaria_curso,
    calcular_dias_aula_turma,
    gerar_datas,
)

# Nomes dos dias da semana em pt-BR, indexados por date.weekday() (segunda=0).
DIAS_SEMANA = ['segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo']

# Padrões de busca (sobrescritos pelos argumentos de linha de comando).
FILTRO_CURSO = "nata"
FILTRO_PERIODO = "2026.2"


def _dt(iso: str):
    """Converte 'YYYY-MM-DD' de volta em date para exibir o dia da semana."""
    from datetime import datetime
    return datetime.strptime(iso, "%Y-%m-%d").date()


def _linhas(label: str) -> None:
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)


def analisar_turma(turma: Turma) -> None:
    periodo = turma.periodo_letivo
    curso = turma.curso

    _linhas(f"TURMA: {turma.nome}")
    print(f"  Ativa?            : {turma.ativo}")
    print(f"  Período letivo    : {periodo.nome if periodo else '—'} "
          f"({periodo.data_inicio} a {periodo.data_fim})" if periodo else "  Período letivo    : —")
    print(f"  Curso             : {curso.nome if curso else '—'}")
    print(f"  C.H. Aula (curso) : {curso.carga_horaria}h" if curso else "  C.H. Aula (curso) : —")
    print(f"  Dias da semana    : {turma.dias_semana}")
    print(f"  Datas da turma    : {turma.data_inicio} a {turma.data_fim}")

    # Datas efetivamente geradas pelo sistema (mesma fonte da pauta/carga).
    blocked = _blocked_dates_str(turma)
    datas = gerar_datas(turma, incluir_futuro=True, blocked_dates=blocked)

    # Quebra por dia da semana dos dias de aula realmente contados.
    quebra = {}
    for iso in datas:
        wd = DIAS_SEMANA[_dt(iso).weekday()]
        quebra[wd] = quebra.get(wd, 0) + 1

    print(f"\n  Dias de aula computados pelo sistema : {len(datas)}")
    for wd, qtd in sorted(quebra.items(), key=lambda kv: -kv[1]):
        print(f"     • {wd.capitalize():<8}: {qtd}")

    # Dias bloqueados do período e em quais dias da semana caem.
    if periodo:
        bloqueios = (
            DiaBloqueado.query.filter_by(periodo_letivo_id=periodo.id)
            .order_by(DiaBloqueado.data)
            .all()
        )
        print(f"\n  Dias sem aula no período ({len(bloqueios)}):")
        if not bloqueios:
            print("     (nenhum)")
        dias_semana_do_curso = {
            d.strip() for d in (turma.dias_semana or "").split(",") if d.strip()
        }
        for b in bloqueios:
            wd = DIAS_SEMANA[b.data.weekday()]
            impacto = "  ⟶ REDUZ a carga (coincide com dia da turma)" if wd in dias_semana_do_curso else ""
            print(f"     • {b.data} ({wd}) — {b.tipo}{impacto}")

        excecoes = DiaBloqueadoTurma.query.filter_by(turma_id=turma.id).all()
        if excecoes:
            print(f"\n  Exceções por turma (dia bloqueado que volta a ter aula):")
            for e in excecoes:
                print(f"     • {e.data} ({DIAS_SEMANA[e.data.weekday()]})")

    # Cruzamento com as funções de produção.
    dias_via_funcao = calcular_dias_aula_turma(turma)
    carga_aula = curso.carga_horaria or 0 if curso else 0
    carga_esperada = carga_aula * dias_via_funcao if carga_aula else None

    print(f"\n  CONFIRA (funções de produção):")
    print(f"     calcular_dias_aula_turma  = {dias_via_funcao}")
    print(f"     C.H. Total (2h x dias)    = {carga_esperada}h")

    if curso:
        oficial = calcular_carga_horaria_curso(curso)
        print(f"\n  valor_exibido_na_tabela (todas as turmas ativas do curso):")
        print(f"     dias_aula   = {oficial['dias_aula']}")
        print(f"     carga_total = {oficial['carga_total']}h")


def main() -> None:
    global FILTRO_CURSO, FILTRO_PERIODO
    if len(sys.argv) >= 2:
        FILTRO_CURSO = sys.argv[1]
    if len(sys.argv) >= 3:
        FILTRO_PERIODO = sys.argv[2]

    app = create_app()
    with app.app_context():
        periodos = (
            PeriodoLetivo.query.filter(
                PeriodoLetivo.nome.ilike(f"%{FILTRO_PERIODO}%")
            ).all()
        )
        if not periodos:
            _linhas(f"Nenhum período contendo '{FILTRO_PERIODO}'. Períodos existentes:")
            for p in PeriodoLetivo.query.order_by(PeriodoLetivo.nome).all():
                print(f"     • [{p.id}] {p.nome} ({p.data_inicio} a {p.data_fim})")
            return

        encontrados = 0
        for p in periodos:
            turmas = (
                Turma.query.join(Curso, Turma.curso_id == Curso.id)
                .filter(
                    Turma.periodo_letivo_id == p.id,
                    Curso.nome.ilike(f"%{FILTRO_CURSO}%"),
                )
                .all()
            )
            for t in turmas:
                analisar_turma(t)
                encontrados += 1

        if not encontrados:
            _linhas(
                f"Nenhuma turma com curso contendo '{FILTRO_CURSO}' "
                f"no período '{FILTRO_PERIODO}'."
            )
            print("  Cursos desta unidade:")
            for c in Curso.query.order_by(Curso.nome).all():
                print(f"     • [{c.id}] {c.nome} (C.H. Aula = {c.carga_horaria}h)")


if __name__ == "__main__":
    main()