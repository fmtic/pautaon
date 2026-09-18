"""Dashboard consolidado usado pela secretaria (e demais perfis com acesso)."""

from datetime import date

from flask import abort, render_template
from flask_login import current_user, login_required

from app.database import db
from app.models import (
    AgendaServicoSocial,
    Aluno,
    DiaBloqueado,
    PeriodoLetivo,
    Turma,
    Unidade,
)
from app.utils.frequencia import contar_pendencias_frequencia
from app.utils.logica import get_unidade_id

from . import bp


@bp.route('/dashboard/secretaria')
@login_required
def dashboard_secretaria():
    if current_user.role not in [
        'admin', 'pedagogico', 'secretaria', 'gerencia', 'servico_social'
    ]:
        abort(403)

    unidade_id = get_unidade_id()

    # --- Contadores básicos -------------------------------------------------
    q_alunos = Aluno.query.filter_by(ativo=True)
    q_turmas = Turma.query.filter_by(ativo=True)
    if unidade_id:
        q_alunos = q_alunos.filter_by(unidade_id=unidade_id)
        q_turmas = q_turmas.filter_by(unidade_id=unidade_id)

    total_alunos = q_alunos.count()
    total_turmas = q_turmas.count()

    # --- Períodos ativos (escopados por unidade quando aplicável) -----------
    q_periodos = PeriodoLetivo.query.filter_by(ativo=True)
    if unidade_id:
        q_periodos = q_periodos.filter_by(unidade_id=unidade_id)
    periodo_ids_ativos = [p.id for p in q_periodos.all()]

    # --- Próximos dias sem aula --------------------------------------------
    hoje = date.today()
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

    # --- Pendências de frequência (usa helper compartilhado) ---------------
    turmas_ativas = q_turmas.all()
    total_pendencias_frequencia = contar_pendencias_frequencia(turmas_ativas)

    # --- Últimos agendamentos do Serviço Social ----------------------------
    agendamentos_ss = []
    try:
        agendamentos_ss = (
            AgendaServicoSocial.query
            .order_by(AgendaServicoSocial.id.desc())
            .limit(5)
            .all()
        )
    except Exception:
        # Agenda é opcional; não deve derrubar o dashboard.
        pass

    # --- Nome da unidade ---------------------------------------------------
    unidade_nome = 'Visão Global'
    if unidade_id:
        u = db.session.get(Unidade, unidade_id)
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