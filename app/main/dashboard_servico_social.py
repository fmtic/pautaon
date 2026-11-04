"""Dashboard do perfil serviço social: indicadores gerais e agenda recente."""

from datetime import date

from flask import flash, render_template, request

from app.models import AgendaServicoSocial, Aluno, Turma
from app.utils.logica import get_unidade_id


def render_dashboard_servico_social():
    """Painel com totais gerais e os últimos agendamentos do serviço social."""
    cat_filtro = request.args.get('categoria')
    total_alunos = total_turmas = 0
    ultimos = []
    try:
        unidade_id = get_unidade_id()
        q_alunos = Aluno.query.filter_by(ativo=True)
        if unidade_id:
            q_alunos = q_alunos.filter_by(unidade_id=unidade_id)
        total_alunos = q_alunos.count()

        q_turmas = Turma.query.filter_by(ativo=True)
        if unidade_id:
            q_turmas = q_turmas.filter_by(unidade_id=unidade_id)
        total_turmas = q_turmas.count()

        query = AgendaServicoSocial.query
        if cat_filtro and cat_filtro != 'Limpar Filtros':
            query = query.filter_by(categoria=cat_filtro)
        ultimos = query.order_by(AgendaServicoSocial.id.desc()).limit(10).all()

    except Exception:
        flash("Erro ao carregar dados do painel.", "warning")

    return render_template(
        'dashboard/servico_social.html',
        total_alunos=total_alunos,
        total_turmas=total_turmas,
        ano_atual=date.today().year,
        ultimos_agendamentos=ultimos,
        categoria_ativa=cat_filtro,
    )
