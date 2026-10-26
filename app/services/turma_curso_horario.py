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

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app import db
from app.models import Turma, TurmaCurso, TurmaCursoHorario
from app.utils.dias_semana import (
    csv_para_weekdays,
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


@dataclass(frozen=True)
class CargaOferta:
    """C.H. de UMA oferta: aula/total em minutos, menor aula e a grade por dia.

    ``carga_horaria_aula`` é ``None`` quando a grade não é uniforme;
    ``carga_horaria_total`` soma a duração da grade em cada ocorrência válida;
    ``min_ch_aula`` é a menor duração semanal; ``por_dia``/``intervalos``
    guardam o par de horários por weekday para a união da turma.
    """

    carga_horaria_aula: int | None
    carga_horaria_total: int | None
    min_ch_aula: int | None
    por_dia: dict[int, int | None]
    intervalos: dict[int, tuple[time, time] | None]


@dataclass(frozen=True)
class CargaTurma:
    """C.H. de UMA turma: aula/total em minutos, menor aula e nº de ofertas.

    ``carga_horaria_aula``/``min_ch_aula`` vêm da oferta principal;
    ``carga_horaria_total`` é o tempo físico da turma (união dos intervalos das
    ofertas ativas por data) — o MESMO valor exibido na listagem e usado pelo
    filtro ``min_ch_total``; ``ofertas_ativas`` conta só as ativas.
    """

    carga_horaria_aula: int | None
    carga_horaria_total: int | None
    min_ch_aula: int | None
    ofertas_ativas: int


logger = logging.getLogger(__name__)


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


def dias_da_oferta(oferta_id: int) -> set[int]:
    """Dias (weekday 0-5) agendados para a oferta, em UMA consulta.

    Fonte canônica dos dias da oferta é a grade ``turma_curso_horario``
    (decisão 5/H2). Reaproveita ``grades_em_lote`` (uma consulta por lote).
    """
    return {l.dia_semana for l in grades_em_lote([oferta_id]).get(oferta_id, [])}


def dias_por_ofertas(
    ids: list[int] | tuple[int, ...],
) -> dict[int, set[int]]:
    """Dias de várias ofertas em UMA consulta (sem N+1).

    Toda oferta pedida aparece no resultado; as sem grade recebem set vazio.
    """
    grades = grades_em_lote(list(ids))
    return {oid: {l.dia_semana for l in linhas} for oid, linhas in grades.items()}


def dias_da_turma(turma_id: int) -> set[int]:
    """União dos dias das ofertas ATIVAS da turma, em UMA consulta.

    Decisão H3a: a Turma passa a DERIVAR seus dias da grade das ofertas ativas,
    sem ler ``Turma.dias_semana``. Retorna set vazio quando a turma não tem
    nenhuma oferta com grade — o chamador decide o fallback legado.
    """
    linhas = (
        db.session.query(TurmaCursoHorario.dia_semana)
        .join(TurmaCurso, TurmaCurso.id == TurmaCursoHorario.turma_curso_id)
        .filter(TurmaCurso.turma_id == turma_id, TurmaCurso.ativo == True)  # noqa: E712
        .distinct()
        .all()
    )
    return {d for (d,) in linhas}


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


def _duracao(inicio: time | None, fim: time | None) -> int | None:
    if inicio is None or fim is None:
        return None
    minutos = (fim.hour * 60 + fim.minute) - (inicio.hour * 60 + inicio.minute)
    return minutos if minutos > 0 else None


def duracao_escalar_oferta(oferta: TurmaCurso) -> int | None:
    """Compatibilidade para oferta legada que ainda não possui linhas de grade."""
    inicio, fim = oferta.hora_inicio, oferta.hora_fim
    if oferta.turma is not None:
        inicio = inicio or oferta.turma.hora_inicio
        fim = fim or oferta.turma.hora_fim
    return _duracao(inicio, fim)


def carga_horaria_total_oferta(
    oferta: TurmaCurso,
    datas_esperadas: list[date],
    grade: list[Linha] | None = None,
) -> int | None:
    """Soma as durações das ocorrências esperadas da oferta.

    ``datas_esperadas`` deve vir resolvida pelo leitor de agenda (com vigência
    e bloqueios aplicados). Sem grade, mantém o cálculo escalar legado.
    """
    linhas = grade_da_oferta(oferta) if grade is None else grade
    if not linhas:
        logger.warning(
            "Oferta %s sem grade: C.H. total usa duração escalar legada.",
            oferta.id,
        )
        duracao = duracao_escalar_oferta(oferta)
        return duracao * len(datas_esperadas) if duracao and datas_esperadas else None

    por_dia = {
        linha.dia_semana: _duracao(linha.hora_inicio, linha.hora_fim)
        for linha in linhas
    }
    valores = [por_dia.get(data.weekday()) for data in datas_esperadas]
    total = sum(valor for valor in valores if valor is not None)
    return total or None


def _bloqueios_em_lote(turmas: list[Turma]) -> dict[int, set[str]]:
    """Lê bloqueios do período e exceções das turmas em no máximo 2 consultas."""
    from app.models import DiaBloqueado, DiaBloqueadoTurma

    turma_ids = [t.id for t in turmas if t.id is not None]
    periodo_por_turma = {t.id: t.periodo_letivo_id for t in turmas if t.id is not None}
    periodo_ids = {pid for pid in periodo_por_turma.values() if pid is not None}
    bloqueios_periodo: dict[int, set[str]] = defaultdict(set)
    excecoes: dict[int, set[str]] = defaultdict(set)

    if periodo_ids:
        for periodo_id, data in db.session.execute(
            select(DiaBloqueado.periodo_letivo_id, DiaBloqueado.data).where(
                DiaBloqueado.periodo_letivo_id.in_(periodo_ids)
            )
        ):
            bloqueios_periodo[periodo_id].add(data.strftime("%Y-%m-%d"))

    if turma_ids:
        for turma_id, data in db.session.execute(
            select(DiaBloqueadoTurma.turma_id, DiaBloqueadoTurma.data).where(
                DiaBloqueadoTurma.turma_id.in_(turma_ids)
            )
        ):
            excecoes[turma_id].add(data.strftime("%Y-%m-%d"))

    return {
        turma_id: bloqueios_periodo.get(periodo_id, set()) - excecoes.get(turma_id, set())
        for turma_id, periodo_id in periodo_por_turma.items()
    }


def oferta_principal_da_turma(ofertas: list[TurmaCurso]) -> TurmaCurso | None:
    """Mesmo critério da lista: marcada principal; senão, menor id ativo."""
    ativas = sorted((o for o in ofertas if o.ativo), key=lambda o: o.id)
    return next((o for o in ativas if o.principal), ativas[0] if ativas else None)


def _duracao_turma_escalar(turma: Turma) -> int | None:
    return _duracao(turma.hora_inicio, turma.hora_fim)


def _intervalos_unidos_minutos(intervalos: list[tuple[int, int]]) -> int:
    total = 0
    fim_atual: int | None = None
    for inicio, fim in sorted(intervalos):
        if fim_atual is None or inicio >= fim_atual:
            total += fim - inicio
        elif fim > fim_atual:
            total += fim - fim_atual
        fim_atual = max(fim_atual or fim, fim)
    return total


def cargas_horarias_ofertas_em_lote(
    ofertas: list[TurmaCurso],
    bloqueios: dict[int, set[str]] | None = None,
) -> dict[int, CargaOferta]:
    """Calcula C.H. por oferta com uma leitura em lote da grade e dos bloqueios."""
    from app.services.turma_curso import datas_esperadas_oferta

    if not ofertas:
        return {}
    ids = [oferta.id for oferta in ofertas]
    grades = grades_em_lote(ids)
    turmas = list({oferta.turma.id: oferta.turma for oferta in ofertas
                   if oferta.turma is not None}.values())
    bloqueados = bloqueios if bloqueios is not None else _bloqueios_em_lote(turmas)
    resultado: dict[int, CargaOferta] = {}

    for oferta in ofertas:
        linhas = grades.get(oferta.id, [])
        if linhas:
            por_dia = {
                linha.dia_semana: _duracao(linha.hora_inicio, linha.hora_fim)
                for linha in linhas
            }
            intervalos = {
                linha.dia_semana: (linha.hora_inicio, linha.hora_fim)
                if linha.hora_inicio is not None and linha.hora_fim is not None
                else None
                for linha in linhas
            }
            pares = {(linha.hora_inicio, linha.hora_fim) for linha in linhas}
            uniforme = len(pares) <= 1
            aula = next(iter(por_dia.values())) if uniforme and por_dia else None
            duracoes = [valor for valor in por_dia.values() if valor is not None]
            menor = min(duracoes) if duracoes else None
        else:
            logger.warning(
                "Oferta %s sem grade: C.H. em lote usa horários escalares legados.",
                oferta.id,
            )
            from app.services.turma_curso import _dias_efetivos_da_oferta

            dias = csv_para_weekdays(_dias_efetivos_da_oferta(oferta))
            aula = duracao_escalar_oferta(oferta)
            por_dia = {dia: aula for dia in dias}
            inicio, fim = oferta.hora_inicio, oferta.hora_fim
            if oferta.turma is not None:
                inicio = inicio or oferta.turma.hora_inicio
                fim = fim or oferta.turma.hora_fim
            intervalos = {dia: (inicio, fim) if inicio and fim else None for dia in dias}
            menor = aula

        turma = oferta.turma
        datas = datas_esperadas_oferta(
            oferta,
            None,
            blocked=bloqueados.get(turma.id, set()) if turma is not None else set(),
        )
        total = carga_horaria_total_oferta(oferta, datas, grade=linhas)
        resultado[oferta.id] = CargaOferta(aula, total, menor, por_dia, intervalos)
    return resultado


def carga_horaria_total_turma(turma: Turma) -> int | None:
    """Tempo físico total da turma: união dos intervalos por data de aula."""
    return cargas_horarias_turmas_em_lote([turma]).get(
        turma.id, CargaTurma(None, None, None, 0)
    ).carga_horaria_total


def cargas_horarias_turmas_em_lote(turmas: list[Turma]) -> dict[int, CargaTurma]:
    """C.H. aula/total e menor aula por turma, sem consultas por oferta/turma."""
    if not turmas:
        return {}

    from app.models import DiaBloqueado, DiaBloqueadoTurma
    from app.services.turma_curso import datas_esperadas_oferta
    from app.utils.dias_semana import csv_para_weekdays

    turma_ids = [turma.id for turma in turmas if turma.id is not None]
    ofertas = db.session.execute(
        select(TurmaCurso)
        .options(selectinload(TurmaCurso.horarios))
        .where(TurmaCurso.turma_id.in_(turma_ids), TurmaCurso.ativo.is_(True))
        .order_by(TurmaCurso.id)
    ).scalars().all() if turma_ids else []
    por_turma: dict[int, list[TurmaCurso]] = defaultdict(list)
    for oferta in ofertas:
        por_turma[oferta.turma_id].append(oferta)

    periodo_ids = {turma.periodo_letivo_id for turma in turmas if turma.periodo_letivo_id}
    bloqueios_periodo: dict[int, set[str]] = defaultdict(set)
    excecoes: dict[int, set[str]] = defaultdict(set)
    if periodo_ids:
        for periodo_id, data in db.session.execute(
            select(DiaBloqueado.periodo_letivo_id, DiaBloqueado.data).where(
                DiaBloqueado.periodo_letivo_id.in_(periodo_ids)
            )
        ):
            bloqueios_periodo[periodo_id].add(data.strftime("%Y-%m-%d"))
    if turma_ids:
        for turma_id, data in db.session.execute(
            select(DiaBloqueadoTurma.turma_id, DiaBloqueadoTurma.data).where(
                DiaBloqueadoTurma.turma_id.in_(turma_ids)
            )
        ):
            excecoes[turma_id].add(data.strftime("%Y-%m-%d"))

    oferta_cargas = cargas_horarias_ofertas_em_lote(ofertas, {
        turma.id: bloqueios_periodo.get(turma.periodo_letivo_id, set())
        - excecoes.get(turma.id, set())
        for turma in turmas if turma.id is not None
    })
    resultado: dict[int, CargaTurma] = {}

    for turma in turmas:
        ativas = por_turma.get(turma.id, [])
        principal = oferta_principal_da_turma(ativas)
        principal_carga = oferta_cargas.get(principal.id) if principal else None
        aula = principal_carga.carga_horaria_aula if principal_carga else _duracao_turma_escalar(turma)
        menor = principal_carga.min_ch_aula if principal_carga else _duracao_turma_escalar(turma)

        if not ativas:
            logger.warning(
                "Turma %s sem oferta ativa/grade: C.H. usa escalares legados.", turma.id,
            )
            duracao = _duracao_turma_escalar(turma)
            if duracao and turma.data_inicio and turma.data_fim:
                bloqueadas = bloqueios_periodo.get(turma.periodo_letivo_id, set()) - excecoes.get(turma.id, set())
                weekdays = set(csv_para_weekdays(turma.dias_semana))
                ocorrencias = 0
                atual = turma.data_inicio
                while atual <= turma.data_fim:
                    if atual.weekday() in weekdays and atual.strftime("%Y-%m-%d") not in bloqueadas:
                        ocorrencias += 1
                    atual += date.resolution
                total = duracao * ocorrencias if ocorrencias else None
            else:
                total = None
        else:
            intervalos_por_data: dict[date, list[tuple[int, int]]] = defaultdict(list)
            for oferta in ativas:
                carga = oferta_cargas.get(oferta.id)
                if carga is None:
                    continue
                bloqueadas = bloqueios_periodo.get(turma.periodo_letivo_id, set()) - excecoes.get(turma.id, set())
                datas = datas_esperadas_oferta(oferta, None, blocked=bloqueadas)
                for data in datas:
                    intervalo = carga.intervalos.get(data.weekday())
                    if intervalo and intervalo[0] is not None and intervalo[1] is not None:
                        inicio = intervalo[0].hour * 60 + intervalo[0].minute
                        fim = intervalo[1].hour * 60 + intervalo[1].minute
                        if fim > inicio:
                            intervalos_por_data[data].append((inicio, fim))
            total_minutos = sum(_intervalos_unidos_minutos(items) for items in intervalos_por_data.values())
            total = total_minutos or None

        resultado[turma.id] = CargaTurma(
            aula,
            total,
            menor,
            len(ativas),
        )
    return resultado


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

def grade_a_partir_do_legado(
    dias_semana: str | None,
    hora_inicio: time | None,
    hora_fim: time | None,
) -> list[tuple[int, time, time]] | None:
    """Converte colunas escalares (CSV de dias + par único) em grade uniforme.

    É a ponte dos escritores legados para ``definir_grade`` (H2): resolve o
    CSV pelo conversor único, descarta domingo (fora do domínio 0–5 do H2) e
    monta um par por dia. Devolve ``None`` quando a agenda legada está
    INCOMPLETA (sem dias utilizáveis, sem hora, ou ``fim <= início``) — o
    chamador deve recusar e pedir agenda completa, nunca gravar grade parcial.
    """
    dias = [d for d in csv_para_weekdays(dias_semana) if d <= 5]
    if not dias or hora_inicio is None or hora_fim is None or hora_fim <= hora_inicio:
        return None
    return [(d, hora_inicio, hora_fim) for d in sorted(set(dias))]


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
