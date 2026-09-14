"""Dashboard consolidado usado pela secretaria (e demais perfis com acesso)."""

from datetime import date

from flask import abort, render_template
from flask_login import current_user, login_required

from app.models import (
    AgendaServicoSocial,
    Aluno,
    DiaBloqueado,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    Turma,
    Unidade,
)
from app.utils.logica import gerar_datas, get_unidade_id

from . import bp


@bp.route('/dashboard/secretaria')
@login_required
def dashboard_secretaria():
    if current_user.role not in ['admin', 'pedagogico', 'secretaria', 'gerencia', 'servico_social']:
        abort(403)

    unidade_id = get_unidade_id()

    q_alunos = Aluno.query.filter_by(ativo=True)
    q_turmas = Turma.query.filter_by(ativo=True)
    if unidade_id:
        q_alunos = q_alunos.filter_by(unidade_id=unidade_id)
        q_turmas = q_turmas.filter_by(unidade_id=unidade_id)

    total_alunos = q_alunos.count()
    total_turmas = q_turmas.count()

    hoje = date.today()
    periodo_ids_ativos = [
        p.id for p in PeriodoLetivo.query.filter_by(ativo=True).all()
        if not unidade_id or p.unidade_id == unidade_id
    ]
    proximas_datas_vagas = []
    if periodo_ids_ativos:
        proximas_datas_vagas = (
            DiaBloqueado.query
            .filter(
                DiaBloqueado.periodo_letivo_id.in_(periodo_ids_ativos),
                DiaBloqueado.data >= hoje,
            )
            .order_by(DiaBloqueado.data)
            .limit(5)
            .all()
        )
    total_dias_sem_aula = len(proximas_datas_vagas)

    turmas_ativas = q_turmas.all()
    total_pendencias_frequencia = 0
    for turma in turmas_ativas:
        blocked = set()
        if turma.periodo_letivo_id:
            blocked = {
                d.data.strftime('%Y-%m-%d')
                for d in DiaBloqueado.query.filter_by(periodo_letivo_id=turma.periodo_letivo_id).all()
            }
        datas_aula = gerar_datas(turma, incluir_futuro=False, blocked_dates=blocked)
        aluno_ids = [
            a.id for a in Aluno.query.join(Inscricao).filter(
                Inscricao.turma_id == turma.id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            ).all()
        ]
        if not aluno_ids:
            continue
        for data_str in datas_aula:
            lancados = Frequencia.query.filter(
                Frequencia.turma_id == turma.id,
                Frequencia.data == data_str,
                Frequencia.aluno_id.in_(aluno_ids),
                Frequencia.conceito.isnot(None),
                Frequencia.conceito != '',
            ).count()
            if lancados < len(aluno_ids):
                total_pendencias_frequencia += 1

    agendamentos_ss = []
    try:
        agendamentos_ss = AgendaServicoSocial.query.order_by(AgendaServicoSocial.id.desc()).limit(5).all()
    except Exception:
        pass

    unidade_nome = 'Visão Global'
    if unidade_id:
        u = Unidade.query.get(unidade_id)
        if u:
            unidade_nome = u.nome

    return render_template(
        'dashboard/secretaria.html',
        total_alunos=total_alunos,
        total_turmas=total_turmas,
        total_pendencias_frequencia=total_pendencias_frequencia,
        total_dias_sem_aula=total_dias_sem_aula,
        proximas_datas_vagas=proximas_datas_vagas,
        agendamentos_ss=agendamentos_ss,
        unidade_contexto=unidade_nome,
    )
