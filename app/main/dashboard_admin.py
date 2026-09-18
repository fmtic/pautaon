"""Dashboard dos perfis administrativo, gerencial e pedagógico."""

from flask import current_app, flash, render_template
from sqlalchemy import func

from app.database import db
from app.models import Aluno, Turma, User
from app.models.enums import UserRole
from app.utils.logica import get_unidade_id


def render_dashboard_gerencial():
    """Painel com totais de turmas, alunos e professores (global ou por unidade)."""
    try:
        unidade_id = get_unidade_id()
        if unidade_id:
            total_turmas = Turma.query.filter_by(
                ativo=True, unidade_id=unidade_id
            ).count()
            total_alunos = Aluno.query.filter_by(
                ativo=True, unidade_id=unidade_id
            ).count()
            total_professores = User.query.filter_by(
                role=UserRole.PROFESSOR.value, unidade_id=unidade_id
            ).count()
        else:
            total_turmas = Turma.query.filter_by(ativo=True).count()
            total_alunos = Aluno.query.filter_by(ativo=True).count()
            total_professores = (
                db.session.query(func.count(func.distinct(Turma.professor_id)))
                .filter(Turma.ativo == True)
                .scalar()
                or 0
            )

        return render_template(
            "dashboard/index.html",
            total_turmas=total_turmas,
            total_alunos=total_alunos,
            total_professores=total_professores,
        )
    except Exception:
        current_app.logger.exception(
            "Falha ao computar dados para o dashboard gerencial."
        )
        flash(
            "Erro ao computar dados para o dashboard gerencial. Contate o suporte.",
            "danger",
        )
        return render_template(
            "dashboard/index.html",
            total_turmas=0,
            total_alunos=0,
            total_professores=0,
            show_excel=False,
        )
