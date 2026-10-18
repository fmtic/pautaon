"""Montagem da visão 360° de UM aluno.

Espelha o padrão do painel de período (`montagem_periodo.montar`):
    - `_Acumulado`: dataclass com totais da turma.
    - `_identidade`: bloco de identificação/status.
    - `_frequencia`: mapa aula-a-aula + curva + KPIs.
    - `_conselho`: etapas, respostas por etapa e diff entre etapas.
    - `_timeline`: eventos ordenados por data.
    - `_percurso`: turmas anteriores do aluno.
    - `_sinais`: regras prontas (mesmo formato do painel).

Todo campo `*_str`/`*_meta`/`*_classe` sai formatado; o template não calcula.
Acesso a perfis (endereço/socioeconômico) SEMPRE via
`app.services.aluno_perfil` — nunca em `aluno.*_json`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    Aluno,
    Atendimento,
    ConselhoClasse,
    ConselhoResposta,
    Frequencia,
    Inscricao,
    PerguntaConselho,
    PeriodoConselho,
    PeriodoLetivo,
    Turma,
)
from app.models.enums import (
    ConceitoFrequencia,
    EtapaConselho,
    StatusAluno,
)
from app.services import aluno_perfil

from .formatacao import (
    classe_tendencia,
    faixa_meta,
    fmt_diff,
    fmt_pct,
)
from .helpers import faixa, pct, semanas_do_periodo
from .regras import LIMIAR_CRITICO


# =============================================================================
# Contexto e acumuladores
# =============================================================================
@dataclass
class _Acumulado:
    presencas: int = 0
    faltas: int = 0
    justificadas: int = 0

    @property
    def total_contabil(self) -> int:
        return self.presencas + self.faltas

    @property
    def pct(self) -> float:
        return pct(self.presencas, self.total_contabil)


def _identidade(aluno: Aluno, turma: Turma | None, inscricao: Inscricao | None) -> dict:
    status = (inscricao.status_aluno if inscricao else None) or StatusAluno.NOVO
    idade = aluno.idade
    return {
        "id": aluno.id,
        "nome": aluno.nome_social or aluno.nome,
        "iniciais": "".join(
            p[0] for p in (aluno.nome_social or aluno.nome).split()[:2]
        ).upper(),
        "matricula": aluno.matricula,
        "idade": idade,
        "menor_idade": idade is not None and idade < 18,
        "status": status,
        "status_label": _rotulo_status(status),
        "status_classe": _classe_status(status),
        "turma": turma,
        "professor": turma.professor if turma and turma.professor else None,
        "dias_horario": _dias_horario(turma) if turma else "—",
    }


def _rotulo_status(s: StatusAluno) -> str:
    return {
        StatusAluno.NOVO: "Novo",
        StatusAluno.RENOVADO: "Renovado",
        StatusAluno.RETORNANTE: "Retornante",
        StatusAluno.EM_JANELA: "Em janela",
        StatusAluno.NAO_RENOVADO: "Não renovado",
        StatusAluno.DESENTURMADO: "Desenturmado",
        StatusAluno.OUTROS: "Outros",
    }.get(s, "—")


def _classe_status(s: StatusAluno) -> str:
    return {
        StatusAluno.NOVO: "primary",
        StatusAluno.RENOVADO: "success",
        StatusAluno.RETORNANTE: "info",
        StatusAluno.EM_JANELA: "warning",
        StatusAluno.NAO_RENOVADO: "danger",
        StatusAluno.DESENTURMADO: "danger",
        StatusAluno.OUTROS: "secondary",
    }.get(s, "secondary")


def _dias_horario(turma: Turma) -> str:
    if not turma.dias_semana:
        return "—"
    h = ""
    if turma.hora_inicio and turma.hora_fim:
        h = f" · {turma.hora_inicio.strftime('%H:%M')}–{turma.hora_fim.strftime('%H:%M')}"
    return f"{turma.dias_semana}{h}"


# =============================================================================
# Frequência
# =============================================================================
def _frequencia(aluno_id: int, turma: Turma, semanas: list) -> dict:
    rows = (
        Frequencia.query.filter_by(aluno_id=aluno_id, turma_id=turma.id)
        .order_by(Frequencia.data)
        .all()
    )

    acum = _Acumulado()
    por_data: dict[date, ConceitoFrequencia] = {}
    serie_aluno: list[float] = []
    serie_turma: list[float] = []
    pres_acum = 0
    falt_acum = 0
    labels: list[str] = []

    # Agregado da turma por data (uma única query)
    turma_data = dict(
        db.session.query(Frequencia.data, func.count(Frequencia.id))
        .filter(
            Frequencia.turma_id == turma.id,
            Frequencia.conceito.in_(
                [
                    ConceitoFrequencia.A,
                    ConceitoFrequencia.B,
                    ConceitoFrequencia.C,
                    ConceitoFrequencia.D,
                ]
            ),
        )
        .group_by(Frequencia.data)
        .all()
    )
    turma_total = dict(
        db.session.query(Frequencia.data, func.count(Frequencia.id))
        .filter(
            Frequencia.turma_id == turma.id,
            Frequencia.conceito.in_(
                [
                    ConceitoFrequencia.A,
                    ConceitoFrequencia.B,
                    ConceitoFrequencia.C,
                    ConceitoFrequencia.D,
                    ConceitoFrequencia.F,
                ]
            ),
        )
        .group_by(Frequencia.data)
        .all()
    )

    # Série semanal acumulada (aluno) e (turma)
    por_semana_aluno: dict[date, list] = defaultdict(lambda: [0, 0])
    por_semana_turma: dict[date, list] = defaultdict(lambda: [0, 0])

    for f in rows:
        por_data[f.data] = f.conceito
        if f.conceito in (
            ConceitoFrequencia.A,
            ConceitoFrequencia.B,
            ConceitoFrequencia.C,
            ConceitoFrequencia.D,
        ):
            acum.presencas += 1
            pres_acum += 1
        elif f.conceito == ConceitoFrequencia.F:
            acum.faltas += 1
            falt_acum += 1
        elif f.conceito == ConceitoFrequencia.J:
            acum.justificadas += 1
            continue

        seg = _segunda_da(f.data)
        por_semana_aluno[seg][0] += pres_acum
        por_semana_aluno[seg][1] += pres_acum + falt_acum

    # Conta turma por semana (uma passada)
    for d, n_pres in turma_data.items():
        seg = _segunda_da(d)
        por_semana_turma[seg][0] += n_pres
    for d, n in turma_total.items():
        seg = _segunda_da(d)
        por_semana_turma[seg][1] += n

    for seg in semanas:
        labels.append(seg.strftime("%d/%m"))
        p, t = por_semana_aluno.get(seg, (0, 0))
        serie_aluno.append(round(p / t * 100, 1) if t else 0.0)
        p, t = por_semana_turma.get(seg, (0, 0))
        serie_turma.append(round(p / t * 100, 1) if t else 0.0)

    # Maior sequência de faltas
    maior_seq = _maior_sequencia_faltas(rows)

    pct_aluno = acum.pct
    pct_turma = serie_turma[-1] if serie_turma else 0.0

    # Substitua o "return" final por:
    return {
        "por_data": por_data,
        "conceitos_turma": turma_data,
        "acumulado": acum,
        "pct": pct_aluno,
        "pct_str": fmt_pct(pct_aluno),
        "faixa": faixa(pct_aluno),
        "faixa_meta": faixa_meta(faixa(pct_aluno)),
        "pct_turma": pct_turma,
        "pct_turma_str": fmt_pct(pct_turma),
        "diff_turma": round(pct_aluno - pct_turma, 1),
        "diff_turma_str": fmt_diff(pct_aluno - pct_turma),
        "diff_turma_classe": (
            "danger"
            if (pct_aluno - pct_turma) <= -5
            else ("success" if (pct_aluno - pct_turma) >= 5 else "secondary")
        ),
        "maior_seq_faltas": maior_seq,
        "labels": labels,
        "serie_aluno": serie_aluno,
        "serie_turma": serie_turma,
        # Adição da lista `mapa` com o `dia_semana` para o template separar em linhas:
        "mapa": [
            {"data": d, "conceito": (c.value if c else None), "dia_semana": d.weekday()}
            for d, c in sorted(por_data.items())
        ],
    }


def _segunda_da(d: date) -> date:
    return date(d.year, d.month, d.day) - __import__("datetime").timedelta(
        days=d.weekday()
    )


def _maior_sequencia_faltas(rows: list) -> int:
    maior = atual = 0
    for f in rows:
        if f.conceito == ConceitoFrequencia.F:
            atual += 1
            maior = max(maior, atual)
        elif f.conceito == ConceitoFrequencia.J:
            continue  # J não quebra a sequência (regra do protótipo)
        else:
            atual = 0
    return maior


# =============================================================================
# Conselho
# =============================================================================
def _conselho(aluno_id: int, turma: Turma, periodo: PeriodoLetivo | None) -> dict:
    conselhos = (
        ConselhoClasse.query.options(joinedload(ConselhoClasse.respostas))
        .filter_by(aluno_id=aluno_id, turma_id=turma.id)
        .order_by(ConselhoClasse.etapa)
        .all()
    )
    por_etapa = {c.etapa: c for c in conselhos}

    respostas: dict[EtapaConselho, dict[int, dict]] = defaultdict(dict)
    ids_pergunta = set()
    for c in conselhos:
        for r in c.respostas:
            respostas[c.etapa][r.pergunta_id] = {
                "resposta": r.resposta,
                "observacao": r.observacao,
            }
            ids_pergunta.add(r.pergunta_id)

    perguntas = (
        PerguntaConselho.query.filter(PerguntaConselho.id.in_(ids_pergunta))
        .order_by(PerguntaConselho.id)
        .all()
        if ids_pergunta
        else []
    )

    etapas_ordenadas = [
        EtapaConselho.INICIAL,
        EtapaConselho.PERCURSO,
        EtapaConselho.FINAL,
    ]
    etapas_view = []
    for e in etapas_ordenadas:
        c = por_etapa.get(e)
        if not c:
            etapas_view.append(
                {
                    "etapa": e.value,
                    "nome": e.value.capitalize(),
                    "data": None,
                    "concluido": False,
                    "respostas": {},
                }
            )
            continue
        etapas_view.append(
            {
                "etapa": e.value,
                "nome": e.value.capitalize(),
                "data": c.data_inicio,
                "concluido": c.concluido,
                "situacao_final": c.situacao_final,
                "respostas": respostas.get(e, {}),
            }
        )

    # Diff Inicial × Percurso
    linhas = []
    for p in perguntas:
        ini = respostas.get(EtapaConselho.INICIAL, {}).get(p.id, {})
        per = respostas.get(EtapaConselho.PERCURSO, {}).get(p.id, {})
        linhas.append(
            {
                "pergunta": p.texto,
                "inicial": ini.get("resposta") or "—",
                "percurso": per.get("resposta") or "—",
                "mudou": ini.get("resposta") != per.get("resposta")
                and bool(ini or per),
                "inicial_obs": ini.get("observacao"),
                "percurso_obs": per.get("observacao"),
            }
        )

    return {"etapas": etapas_view, "linhas": linhas, "por_etapa": por_etapa}


# =============================================================================
# Sinais de atenção
# =============================================================================
def _sinais(freq: dict, conselho: dict, atendimentos_count: int) -> list[dict]:
    sinais: list[dict] = []
    if freq["maior_seq_faltas"] >= 2:
        sinais.append(
            {
                "nivel": "warn",
                "icone": "calendar-x",
                "titulo": f'{freq["maior_seq_faltas"]} faltas seguidas no período',
                "detalhe": "Regra: 2 ou mais faltas (F) seguidas; J não conta.",
            }
        )
    if freq["diff_turma"] <= -5:
        sinais.append(
            {
                "nivel": "warn",
                "icone": "graph-up",
                "titulo": f'{abs(freq["diff_turma"]):.1f} pontos abaixo da média da turma',
                "detalhe": f'{freq["pct_str"]} contra {freq["pct_turma_str"]} · regra: 5 pp ou mais.',
            }
        )
    if LIMIAR_CRITICO <= freq["pct"] < 90:
        sinais.append(
            {
                "nivel": "info",
                "icone": "clipboard-check",
                "titulo": "Faixa de frequência 75–89%",
                "detalhe": "Mais 2 faltas seguidas levariam abaixo de 75% (faixa crítica).",
            }
        )
    if freq["pct"] < LIMIAR_CRITICO:
        sinais.append(
            {
                "nivel": "bad",
                "icone": "exclamation-triangle",
                "titulo": f"Abaixo do limite crítico ({fmt_pct(LIMIAR_CRITICO)})",
                "detalhe": "Prioridade para atendimento pedagógico.",
            }
        )
    if atendimentos_count:
        sinais.append(
            {
                "nivel": "info",
                "icone": "chat-left-text",
                "titulo": f"{atendimentos_count} atendimento(s) no período",
                "detalhe": "Verifique o histórico para acompanhar o retorno.",
            }
        )
    return sinais


# =============================================================================
# Timeline
# =============================================================================
def _timeline(
    freq: dict, conselho: dict, atendimentos: list, turma: Turma
) -> list[dict]:
    ev: list[dict] = []

    # Faltas (agrupadas em sequência)
    prev = None
    seq_start = None
    for d, c in sorted(freq["por_data"].items()):
        if c == ConceitoFrequencia.F:
            if seq_start is None:
                seq_start = d
            prev = d
        else:
            if seq_start is not None:
                _push_falta(ev, seq_start, prev)
            seq_start = None
    if seq_start is not None:
        _push_falta(ev, seq_start, prev)

    # Justificadas isoladas
    for d, c in freq["por_data"].items():
        if c == ConceitoFrequencia.J:
            ev.append(
                {
                    "data": d,
                    "tipo": "warn",
                    "icone": "check2-circle",
                    "titulo": "Falta justificada",
                    "detalhe": None,
                }
            )

    # Conselhos
    for e in conselho["etapas"]:
        if e["data"] and e["concluido"]:
            ev.append(
                {
                    "data": e["data"],
                    "tipo": "ok",
                    "icone": "clipboard-check",
                    "titulo": f'Conselho {e["nome"].lower()} concluído',
                    "detalhe": (f'Situação: {e.get("situacao_final") or "—"}'),
                }
            )

    # Atendimentos
    for a in atendimentos:
        ev.append(
            {
                "data": a.data_atendimento,
                "tipo": "info",
                "icone": "chat-left-text",
                "titulo": "Atendimento pedagógico",
                "detalhe": a.resumo,
            }
        )

    # Início
    if turma.data_inicio:
        ev.append(
            {
                "data": turma.data_inicio,
                "tipo": "info",
                "icone": "person-plus",
                "titulo": "Início na turma",
                "detalhe": None,
            }
        )

    ev.sort(key=lambda x: x["data"], reverse=True)
    return ev


def _push_falta(ev: list, ini: date, fim: date | None) -> None:
    fim = fim or ini
    if ini == fim:
        titulo = "Falta isolada"
    else:
        titulo = f"{(fim - ini).days // 7 + 1} faltas seguidas"
    ev.append(
        {
            "data": fim,
            "tipo": "bad",
            "icone": "calendar-x",
            "titulo": titulo,
            "detalhe": (
                f"{ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}"
                if ini != fim
                else None
            ),
        }
    )


# =============================================================================
# Percurso (turmas anteriores)
# =============================================================================
def _percurso(aluno_id: int, turma_atual_id: int) -> list[dict]:
    rows = (
        db.session.query(Inscricao, Turma)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .join(PeriodoLetivo, PeriodoLetivo.id == Turma.periodo_letivo_id)
        .filter(Inscricao.aluno_id == aluno_id, Turma.id != turma_atual_id)
        .order_by(PeriodoLetivo.data_inicio.desc())
        .all()
    )
    out = []
    for insc, t in rows:
        # Recalcula pct simples
        tot = Frequencia.query.filter_by(aluno_id=aluno_id, turma_id=t.id).count()
        pres = Frequencia.query.filter(
            Frequencia.aluno_id == aluno_id,
            Frequencia.turma_id == t.id,
            Frequencia.conceito.in_(
                [
                    ConceitoFrequencia.A,
                    ConceitoFrequencia.B,
                    ConceitoFrequencia.C,
                    ConceitoFrequencia.D,
                ]
            ),
        ).count()
        cont = Frequencia.query.filter(
            Frequencia.aluno_id == aluno_id,
            Frequencia.turma_id == t.id,
            Frequencia.conceito.in_(
                [
                    ConceitoFrequencia.A,
                    ConceitoFrequencia.B,
                    ConceitoFrequencia.C,
                    ConceitoFrequencia.D,
                    ConceitoFrequencia.F,
                ]
            ),
        ).count()
        p = pct(pres, cont)
        situacao = _situacao_por_turma(aluno_id, t.id)
        out.append(
            {
                "periodo": t.periodo_letivo.nome if t.periodo_letivo else "—",
                "turma": t.nome,
                "nivel": insc.nivel or "—",
                "aulas": tot,
                "pct": p,
                "pct_str": fmt_pct(p),
                "situacao": situacao,
            }
        )
    return out


def _situacao_por_turma(aluno_id: int, turma_id: int) -> dict:
    c = ConselhoClasse.query.filter_by(
        aluno_id=aluno_id, turma_id=turma_id, etapa=EtapaConselho.FINAL
    ).first()
    if not c:
        return {"label": "Em andamento", "classe": "primary"}
    if not c.situacao_final:
        return {"label": "Em andamento", "classe": "primary"}
    from app.models.enums import SituacaoFinal

    s = c.situacao_final
    if s == SituacaoFinal.APROVADO:
        return {"label": "Aprovado", "classe": "success"}
    if s == SituacaoFinal.REPROVADO:
        return {"label": "Reprovado", "classe": "danger"}
    return {"label": str(s), "classe": "secondary"}


# =============================================================================
# Orquestração
# =============================================================================
def montar(aluno: Aluno, turma: Turma, inscricao: Inscricao | None) -> dict:
    periodo = turma.periodo_letivo
    semanas = semanas_do_periodo(periodo) if periodo else []

    freq = _frequencia(aluno.id, turma, semanas)
    cons = _conselho(aluno.id, turma, periodo)

    atendimentos = (
        Atendimento.query.filter_by(aluno_id=aluno.id)
        .order_by(Atendimento.data_atendimento.desc())
        .limit(20)
        .all()
    )

    perfil = aluno_perfil.get_perfil_completo(aluno) or {}
    endereco = perfil.get("endereco") or {}
    socio = perfil.get("socioeconomico") or {}

    return {
        "aluno": aluno,
        "turma": turma,
        "inscricao": inscricao,
        "periodo": periodo,
        "identidade": _identidade(aluno, turma, inscricao),
        "frequencia": freq,
        "conselho": cons,
        "atendimentos": atendimentos,
        "timeline": _timeline(freq, cons, atendimentos, turma),
        "percurso": _percurso(aluno.id, turma.id),
        "sinais": _sinais(freq, cons, len(atendimentos)),
        "contexto_restrito": {
            "renda_familiar": socio.get("renda_familiar"),
            "programa_social": socio.get("beneficio_social_status") == "Sim",
            "internet": endereco.get("possui_acesso_internet"),
            "bairro": endereco.get("bairro"),
            "permitido": True,  # o template só renderiza se tiver permissão
        },
    }
