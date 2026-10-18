"""Constantes e dataclasses de regra do painel pedagógico.

Todos os limiares ficam centralizados aqui para facilitar ajuste.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models.enums import StatusAluno


# --- Limiares -------------------------------------------------------------
LIMIAR_CRITICO = 75.0
LIMIAR_ATENCAO = 90.0
QUEDA_SEMANAL_PP = 8.0
FALTAS_SEGUIDAS_SINAL = 2
MIN_TURMAS_QUEDA_COMUM = 5


STATUS_ENTURMADO = frozenset({
    StatusAluno.NOVO,
    StatusAluno.RENOVADO,
    StatusAluno.RETORNANTE,
})


# --- Contextos de sinais --------------------------------------------------
@dataclass(frozen=True)
class ContextoSinaisPeriodo:
    turmas_abaixo_75: int = 0
    semanas_queda_comum: frozenset[int] = frozenset()
    semanas: tuple[date, ...] = ()
    queda_por_semana: dict[int, int] = field(default_factory=dict)
    alunos_risco_noite: int = 0
    alunos_noite_total: int = 0
    conselho_pendentes: int = 0


@dataclass(frozen=True)
class ContextoSinaisTurma:
    faixas: dict = field(default_factory=dict)
    pct_turma: float = 0.0
    semanais: dict[int, float | None] = field(default_factory=dict)
    semanas: tuple[date, ...] = ()
    faltas_atuais: int = 0
    conselho_pendentes: int = 0