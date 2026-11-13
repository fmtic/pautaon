"""Agregação do conselho de classe POR OFERTA (1 consulta por tabela).

D5.4: a unidade de conselho é (oferta, aluno, etapa). `por_turma` continua
recebendo ids de turma (o painel é por turma), mas agrega cada oferta
separadamente com o rótulo "Turma — Curso". Desde a D5.5
`turma_curso_id` é NOT NULL — linha legada sem oferta não existe mais (a
lista de conferência prévia ficou registrada em
`scripts/verificar_onda4_d5.py`).
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Iterable

from sqlalchemy.orm import joinedload

from app.models import ConselhoClasse, ConselhoResposta, PerguntaConselho, TurmaCurso
from app.models.enums import EtapaConselho, ETAPA_PARA_CAMPO_AVALIACAO
from app.services.conselho_leitura import rotulo_oferta


def _bloco_vazio() -> dict:
    return {
        "inicial": {"total": 0, "respondidos": 0},
        "percurso": {"total": 0, "respondidos": 0},
        "final": {"total": 0, "respondidos": 0},
        "respostas": defaultdict(
            lambda: {
                "inicial": defaultdict(int),
                "percurso": defaultdict(int),
                "final": defaultdict(int),
            }
        ),
        "perguntas": {},
    }


def _aplicar(bloco: dict, cons, respostas: list, perguntas: dict[str, str]) -> None:
    etapa = (cons.etapa or "").lower()
    if etapa not in ("inicial", "percurso", "final"):
        return
    bloco[etapa]["total"] += 1
    if respostas:
        bloco[etapa]["respondidos"] += 1
    for r in respostas:
        if r.pergunta_id is None:
            continue
        bloco["perguntas"][r.pergunta_id] = perguntas.get(
            r.pergunta_id, f"Pergunta {r.pergunta_id}"
        )
        opcao = (r.resposta or "").strip() or "—"
        if etapa in ("inicial", "percurso", "final"):
            bloco["respostas"][r.pergunta_id][etapa][opcao] += 1


def _serializar(bloco: dict) -> dict:
    return {
        "inicial": bloco["inicial"],
        "percurso": bloco["percurso"],
        "final": bloco["final"],
        "respostas": {
            pid: {
                "inicial": dict(etapas["inicial"]),
                "percurso": dict(etapas["percurso"]),
                "final": dict(etapas["final"]),
            }
            for pid, etapas in bloco["respostas"].items()
        },
        "perguntas": bloco["perguntas"],
    }


def por_turma(turmas_ids: Iterable[int]) -> dict[int, dict]:
    turmas_ids = list(turmas_ids)
    if not turmas_ids:
        return {}

    # AJ20: casca sem conteúdo equivale a linha ausente — não deve fazer a
    # turma/oferta aparecer no painel só por causa dela.
    from app.services.conselho_leitura import cond_conselho_sem_conteudo

    conselhos = (
        ConselhoClasse.query.filter(
            ConselhoClasse.turma_id.in_(turmas_ids),
            ConselhoClasse.turma_curso_id.is_not(None),
            ~cond_conselho_sem_conteudo(),
        ).all()
    )
    if not conselhos:
        return {}

    conselho_ids = [c.id for c in conselhos]
    respostas_por_conselho: dict[int, list[ConselhoResposta]] = defaultdict(list)
    for r in ConselhoResposta.query.filter(
        ConselhoResposta.conselho_id.in_(conselho_ids)
    ).all():
        respostas_por_conselho[r.conselho_id].append(r)

    perguntas_ids = {
        r.pergunta_id for lst in respostas_por_conselho.values()
        for r in lst if r.pergunta_id
    }
    # D5.4: `PerguntaConselho` tem `texto` (o antigo `p.enunciado` estourava
    # AttributeError sempre que havia respostas registradas).
    perguntas = (
        {
            p.id: p.texto
            for p in PerguntaConselho.query.filter(
                PerguntaConselho.id.in_(perguntas_ids)
            ).all()
        }
        if perguntas_ids else {}
    )

    ofertas: dict[int, TurmaCurso] = {
        o.id: o
        for o in TurmaCurso.query.options(
            joinedload(TurmaCurso.curso), joinedload(TurmaCurso.turma)
        )
        .filter(TurmaCurso.id.in_({c.turma_curso_id for c in conselhos}))
        .all()
    }

    turma_map: dict[int, dict] = defaultdict(_bloco_vazio)
    por_oferta: dict[tuple[int, int], dict] = defaultdict(_bloco_vazio)

    for cons in conselhos:
        respostas = respostas_por_conselho.get(cons.id, [])
        _aplicar(turma_map[cons.turma_id], cons, respostas, perguntas)
        _aplicar(
            por_oferta[(cons.turma_id, cons.turma_curso_id)],
            cons,
            respostas,
            perguntas,
        )

    saida: dict[int, dict] = {}
    for tid, bloco in turma_map.items():
        ofertas_view = []
        for (turma_id, oferta_id), bloco_oferta in por_oferta.items():
            if turma_id != tid:
                continue
            oferta = ofertas.get(oferta_id)
            ofertas_view.append(
                {
                    "turma_curso_id": oferta_id,
                    "rotulo": rotulo_oferta(oferta),
                    **_serializar(bloco_oferta),
                }
            )
        ofertas_view.sort(key=lambda item: (item["rotulo"], item["turma_curso_id"]))
        saida[tid] = {**_serializar(bloco), "ofertas": ofertas_view}
    return saida


def etapas(cons: dict) -> list[dict]:
    if not cons:
        return []
    return [
        {"nome": "Inicial", "chave": "inicial", **cons.get("inicial", {})},
        {"nome": "Percurso", "chave": "percurso", **cons.get("percurso", {})},
        {"nome": "Final", "chave": "final", **cons.get("final", {})},
    ]


def _dist_com_pct(dist: dict[str, int]) -> list[dict]:
    total = sum(dist.values()) or 1
    return [
        {"rotulo": k, "qtd": v, "pct": round(v / total * 100, 2)}
        for k, v in dist.items()
    ]


def agregar_respostas(cons: dict) -> list[dict]:
    if not cons:
        return []
    return [
        {
            "id": pid,
            "pergunta": cons.get("perguntas", {}).get(pid, f"Pergunta {pid}"),
            "inicial": _dist_com_pct(etapas_["inicial"]),
            "percurso": _dist_com_pct(etapas_["percurso"]),
            "final": _dist_com_pct(etapas_["final"]),
        }
        for pid, etapas_ in cons.get("respostas", {}).items()
    ]


def carregar_avaliacoes_coletivas(oferta_ids: Iterable[int]) -> dict[int, dict]:
    """Carrega `avaliacao_<etapa>` (JSON) das ofertas em UMA consulta.

    Devolve `{turma_curso_id: {etapa: {pergunta_id_str: resposta}}}` com as
    chaves de etapa em minúsculas (`inicial`, `percurso`, `final`) — o mesmo
    formato de `respostas` usado pelo restante do painel.
    Ofertas sem avaliação gravada mapeiam para dicionários de etapa vazios.
    """
    ids = [i for i in oferta_ids if i is not None]
    if not ids:
        return {}
    linhas = (
        TurmaCurso.query.options(joinedload(TurmaCurso.curso))
        .filter(TurmaCurso.id.in_(ids))
        .all()
    )
    saida: dict[int, dict] = {}
    for o in linhas:
        etapa_dados: dict[str, dict] = {}
        for etapa, campo in ETAPA_PARA_CAMPO_AVALIACAO.items():
            bruto = getattr(o, campo) or ""
            dados: dict[str, str] = {}
            if bruto:
                try:
                    carregado = json.loads(bruto)
                except (TypeError, json.JSONDecodeError):
                    carregado = {}
                if isinstance(carregado, dict):
                    dados = {
                        str(k): str(v)
                        for k, v in carregado.items()
                        if v and k != '_obs'
                    }
            etapa_dados[etapa.value.lower()] = dados
        saida[o.id] = etapa_dados
    return saida
