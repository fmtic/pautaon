"""Agregação de frequência (1 consulta) e quebra semanal.

ETAPA D3b.2: o cálculo migrou para o serviço único
`app.services.frequencia_oferta`; este módulo fica como adaptador fino —
mantém o nome `FrequenciaTurma` e a função `agregar_por_turma` que os
leitores do painel (turma.py, periodo.py) já consomem, e preserva a
quebra semanal (Python puro, sem consulta).
"""

from __future__ import annotations

from datetime import date
from typing import Iterable

from app.models.enums import CONCEITOS_CONTABEIS, CONCEITOS_PRESENCA
from app.services.frequencia_oferta import TurmaFrequencia, agregar_por_turma as _agregar_turma

from .helpers import semana_de, pct

# Compatibilidade de nome: a estrutura é a do serviço (fonte única).
FrequenciaTurma = TurmaFrequencia


def agregar_por_turma(
    turmas_ids: Iterable[int],
    unidade_id: int | None = None,
) -> dict[int, FrequenciaTurma]:
    """Delegação ao serviço único (UMA consulta de frequência em lote).

    `unidade_id` estreita o escopo quando o chamador já filtra por unidade
    (visão por período); sem ele, soma todas as linhas da turma (ofertas +
    legado), exatamente como antes do serviço.
    """
    return _agregar_turma(turmas_ids, unidade_id=unidade_id)


def semanal(
    por_aluno: dict[int, list[tuple[date, str]]], semanas: list[date]
) -> dict[int, float | None]:
    buckets = [{"total": 0, "pres": 0} for _ in semanas]
    for lista in por_aluno.values():
        for data_aula, conceito in lista:
            if conceito not in CONCEITOS_CONTABEIS:
                continue
            idx = semana_de(data_aula, semanas)
            if idx is None:
                continue
            buckets[idx]["total"] += 1
            if conceito in CONCEITOS_PRESENCA:
                buckets[idx]["pres"] += 1
    return {
        i: pct(b["pres"], b["total"]) if b["total"] else None
        for i, b in enumerate(buckets)
    }
