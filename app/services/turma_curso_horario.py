"""Serviço único da grade de horário por dia da oferta (H1-P4).

Camada de leitura/escrita sobre `TurmaCursoHorario` (fonte dos dias e horários
da oferta — decisão 5). Nenhuma função desta camada faz ``commit``: o chamador
(rota/escritor do H2) controla a transação.

Convenções:
    - ``dia_semana`` é sempre ``date.weekday()`` (0 = segunda … 6 = domingo);
      a tradução com o texto dos formulários passa pelo conversor único
      ``app/utils/dias_semana.py`` (H1-P1).
    - A grade pode ter dias sem horário (par ``hora_inicio``/``hora_fim`` ambos
      NULL). Só um extremo preenchido é inválido (decisão 2), assim como
      ``hora_fim <= hora_inicio`` — ``definir_grade`` recusa ambos.
    - ``sincronizar_projecao_horario`` é, a partir do H2, o ÚNICO ponto que
      escreve ``oferta.dias_semana``/``hora_inicio``/``hora_fim`` (projeção
      transitória removida no H5).

Nada aqui altera os escritores/leitores atuais; é somente a base que o H2 usa.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import time

from app import db
from app.models import TurmaCurso, TurmaCursoHorario
from app.utils.dias_semana import weekday_para_abrev, weekdays_para_csv


@dataclass(frozen=True)
class Linha:
    """Uma linha da grade: dia (0-6) e o par de horários (opcional)."""

    dia_semana: int
    hora_inicio: time | None
    hora_fim: time | None


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def grade_da_oferta(oferta: TurmaCurso) -> list[Linha]:
    """Grade da oferta como lista ordenada de ``Linha`` (por dia 0-6).

    Usa o relacionamento ``horarios`` (lazy ``selectin``); sem grade → lista
    vazia.
    """
    return [
        Linha(l.dia_semana, l.hora_inicio, l.hora_fim)
        for l in sorted(
            oferta.horarios,
            key=lambda l: l.dia_semana,
        )
    ]


def grades_em_lote(oferta_ids: list[int] | tuple[int, ...]) -> dict[int, list[Linha]]:
    """Grade de várias ofertas em UMA consulta (sem N+1).

    Toda oferta pedida aparece no resultado; as sem linhas recebem lista vazia.
    """
    ids = list(oferta_ids)
    resultado: dict[int, list[Linha]] = {oid: [] for oid in ids}
    if not ids:
        return resultado

    linhas = (
        db.session.query(TurmaCursoHorario)
        .filter(TurmaCursoHorario.turma_curso_id.in_(ids))
        .order_by(TurmaCursoHorario.turma_curso_id, TurmaCursoHorario.dia_semana)
        .all()
    )
    for l in linhas:
        resultado.setdefault(l.turma_curso_id, []).append(
            Linha(l.dia_semana, l.hora_inicio, l.hora_fim)
        )
    return resultado


def duracao_do_dia(oferta: TurmaCurso, dia: int) -> int | None:
    """Duração em MINUTOS do `dia`; ``None`` se o dia não existe na grade ou
    existe mas está sem horário."""
    for linha in grade_da_oferta(oferta):
        if linha.dia_semana == dia:
            if linha.hora_inicio is None or linha.hora_fim is None:
                return None
            return (
                linha.hora_fim.hour * 60 + linha.hora_fim.minute
                - linha.hora_inicio.hour * 60 - linha.hora_inicio.minute
            )
    return None


def grade_uniforme(oferta: TurmaCurso) -> bool:
    """``True`` se todos os dias compartilham o MESMO par de horários.

    Casos uniformes: grade vazia; todos os dias sem horário. Não uniforme:
    dias com horário misturados a dias sem horário, ou pares diferentes entre
    os dias.
    """
    pares = {(l.hora_inicio, l.hora_fim) for l in grade_da_oferta(oferta)}
    return len(pares) <= 1


def _formatar_hora(valor: time | None) -> str:
    return f"{valor:%H:%M}" if valor is not None else ""


def resumo_grade(oferta: TurmaCurso) -> str:
    """Resumo legível da grade.

    - Vazia → ``""``.
    - Sem horário em nenhum dia → só os dias: ``"Seg, Qua"``.
    - Uniforme com horário → dias + um par: ``"Seg, Qua · 13:30-16:30"``.
    - Não uniforme → um segmento por dia: ``"Seg 13:30-16:30 · Ter 13:00-15:00"``
      (dia sem horário aparece apenas com a abreviação).
    """
    grade = grade_da_oferta(oferta)
    if not grade:
        return ""

    dias = [l.dia_semana for l in grade]
    pares = {(l.hora_inicio, l.hora_fim) for l in grade}

    # Nenhum dia tem horário -> só os dias.
    if pares == {(None, None)}:
        return ", ".join(weekday_para_abrev(d) for d in dias)

    # Uniforme com horário -> dias + par único.
    if len(pares) == 1:
        ini, fim = next(iter(pares))
        dias_csv = ", ".join(weekday_para_abrev(d) for d in dias)
        if ini is None:  # (não uniforme jamais cai aqui) sem horário
            return dias_csv
        return f"{dias_csv} · {_formatar_hora(ini)}-{_formatar_hora(fim)}"

    # Não uniforme -> um segmento por dia.
    segmentos: list[str] = []
    for l in grade:
        abrev = weekday_para_abrev(l.dia_semana)
        if l.hora_inicio is None or l.hora_fim is None:
            segmentos.append(abrev)
        else:
            segmentos.append(
                f"{abrev} {_formatar_hora(l.hora_inicio)}-{_formatar_hora(l.hora_fim)}"
            )
    return " · ".join(segmentos)


# ---------------------------------------------------------------------------
# Projeção (único ponto que escreve as três colunas escalares da oferta)
# ---------------------------------------------------------------------------

def sincronizar_projecao_horario(oferta: TurmaCurso) -> None:
    """Regrava a PROJEÇÃO transitória da oferta a partir da grade.

    - ``oferta.dias_semana`` ← CSV canônico dos dias (NULL se grade vazia).
    - ``oferta.hora_inicio``/``hora_fim`` ← o par único APENAS se a grade é
      uniforme COM horário; nos demais casos ficam NULL (não há um par único
      que represente a oferta).

    Não faz commit. Este é, a partir do H2, o ÚNICO ponto que escreve essas
    três colunas (as colunas são removidas no H5).
    """
    grade = grade_da_oferta(oferta)
    oferta.dias_semana = weekdays_para_csv([l.dia_semana for l in grade])

    pares = {(l.hora_inicio, l.hora_fim) for l in grade}
    if len(pares) == 1:
        ini, fim = next(iter(pares))
    else:
        ini = fim = None  # não uniforme -> sem par projetado

    # Só projeta horário quando é uniforme E existe par completo.
    if ini is not None and fim is not None:
        oferta.hora_inicio = ini
        oferta.hora_fim = fim
    else:
        oferta.hora_inicio = None
        oferta.hora_fim = None


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

def definir_grade(oferta: TurmaCurso, itens: list[tuple[int, time | None, time | None]]) -> None:
    """Substitui a grade inteira da oferta por `itens` (átomo, sem commit).

    `itens` é uma lista de ``(dia_semana, hora_inicio|None, hora_fim|None)``.
    Valida antes de tocar na coleção: dia em 0-6, sem duplicata de dia, par
    completo (ambos NULL ou ambos preenchidos) e ``hora_fim > hora_inicio``
    quando preenchido. Em qualquer erro levanta ``ValueError`` em português e
    NÃO altera a grade anterior.

    A substituição é feita removendo as linhas antigas e ``flush``-ando antes
    de reinserir, para não violar ``uix_turma_curso_horario_dia`` no meio do
    flush. Por fim chama ``sincronizar_projecao_horario``.
    """
    vistos: set[int] = set()
    validados: list[tuple[int, time | None, time | None]] = []

    for idx, item in enumerate(itens):
        try:
            dia, ini, fim = item
        except (TypeError, ValueError):
            raise ValueError(
                "Cada item da grade deve ser (dia_semana, hora_inicio, hora_fim)."
            )

        if not isinstance(dia, int) or dia < 0 or dia > 6:
            raise ValueError(
                f"dia_semana inválido {dia!r}: use inteiro de 0 (segunda) a "
                "6 (domingo)."
            )
        if dia in vistos:
            raise ValueError(f"dia_semana duplicado na grade: {dia}.")
        vistos.add(dia)

        if (ini is None) != (fim is None):
            raise ValueError(
                f"Par de horários incompleto no dia {dia}: preencha início e "
                "fim juntos, ou deixe ambos vazios (dia sem horário)."
            )
        if ini is not None and fim is not None and fim <= ini:
            raise ValueError(
                f"Horário inválido no dia {dia}: hora_fim ({fim:%H:%M}) deve "
                f"ser maior que hora_inicio ({ini:%H:%M})."
            )

        validados.append((dia, ini, fim))

    # Remove as linhas antigas e consolida o DELETE antes de reinserir (evita
    # colisão com a UNIQUE (turma_curso_id, dia_semana) no mesmo flush).
    for linha in list(oferta.horarios):
        db.session.delete(linha)
    db.session.flush()

    oferta.horarios = [
        TurmaCursoHorario(
            turma_curso_id=oferta.id,
            dia_semana=dia,
            hora_inicio=ini,
            hora_fim=fim,
        )
        for dia, ini, fim in validados
    ]
    db.session.flush()

    sincronizar_projecao_horario(oferta)
