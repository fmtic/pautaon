"""Coortes de status: alunos enturmados e renovação entre períodos."""

from __future__ import annotations

from app.models import PeriodoLetivo
from app.models.enums import StatusAluno
from app.services.aluno_status import status_alunos_para_bi

from .regras import STATUS_ENTURMADO


def status(unidade_id: int | None, periodo_letivo_id: int) -> dict[int, StatusAluno]:
    return status_alunos_para_bi(
        unidade_id=unidade_id,
        periodo_letivo_id=periodo_letivo_id,
    )


def enturmados(status_map: dict[int, StatusAluno]) -> set[int]:
    return {aid for aid, st in status_map.items() if st in STATUS_ENTURMADO}


def renovacao(
    periodo: PeriodoLetivo, unidade_id: int | None, enturmados_ids: set[int]
) -> dict | None:
    periodo_ant = (
        PeriodoLetivo.query.filter(
            PeriodoLetivo.unidade_id == periodo.unidade_id,
            PeriodoLetivo.data_inicio < periodo.data_inicio,
        )
        .order_by(PeriodoLetivo.data_inicio.desc())
        .first()
    )
    if not periodo_ant:
        return None

    status_ant = status(unidade_id, periodo_ant.id)
    coorte_ant = enturmados(status_ant)
    if not coorte_ant:
        return None

    renovados = len(coorte_ant & enturmados_ids)
    return {
        "periodo": periodo_ant.nome,
        "renovados": renovados,
        "total": len(coorte_ant),
        "pct": round(renovados / len(coorte_ant) * 100, 0),
    }