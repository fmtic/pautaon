"""Helpers puros: semanas, faixas, tendência, sequências de falta."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import PeriodoLetivo
from app.models.enums import CONCEITOS_CONTABEIS
# Alias: `percentual` é nome de parâmetro em faixa(); evitar sombreamento.
from app.services.frequencia_oferta import percentual as percentual_unica

from .regras import LIMIAR_ATENCAO, LIMIAR_CRITICO


def semanas_do_periodo(periodo: PeriodoLetivo) -> list[date]:
    if not periodo or not periodo.data_inicio or not periodo.data_fim:
        return []
    cursor = periodo.data_inicio - timedelta(days=periodo.data_inicio.weekday())
    semanas: list[date] = []
    while cursor <= periodo.data_fim:
        semanas.append(cursor)
        cursor += timedelta(days=7)
    return semanas


def semana_de(data_ref: date, semanas: list[date]) -> int | None:
    for i, seg in enumerate(semanas):
        if seg <= data_ref < seg + timedelta(days=7):
            return i
    return None


def faixa(percentual: float) -> str:
    """hi/mid/lo sobre o valor JÁ ARREDONDADO a 1 casa — ETAPA D3b.2.

    Delegado ao serviço único (fecha a brecha em que p.ex. 89,96 ficava
    fora de todas as faixas ao comparar o valor cru com >= 90).
    """
    from app.services.frequencia_oferta import faixa as _faixa

    return _faixa(percentual)


def pct(presentes: int, total: int) -> float:
    """Regra única de percentual (presentes/(presentes+faltas), 1 casa).

    `total` aqui já é o denominador contável (presentes + faltas, sem J),
    então faltas = total - presentes.
    """
    return percentual_unica(presentes, total - presentes)


def tendencia(
    semanais: dict[int, float | None], min_semanas: int = 6
) -> float | None:
    validas = [(i, v) for i, v in semanais.items() if v is not None]
    if len(validas) < min_semanas:
        return None
    ult = [v for _, v in validas[-3:]]
    ant = [v for _, v in validas[:-3]]
    return round(sum(ult) / 3 - sum(ant) / len(ant), 0)


def maior_sequencia_faltas(lista: list[tuple[date, str]]) -> int:
    maior = atual = 0
    for _, conceito in lista:
        if conceito == "F":
            atual += 1
            maior = max(maior, atual)
        elif conceito in CONCEITOS_CONTABEIS:
            atual = 0
    return maior


def faltas_atuais(lista: list[tuple[date, str]]) -> int:
    cont = 0
    for _, conceito in reversed(lista):
        if conceito == "F":
            cont += 1
        elif conceito in CONCEITOS_CONTABEIS:
            break
    return cont


def faixas_alunos(por_aluno_pct: dict[int, float]) -> dict:
    hi = mid = lo = 0
    for p in por_aluno_pct.values():
        f = faixa(p)
        if f == "hi":
            hi += 1
        elif f == "mid":
            mid += 1
        else:
            lo += 1
    return {"hi": hi, "mid": mid, "lo": lo, "total": hi + mid + lo}