"""Agregação do conselho de classe por turma (1 consulta por tabela)."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from app.models import ConselhoClasse, ConselhoResposta, PerguntaConselho


def por_turma(turmas_ids: Iterable[int]) -> dict[int, dict]:
    turmas_ids = list(turmas_ids)
    if not turmas_ids:
        return {}

    conselhos = ConselhoClasse.query.filter(
        ConselhoClasse.turma_id.in_(turmas_ids)
    ).all()
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
    perguntas = (
        {
            p.id: p.enunciado
            for p in PerguntaConselho.query.filter(
                PerguntaConselho.id.in_(perguntas_ids)
            ).all()
        }
        if perguntas_ids else {}
    )

    turma_map: dict[int, dict] = defaultdict(
        lambda: {
            "inicial": {"total": 0, "respondidos": 0},
            "percurso": {"total": 0, "respondidos": 0},
            "final": {"total": 0, "respondidos": 0},
            "respostas": defaultdict(
                lambda: {"inicial": defaultdict(int), "percurso": defaultdict(int)}
            ),
            "perguntas": {},
        }
    )

    for cons in conselhos:
        etapa = (cons.etapa or "").lower()
        bloco = turma_map[cons.turma_id]
        if etapa not in bloco:
            continue
        bloco[etapa]["total"] += 1
        respostas = respostas_por_conselho.get(cons.id, [])
        if respostas:
            bloco[etapa]["respondidos"] += 1
        for r in respostas:
            if r.pergunta_id is None:
                continue
            bloco["perguntas"][r.pergunta_id] = perguntas.get(
                r.pergunta_id, f"Pergunta {r.pergunta_id}"
            )
            opcao = (r.resposta or "").strip() or "—"
            if etapa in ("inicial", "percurso"):
                bloco["respostas"][r.pergunta_id][etapa][opcao] += 1

    return {
        tid: {
            "inicial": bloco["inicial"],
            "percurso": bloco["percurso"],
            "final": bloco["final"],
            "respostas": {
                pid: {"inicial": dict(e["inicial"]),
                      "percurso": dict(e["percurso"])}
                for pid, e in bloco["respostas"].items()
            },
            "perguntas": bloco["perguntas"],
        }
        for tid, bloco in turma_map.items()
    }


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
        }
        for pid, etapas_ in cons.get("respostas", {}).items()
    ]