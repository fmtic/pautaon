from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.database import db
from app.informacao_padrao import get_informacao_padrao_values, upsert_informacao_padrao
from app.services.auth_service import register_security_log

bp = Blueprint("informacao_padrao", __name__)


@bp.route("/admin/informacao-padrao", methods=["GET"])
@login_required
def painel_informacao_padrao():
    if current_user.role != "admin":
        abort(403)

    return render_template(
        "admin/informacao_padrao.html",
        informacao=get_informacao_padrao_values(),
    )


@bp.route("/admin/informacao-padrao", methods=["POST"])
@login_required
def salvar_informacao_padrao():
    if current_user.role != "admin":
        abort(403)

    try:
        upsert_informacao_padrao(request.form, request.files)
        db.session.commit()
        register_security_log("Informacao Padrao", "Administrador atualizou dados institucionais padrao.")
        flash("Informacoes padrao atualizadas com sucesso.", "success")
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao atualizar informacoes padrao.")
        flash("Nao foi possivel salvar as informacoes padrao.", "danger")

    return redirect(url_for("informacao_padrao.painel_informacao_padrao"))
