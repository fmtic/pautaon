"""
================================================================================
FORMATTERS.PY - Helpers de formatação para exibição
================================================================================

Contém:
    - formatar_ch : converte minutos inteiros em string legível de C.H.

NOTAS DE ONDAS
    - Onda 3C: criado para suportar a exibição de carga horária calculada em
      minutos (Turma.carga_horaria_aula / Turma.carga_horaria_total).
================================================================================
"""


def formatar_ch(minutos: int | None) -> str:
    """
    Converte minutos inteiros em string legível de carga horária.

    Exemplos:
        formatar_ch(60)   → "1h"
        formatar_ch(90)   → "1h30min"
        formatar_ch(1800) → "30h"
        formatar_ch(None) → "—"
        formatar_ch(0)    → "—"
    """
    if not minutos or minutos < 0:
        return "—"
    h = minutos // 60
    m = minutos % 60
    if m == 0:
        return f"{h}h"
    return f"{h}h{m:02d}min"
