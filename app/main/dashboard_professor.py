"""Dashboard do perfil professor: turmas, alunos e pendências de frequência."""

from datetime import date

from flask import current_app, flash, render_template
from flask_login import current_user

from app.models import Aluno, DiaBloqueado, Turma
from app.utils.datetime_parse import parse_date
from app.utils.frequencia import (
    alunos_ativos_da_turma,
    datas_bloqueadas_str,
    frequencias_lancadas,
)
from app.utils.logica import gerar_datas


def _aulas_pendentes(minhas_turmas):
    """
    Lista de aulas com frequência incompleta nas turmas do professor.

    Retorna lista de dicts:
        - turma     : instância de Turma
        - data      : `date` da aula (após Onda 2A)
        - faltando  : alunos sem conceito lançado
        - total     : total de alunos ativos na turma
    """
    pendentes = []
    for turma in minhas_turmas:
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        datas_aula = gerar_datas(
            turma, incluir_futuro=False, blocked_dates=blocked
        )

        aluno_ids = alunos_ativos_da_turma(turma.id)
        if not aluno_ids:
            continue

        for data_item in datas_aula:
            # `gerar_datas` ainda pode retornar strings; parse_date normaliza.
            data_alvo = parse_date(data_item)
            if data_alvo is None:
                continue

            lancados = frequencias_lancadas(turma.id, data_alvo, aluno_ids)
            if lancados < len(aluno_ids):
                pendentes.append({
                    'turma':    turma,
                    'data':     data_alvo,
                    'faltando': len(aluno_ids) - lancados,
                    'total':    len(aluno_ids),
                })

    pendentes.sort(key=lambda x: x['data'])
    return pendentes


def render_dashboard_professor():
    """Painel com as turmas do professor logado e as aulas com frequência pendente."""
    try:
        minhas_turmas = Turma.query.filter_by(
            professor_id=current_user.id, ativo=True
        ).all()
        ids_turmas = [t.id for t in minhas_turmas]

        total_meus_alunos = 0
        if ids_turmas:
            total_meus_alunos = (
                Aluno.query.join(Aluno.turmas)
                .filter(Turma.id.in_(ids_turmas), Aluno.ativo == True)
                .distinct()
                .count()
            )

        hoje = date.today()
        periodo_ids = {
            t.periodo_letivo_id for t in minhas_turmas if t.periodo_letivo_id
        }
        dias_bloqueados = []
        if periodo_ids:
            dias_bloqueados = (
                DiaBloqueado.query.filter(
                    DiaBloqueado.periodo_letivo_id.in_(periodo_ids),
                    DiaBloqueado.data >= hoje,
                )
                .order_by(DiaBloqueado.data)
                .all()
            )

        aulas_pendentes = _aulas_pendentes(minhas_turmas)

        return render_template(
            "dashboard/professor.html",
            turmas=minhas_turmas,
            total_alunos=total_meus_alunos,
            dias_bloqueados=dias_bloqueados,
            aulas_pendentes=aulas_pendentes,
        )
    except Exception:
        # Loga o traceback no servidor em vez de engolir silenciosamente.
        current_app.logger.exception(
            "Erro ao processar as turmas do professor (user_id=%s)",
            current_user.id,
        )
        flash("Erro ao processar as turmas do professor.", "warning")
        return render_template(
            "dashboard/professor.html",
            turmas=[],
            total_alunos=0,
            dias_bloqueados=[],
            aulas_pendentes=[],
        )