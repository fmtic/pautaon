"""Troca do contexto de unidade ativa na sessão do usuário."""

from flask import abort, flash, redirect, session, url_for
from flask_login import current_user, login_required

from app.models import Unidade

from . import bp


@bp.route("/trocar-unidade/<int:id>")
@login_required
def trocar_unidade(id):
    if current_user.role not in ["admin", "gerencia"]:
        abort(403)

    if id == 0:
        session.pop("unidade_id", None)
        flash("Visão Global (Todas as Unidades) ativada.", "success")
    else:
        uni = Unidade.query.get(id)
        if not uni or not uni.ativo:
            abort(404)
        session["unidade_id"] = id
        flash(f"Você agora está na Unidade {uni.nome}", "info")
    return redirect(url_for("main.painel"))
