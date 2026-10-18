"""Montagem da visão por turma."""

from __future__ import annotations

from datetime import date, timedelta

from app.models import Aluno, Inscricao, Turma

from . import coorte, conselho, frequencia
from .frequencia import FrequenciaTurma
from .formatacao import (
    celulas_semanais,
    classe_tendencia,
    faixa_meta,
    fmt_diff,
    fmt_pct,
    larguras_faixas,
)
from .helpers import (
    faixa,
    faixas_alunos,
    faltas_atuais,
    maior_sequencia_faltas,
    pct,
    semanas_do_periodo,
    tendencia,
)
from .regras import FALTAS_SEGUIDAS_SINAL, ContextoSinaisTurma
from .sinais import sinais_turma


def montar(turma: Turma, unidade_id: int | None) -> dict:
    periodo = turma.periodo_letivo
    if not periodo:
        return {"turma": turma, "vazia": True}

    semanas = semanas_do_periodo(periodo)
    freq = frequencia.agregar_por_turma([turma.id]).get(
        turma.id, FrequenciaTurma()
    )
    cons = conselho.por_turma([turma.id]).get(turma.id, {})

    alunos_dados = _alunos_da_turma(turma, freq)
    fx = faixas_alunos(freq.por_aluno_pct)
    semanais = frequencia.semanal(freq.por_aluno, semanas)
    tend = tendencia(semanais)

    media_periodo = _media_periodo(periodo)
    diff_media = (
        freq.pct_turma - media_periodo
        if media_periodo is not None else None
    )

    cons_perc = cons.get("percurso", {})
    pend_percurso = max(
        0, cons_perc.get("total", 0) - cons_perc.get("respondidos", 0)
    )
    faltas_atuais_qtd = sum(
        1 for a in alunos_dados if a["faltas_atuais"] >= FALTAS_SEGUIDAS_SINAL
    )

    sinais = sinais_turma(ContextoSinaisTurma(
        faixas=fx,
        pct_turma=freq.pct_turma,
        semanais=semanais,
        semanas=tuple(semanas),
        faltas_atuais=faltas_atuais_qtd,
        conselho_pendentes=pend_percurso,
    ))

    f_t = faixa(freq.pct_turma)
    serie = [semanais[i] for i in sorted(semanais)]

    return {
        "turma": turma,
        "periodo": periodo,
        "semanas": semanas,
        "semanas_iso": [d.isoformat() for d in semanas],
        "serie_turma": serie,
        "alunos": alunos_dados,
        "alunos_por_aula": _matriz_alunos_aula(alunos_dados),
        "faixas": fx,
        "faixas_largura": larguras_faixas(fx),
        "pct_turma": freq.pct_turma,
        "pct_turma_str": fmt_pct(freq.pct_turma),
        "faixa_turma": f_t,
        "faixa_meta": faixa_meta(f_t),
        "faltas": freq.total - freq.presentes,
        "presencas": freq.presentes,
        "total_aulas": freq.total,
        "media_periodo": media_periodo,
        "media_periodo_str": fmt_pct(media_periodo),
        "diff_media": diff_media,
        "diff_media_str": fmt_diff(diff_media),
        "diff_media_classe": classe_tendencia(diff_media),
        "semanais": semanais,
        "semanais_celulas": celulas_semanais(semanais),
        "tendencia": tend,
        "tendencia_str": fmt_diff(tend),
        "tendencia_classe": classe_tendencia(tend),
        "sinais": sinais,
        "conselho": cons,
        "conselho_etapas": conselho.etapas(cons),
        "conselho_agregado": conselho.agregar_respostas(cons),
    }


def _alunos_da_turma(turma: Turma, freq: FrequenciaTurma) -> list[dict]:
    aluno_ids = list(freq.por_aluno.keys())
    if not aluno_ids:
        return []

    alunos = {
        a.id: a for a in Aluno.query.filter(Aluno.id.in_(aluno_ids)).all()
    }
    inscricoes = {
        i.aluno_id: i
        for i in Inscricao.query.filter(
            Inscricao.aluno_id.in_(aluno_ids),
            Inscricao.turma_id == turma.id,
        ).all()
    }

    saida = []
    for aluno_id, lista in freq.por_aluno.items():
        aluno = alunos.get(aluno_id)
        if not aluno:
            continue
        p = freq.por_aluno_pct.get(aluno_id, 0.0)
        insc = inscricoes.get(aluno_id)
        f_al = faixa(p)
        saida.append({
            "id": aluno.id,
            "nome": aluno.nome,
            "nome_social": aluno.nome_social,
            "status": getattr(insc, "status", "") if insc else "",
            "pct": p,
            "pct_str": fmt_pct(p),
            "faixa": f_al,
            "faixa_meta": faixa_meta(f_al),
            "maior_seq_faltas": maior_sequencia_faltas(lista),
            "faltas_atuais": faltas_atuais(lista),
            "aulas": [{"data": d, "conceito": c} for d, c in lista],
            "conceitos_por_data": {d.isoformat(): c for d, c in lista},
        })
    saida.sort(key=lambda d: d["pct"])
    return saida


def _media_periodo(periodo) -> float | None:
    turmas_periodo = Turma.query.filter_by(
        periodo_letivo_id=periodo.id, ativo=True
    ).all()
    if not turmas_periodo:
        return None
    agg = frequencia.agregar_por_turma([t.id for t in turmas_periodo])
    pres = sum(v.presentes for v in agg.values())
    tot = sum(v.total for v in agg.values())
    return pct(pres, tot) if tot else None


def _matriz_alunos_aula(alunos: list[dict]) -> dict:
    """Datas reais e rótulos prontos, sem deixar `date` no template."""
    datas_reais = sorted({a["data"] for al in alunos for a in al["aulas"]})
    return {
        "datas": [
            {"iso": d.isoformat(), "label": d.strftime("%d/%m")}
            for d in datas_reais
        ],
        "semanas_padding": [
            # colunas por semana com dias úteis padrão (ter/qui)
            d.isoformat() for d in datas_reais
        ],
    }