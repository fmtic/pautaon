"""Rota central do painel: decide qual dashboard renderizar conforme o perfil do usuário.

A lógica de cada perfil vive em seu próprio módulo (dashboard_admin,
dashboard_professor, dashboard_servico_social) — esta rota é só o roteador.
"""

from flask import abort, redirect, url_for
from flask_login import current_user, login_required

from . import bp
from .dashboard_admin import render_dashboard_gerencial
from .dashboard_professor import render_dashboard_professor
from .dashboard_servico_social import render_dashboard_servico_social


@bp.route("/dashboard")
@login_required
def dashboard():
    """Controlador central do painel do sistema."""
    if current_user.role == "pendente":
        return redirect(url_for("auth.aguardando_aprovacao"))

    if current_user.role == "secretaria":
        return redirect(url_for("main.dashboard_secretaria"))

    if current_user.role in ("admin", "gerencia", "pedagogico"):
        return render_dashboard_gerencial()

    if current_user.role == "professor":
        return render_dashboard_professor()

    if current_user.role == "servico_social":
        return render_dashboard_servico_social()

    abort(403)
