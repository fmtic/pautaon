"""Regras de sinais de atenção (período e turma)."""

from __future__ import annotations

from .regras import (
    FALTAS_SEGUIDAS_SINAL,
    LIMIAR_CRITICO,
    QUEDA_SEMANAL_PP,
    ContextoSinaisPeriodo,
    ContextoSinaisTurma,
)


def sinais_periodo(ctx: ContextoSinaisPeriodo) -> list[dict]:
    sinais: list[dict] = []
    if ctx.turmas_abaixo_75:
        sinais.append({
            "nivel": "bad",
            "icone": "exclamation-triangle",
            "titulo": (
                f"{ctx.turmas_abaixo_75} turma(s) abaixo de "
                f"{LIMIAR_CRITICO:.0f}%"
            ),
            "detalhe": f"Regra: frequência da turma < {LIMIAR_CRITICO:.0f}%.",
        })
    if ctx.semanas_queda_comum:
        sinais.append({
            "nivel": "info",
            "icone": "calendar3",
            "titulo": "Queda comum nas semanas "
            + ", ".join(
                f"{ctx.semanas[i]:%d/%m}"
                for i in sorted(ctx.semanas_queda_comum)
            ),
            "detalhe": (
                f"Até "
                f"{max(ctx.queda_por_semana[i] for i in ctx.semanas_queda_comum)} "
                "turmas ficaram 8+ pontos abaixo da própria média."
            ),
        })
    if ctx.alunos_risco_noite:
        sinais.append({
            "nivel": "warn",
            "icone": "person-lines-fill",
            "titulo": (
                f"{ctx.alunos_risco_noite} dos alunos em risco estão no "
                "turno da noite"
            ),
            "detalhe": (
                f"O noturno reúne {ctx.alunos_noite_total} alunos enturmados."
            ),
        })
    if ctx.conselho_pendentes:
        sinais.append({
            "nivel": "warn",
            "icone": "clipboard-check",
            "titulo": (
                f"Conselho de percurso: {ctx.conselho_pendentes} "
                "aluno(s) pendente(s)"
            ),
            "detalhe": (
                "Etapa final abre na data configurada em "
                "`ConfiguracaoSistema`."
            ),
        })
    return sinais


def sinais_turma(ctx: ContextoSinaisTurma) -> list[dict]:
    sinais: list[dict] = []
    if ctx.faixas["lo"]:
        sinais.append({
            "nivel": "bad" if ctx.faixas["lo"] > 1 else "warn",
            "icone": "exclamation-triangle",
            "titulo": (
                f"{ctx.faixas['lo']} aluno(s) abaixo de {LIMIAR_CRITICO:.0f}%"
            ),
            "detalhe": (
                f"{ctx.faixas['lo']/ctx.faixas['total']*100:.1f}% da turma · "
                f"regra: frequência individual < {LIMIAR_CRITICO:.0f}%."
            ),
        })
    if ctx.pct_turma and ctx.semanais:
        pior = min(
            (i for i, v in ctx.semanais.items() if v is not None),
            key=lambda i: ctx.semanais[i],
            default=None,
        )
        if (
            pior is not None
            and ctx.pct_turma - ctx.semanais[pior] >= QUEDA_SEMANAL_PP
        ):
            sinais.append({
                "nivel": "info",
                "icone": "graph-up",
                "titulo": (
                    f"Semana de {ctx.semanas[pior]:%d/%m}: "
                    f"{ctx.semanais[pior]:.0f}% de frequência"
                ),
                "detalhe": (
                    f"{ctx.pct_turma - ctx.semanais[pior]:.0f} pontos abaixo "
                    f"da média da turma · regra: queda de "
                    f"{QUEDA_SEMANAL_PP:.0f}+ pontos."
                ),
            })
    if ctx.faltas_atuais:
        sinais.append({
            "nivel": "warn",
            "icone": "calendar-x",
            "titulo": (
                f"{ctx.faltas_atuais} aluno(s) com "
                f"{FALTAS_SEGUIDAS_SINAL}+ faltas seguidas agora"
            ),
            "detalhe": "Regra: as últimas aulas válidas foram F; J não conta.",
        })
    if ctx.conselho_pendentes:
        sinais.append({
            "nivel": "warn",
            "icone": "clipboard-check",
            "titulo": (
                f"Conselho de percurso pendente para "
                f"{ctx.conselho_pendentes} aluno(s)"
            ),
            "detalhe": "Etapa fechada para a maioria; faltam registros.",
        })
    if not sinais:
        sinais.append({
            "nivel": "ok",
            "icone": "check2-circle",
            "titulo": "Sem sinais de atenção",
            "detalhe": "Nenhuma das regras foi acionada nesta turma.",
        })
    return sinais