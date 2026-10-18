"""Agregação de frequência (1 consulta) e quebra semanal."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from app import db
from app.models import Frequencia
from app.models.enums import CONCEITOS_CONTABEIS, CONCEITOS_PRESENCA

from .helpers import pct, semana_de


@dataclass
class FrequenciaTurma:
    por_aluno: dict[int, list[tuple[date, str]]] = field(default_factory=dict)
    por_aluno_pct: dict[int, float] = field(default_factory=dict)
    total: int = 0
    presentes: int = 0
    pct_turma: float = 0.0


def agregar_por_turma(
    turmas_ids: Iterable[int],
) -> dict[int, FrequenciaTurma]:
    turmas_ids = list(turmas_ids)
    if not turmas_ids:
        return {}

    rows = (
        db.session.query(
            Frequencia.turma_id,
            Frequencia.aluno_id,
            Frequencia.data,
            Frequencia.conceito,
        )
        .filter(Frequencia.turma_id.in_(turmas_ids))
        .order_by(Frequencia.turma_id, Frequencia.aluno_id, Frequencia.data)
        .all()
    )

    bruto: dict[int, dict] = defaultdict(
        lambda: {"por_aluno": defaultdict(list), "total": 0, "presentes": 0}
    )
    for turma_id, aluno_id, data_aula, conceito in rows:
        bruto[turma_id]["por_aluno"][aluno_id].append((data_aula, conceito))
        if conceito in CONCEITOS_CONTABEIS:
            bruto[turma_id]["total"] += 1
            if conceito in CONCEITOS_PRESENCA:
                bruto[turma_id]["presentes"] += 1

    resultado: dict[int, FrequenciaTurma] = {}
    for turma_id, info in bruto.items():
        pct_por_aluno: dict[int, float] = {}
        for aluno_id, lista in info["por_aluno"].items():
            contabeis = [c for _, c in lista if c in CONCEITOS_CONTABEIS]
            if contabeis:
                pres = sum(1 for c in contabeis if c in CONCEITOS_PRESENCA)
                pct_por_aluno[aluno_id] = pct(pres, len(contabeis))
        resultado[turma_id] = FrequenciaTurma(
            por_aluno={aid: list(l) for aid, l in info["por_aluno"].items()},
            por_aluno_pct=pct_por_aluno,
            total=info["total"],
            presentes=info["presentes"],
            pct_turma=pct(info["presentes"], info["total"]),
        )
    return resultado


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