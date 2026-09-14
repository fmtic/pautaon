"""Dashboard do perfil professor: turmas, alunos e pendências de frequência."""

from datetime import date

from flask import flash, render_template
from flask_login import current_user

from app.models import Aluno, DiaBloqueado, Frequencia, Inscricao, Turma
from app.utils.logica import gerar_datas


def render_dashboard_professor():
    """Painel com as turmas do professor logado e as aulas com frequência pendente."""
    try:
        minhas_turmas = Turma.query.filter_by(professor_id=current_user.id, ativo=True).all()
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
        periodo_ids = {t.periodo_letivo_id for t in minhas_turmas if t.periodo_letivo_id}
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

        aulas_pendentes = []
        for turma in minhas_turmas:
            blocked = set()
            if turma.periodo_letivo_id:
                blocked = {
                    d.data.strftime('%Y-%m-%d')
                    for d in DiaBloqueado.query.filter_by(periodo_letivo_id=turma.periodo_letivo_id).all()
                }

            datas_aula = gerar_datas(turma, incluir_futuro=False, blocked_dates=blocked)

            alunos_turma = (
                Aluno.query.join(Inscricao)
                .filter(
                    Inscricao.turma_id == turma.id,
                    Inscricao.ativo == True,
                    Aluno.ativo == True,
                )
                .all()
            )
            if not alunos_turma:
                continue

            aluno_ids = [a.id for a in alunos_turma]

            for data_str in datas_aula:
                lancados = Frequencia.query.filter(
                    Frequencia.turma_id == turma.id,
                    Frequencia.data == data_str,
                    Frequencia.aluno_id.in_(aluno_ids),
                    Frequencia.conceito.isnot(None),
                    Frequencia.conceito != '',
                ).count()

                if lancados < len(aluno_ids):
                    faltando = len(aluno_ids) - lancados
                    aulas_pendentes.append({
                        'turma':    turma,
                        'data':     data_str,
                        'faltando': faltando,
                        'total':    len(aluno_ids),
                    })

        aulas_pendentes.sort(key=lambda x: x['data'])

        return render_template(
            "dashboard/professor.html",
            turmas=minhas_turmas,
            total_alunos=total_meus_alunos,
            dias_bloqueados=dias_bloqueados,
            aulas_pendentes=aulas_pendentes,
        )
    except Exception:
        flash("Erro ao processar as turmas do professor.", "warning")
        return render_template(
            "dashboard/professor.html",
            turmas=[],
            total_alunos=0,
            dias_bloqueados=[],
            aulas_pendentes=[],
        )
