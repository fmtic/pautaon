"""Serviço único da grade de horário por dia da oferta (H1-P4, H2-P2).

Camada de leitura/escrita sobre `TurmaCursoHorario` (fonte dos dias e horários
da oferta — decisão 5). Nenhuma função desta camada faz ``commit``: o chamador
(rota/escritor do H2) controla a transação.

Convenções:
    - ``dia_semana`` é ``date.weekday()``; o domínio GRAVÁVEL pela escrita é
      0–5 (segunda a sábado) — domingo (6) é recusado por ``definir_grade``
      (decisão H2), embora o CHECK do banco ainda admita 0–6 por tolerância ao
      legado lido antes do H2. A tradução com o texto dos formulários passa
      pelo conversor único ``app/utils/dias_semana.py`` (H1-P1).
    - Desde o H2 toda grade escrita pelo serviço tem AO MENOS um dia e TODO dia
      com ``hora_inicio`` e ``hora_fim`` preenchidos, ``fim > início``
      (decisão H2). Leitores (`duracao_do_dia`, `grade_uniforme`, `resumo_grade`)
      continuam tolerando linhas sem horário vindas do backfill, para não
      quebrar antes do H3.
    - ``sincronizar_projecao_horario`` é, a partir do H2, o ÚNICO ponto que
      escreve ``oferta.dias_semana``/``hora_inicio``/``hora_fim`` (projeção
      transitória removida no H5).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import time

from app import db
from app.models import TurmaCurso, TurmaCursoHorario
from app.utils.dias_semana import (
    weekday_para_abrev,
    weekday_para_nome,
    weekdays_para_csv,
)


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

    `itens` é uma lista de ``(dia_semana, hora_inicio, hora_fim)``. Regras H2
    (decisões 2–4), validadas ANTES de qualquer alteração:

    - grade não pode ser vazia (toda oferta tem ao menos um dia de aula);
    - dia em 0–5 (segunda a sábado); domingo (6) é recusado;
    - sem duplicata de dia;
    - todo dia tem hora de início E fim preenchidas;
    - ``hora_fim > hora_inicio`` (mesmo dia, sem virar meia-noite).

    Qualquer violação levanta ``ValueError`` com mensagem em português
    identificando o dia, e a grade anterior permanece intacta. Aplicar a
    MESMA grade de novo é no-op (não escreve nada).

    A substituição remove as linhas antigas e ``flush``-a antes de reinserir,
    para não violar ``uix_turma_curso_horario_dia`` no meio do flush. Por fim
    chama ``sincronizar_projecao_horario``.
    """
    if not itens:
        raise ValueError(
            "A grade não pode ficar vazia: selecione ao menos um dia de aula."
        )

    vistos: set[int] = set()
    validados: list[tuple[int, time | None, time | None]] = []

    for item in itens:
        try:
            dia, ini, fim = item
        except (TypeError, ValueError):
            raise ValueError(
                "Cada item da grade deve ser (dia_semana, hora_inicio, hora_fim)."
            )

        if not isinstance(dia, int) or dia < 0 or dia > 6:
            raise ValueError(
                f"dia_semana inválido {dia!r}: use inteiro de 0 (segunda) a "
                "5 (sábado)."
            )
        if dia == 6:
            raise ValueError(
                "Domingo não é dia de aula: use dias de segunda (0) a sábado (5)."
            )
        if dia in vistos:
            raise ValueError(f"Dia duplicado na grade: {weekday_para_nome(dia)}.")
        vistos.add(dia)

        if ini is None or fim is None:
            raise ValueError(
                f"Falta horário no dia {weekday_para_nome(dia)}: toda aula precisa "
                "de hora de início e de término."
            )
        if fim <= ini:
            raise ValueError(
                f"Horário inválido no dia {weekday_para_nome(dia)}: hora_fim "
                f"({fim:%H:%M}) deve ser maior que hora_inicio ({ini:%H:%M})."
            )

        validados.append((dia, ini, fim))

    validados.sort(key=lambda t: t[0])
    atuais = [
        (l.dia_semana, l.hora_inicio, l.hora_fim)
        for l in grade_da_oferta(oferta)
    ]
    if atuais == validados:
        # Idempotência: mesma grade não toca no banco nem na projeção.
        return

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
