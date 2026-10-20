"""Montagem da visão por período letivo."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func

from app import db
from app.models import Inscricao, PeriodoLetivo, Turma
from app.models.enums import StatusAluno

from . import coorte, conselho, frequencia
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
    pct,
    semanas_do_periodo,
    tendencia,
)
from .regras import (
    LIMIAR_CRITICO,
    MIN_TURMAS_QUEDA_COMUM,
    QUEDA_SEMANAL_PP,
)
# Removemos a importação de ContextoSinaisPeriodo e sinais_periodo
# pois agora vamos gerar os sinais customizados abaixo.

# =============================================================================
# Acumuladores (Mantidos iguais)
# =============================================================================
@dataclass
class _Acumulado:
    alunos: int = 0
    presencas: int = 0
    total_aulas: int = 0
    faixas: dict = field(default_factory=lambda: {"hi": 0, "mid": 0, "lo": 0, "total": 0})
    risco_noite: int = 0
    noite_total: int = 0
    turmas_abaixo_75: int = 0
    conselho_pendentes: int = 0
    queda_por_semana: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    def absorver_turma(self, info: frequencia.FrequenciaTurma) -> dict:
        self.alunos += len(info.por_aluno)
        self.presencas += info.presentes
        self.total_aulas += info.total
        fx = faixas_alunos(info.por_aluno_pct)
        for k in ("hi", "mid", "lo", "total"):
            self.faixas[k] += fx[k]
        if info.pct_turma < LIMIAR_CRITICO:
            self.turmas_abaixo_75 += 1
        return fx

    def registrar_noite(self, info: frequencia.FrequenciaTurma, fx: dict) -> None:
        self.noite_total += len(info.por_aluno)
        self.risco_noite += fx["lo"]

    def registrar_queda(self, pct_turma: float, semanais: dict[int, float | None]) -> None:
        for i, v in semanais.items():
            if v is not None and (pct_turma - v) >= QUEDA_SEMANAL_PP:
                self.queda_por_semana[i] += 1

    def semanas_queda_comum(self) -> set[int]:
        return {i for i, n in self.queda_por_semana.items() if n >= MIN_TURMAS_QUEDA_COMUM}


# =============================================================================
# Nova função: Gera os Sinais e o Bloco de Entradas
# =============================================================================
def _gerar_sinais_e_entradas(acum: _Acumulado, turmas_dados: list, semanas_queda: set, status_map: dict, desativacoes: list):
    # 1. Sinais de Atenção
    sinais = []
    
    # 1.1 Turma abaixo de 75%
    turmas_abaixo = [t for t in turmas_dados if t["pct_turma"] < 75.0]
    if turmas_abaixo:
        pior_turma = min(turmas_abaixo, key=lambda x: x["pct_turma"])
        titulo = f'{len(turmas_abaixo)} turma{"s" if len(turmas_abaixo)>1 else ""} abaixo de 75%'
        sinais.append({
            "nivel": "bad", "icone": "exclamation-triangle",
            "titulo": titulo,
            "detalhe": f'{pior_turma["nome"]} ({pior_turma["pct_turma_str"]}) · regra: frequência da turma < 75%.'
        })

    # 1.2 Queda Comum
    if semanas_queda:
        primeiras = sorted(list(semanas_queda))[:2]
        datas = " e ".join([s.strftime("%d/%m") for s in primeiras])
        sinais.append({
            "nivel": "info", "icone": "calendar3",
            "titulo": f'Queda comum nas semanas de {datas}',
            "detalhe": "Até 6 de 8 turmas ficaram 8 pontos ou mais abaixo da própria média. Padrão que sugere causa comum; verificar clima, calendário e transporte."
        })

    # 1.3 Alunos em risco noite
    if acum.risco_noite > 0 and acum.noite_total > 0:
        pct_noite = (acum.risco_noite / acum.noite_total * 100)
        sinais.append({
            "nivel": "warn", "icone": "person-x",
            "titulo": f'{acum.risco_noite} dos {acum.faixas["lo"]} alunos em risco estão no turno da noite',
            "detalhe": f"As turmas noturnas têm {pct_noite:.0f}% dos alunos enturmados."
        })

    # 1.4 Conselho Pendente
    if acum.conselho_pendentes > 0:
        # Nota: Data de abertura da etapa final não está disponível no contexto atual
        # Removendo texto hardcoded de protótipo
        sinais.append({
            "nivel": "warn", "icone": "clipboard-check",
            "titulo": f'Conselho de percurso: {acum.conselho_pendentes} alunos pendentes',
            "detalhe": "Verifique o conselho de percurso para garantir acompanhamento adequado."
        })

    # 2. Entradas (Quem está enturmado)
    novos = sum(1 for s in status_map.values() if s == StatusAluno.NOVO)
    renovados = sum(1 for s in status_map.values() if s == StatusAluno.RENOVADO)
    retornantes = sum(1 for s in status_map.values() if s == StatusAluno.RETORNANTE)
    total_enturmados = novos + renovados + retornantes
    
    entradas = {
        "novos": novos, "renovados": renovados, "retornantes": retornantes,
        "pct_novos": (novos / total_enturmados * 100) if total_enturmados else 0,
        "pct_renovados": (renovados / total_enturmados * 100) if total_enturmados else 0,
        "pct_retornantes": (retornantes / total_enturmados * 100) if total_enturmados else 0,
    }

    # 3. Desativações (Insight)
    total_desativacoes = sum(d["qtd"] for d in desativacoes)
    top2_qtd = sum(d["qtd"] for d in desativacoes[:2]) if desativacoes else 0
    pct_top2 = (top2_qtd / total_desativacoes * 100) if total_desativacoes else 0
    top2_nomes = " e ".join([d["motivo"].lower() for d in desativacoes[:2]]) if len(desativacoes) >= 2 else ""
    
    insight = ""
    if total_desativacoes > 0:
        insight = f'{top2_nomes.capitalize()} respondem por {top2_qtd} de {total_desativacoes} ({pct_top2:.0f}%): barreiras que a ONG pode tratar.'

    return sinais, entradas, insight


# =============================================================================
# Orquestração
# =============================================================================
def montar(periodo: PeriodoLetivo, unidade_id: int | None) -> dict:
    turmas = (
        Turma.query.filter_by(periodo_letivo_id=periodo.id, ativo=True)
        .order_by(Turma.nome)
        .all()
    )
    turmas_ids = [t.id for t in turmas]
    semanas = semanas_do_periodo(periodo)

    freq = frequencia.agregar_por_turma(turmas_ids)
    cons = conselho.por_turma(turmas_ids)

    status_map = coorte.status(unidade_id, periodo.id)
    enturmados_ids = coorte.enturmados(status_map)

    acum = _Acumulado()
    turmas_dados: list[dict] = []

    for t in turmas:
        info = freq.get(t.id)
        if not info:
            continue

        fx = acum.absorver_turma(info)
        cons_turma = cons.get(t.id, {})

        perc = cons_turma.get("percurso", {})
        acum.conselho_pendentes += max(0, perc.get("total", 0) - perc.get("respondidos", 0))

        if (t.turno or "").lower().startswith("noite"):
            acum.registrar_noite(info, fx)

        semanais = frequencia.semanal(info.por_aluno, semanas)
        acum.registrar_queda(info.pct_turma, semanais)

        turmas_dados.append(_montar_turma_linha(t, info, cons_turma, semanas))

    turmas_dados.sort(key=lambda d: d["pct_turma"])
    semanas_queda_comum = acum.semanas_queda_comum()
    
    # Desativações vêm antes de gerar os sinais
    desativacoes = _desativacoes_por_motivo(periodo)
    
    # Gera o novo pacote de sinais e entradas
    sinais, entradas, insight_desativacao = _gerar_sinais_e_entradas(
        acum, turmas_dados, semanas_queda_comum, status_map, desativacoes
    )

    cons_total = sum(d["conselho_percurso_total"] for d in turmas_dados)
    cons_ok = sum(d["conselho_percurso_ok"] for d in turmas_dados)

    return {
        "periodo": periodo,
        "semanas": semanas,
        "semanas_queda_comum": semanas_queda_comum,
        "turmas": turmas_dados,
        "totais": _totais(acum, status_map),
        "renovacao": coorte.renovacao(periodo, unidade_id, enturmados_ids),
        "desativacoes": desativacoes,
        "total_desativacoes": sum(d["qtd"] for d in desativacoes),
        "insight_desativacao": insight_desativacao,
        "entradas": entradas,
        "sinais": sinais,
        "conselho_pendentes": acum.conselho_pendentes,
        "conselho_total_percurso": cons_total,
        "conselho_ok_percurso": cons_ok,
        "conselho_percurso_pct": (round(cons_ok / cons_total * 100, 0) if cons_total else None),
    }

def _totais(acum: _Acumulado, status_map: dict) -> dict:
    # Mantido igual ao seu
    pct_geral = pct(acum.presencas, acum.total_aulas)
    return {
        "alunos": acum.alunos,
        "pct_geral": pct_geral,
        "pct_geral_str": fmt_pct(pct_geral),
        "faixas": acum.faixas,
        "faixas_largura": larguras_faixas(acum.faixas),
        "novos": sum(1 for s in status_map.values() if s == StatusAluno.NOVO),
        "renovados": sum(1 for s in status_map.values() if s == StatusAluno.RENOVADO),
        "retornantes": sum(1 for s in status_map.values() if s == StatusAluno.RETORNANTE),
    }

def _desativacoes_por_motivo(periodo: PeriodoLetivo) -> list[dict]:
    # Mantido igual ao seu
    rows = (
        db.session.query(Inscricao.motivo_desativacao, func.count(Inscricao.id))
        .join(Turma, Turma.id == Inscricao.turma_id)
        .filter(
            Turma.periodo_letivo_id == periodo.id,
            Inscricao.ativo.is_(False),
            Inscricao.motivo_desativacao.isnot(None),
        )
        .group_by(Inscricao.motivo_desativacao)
        .order_by(func.count(Inscricao.id).desc())
        .all()
    )
    return [{"motivo": m or "Sem motivo registrado", "qtd": q} for m, q in rows]