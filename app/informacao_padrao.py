from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.exceptions import HTTPException

from app.database import db
from app.services.informacao_padrao import get_informacao_padrao_values, upsert_informacao_padrao
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
        register_security_log("Informacao Padrao", "Administrador atualizou dados institucionais padrão.")
        flash("Informações padrão atualizadas com sucesso.", "success")
    except HTTPException:
        # AJ5-C (E3b): o acesso a `request.form` dentro de
        # `upsert_informacao_padrao` pode levantar 413 (MAX_CONTENT_LENGTH) —
        # erro HTTP legítimo vai ao handler global (flash amigável com o
        # teto, AJ5-B) em vez de virar a mensagem genérica do except abaixo.
        raise
    except ValueError:
        db.session.rollback()
        current_app.logger.warning("Dados inválidos ao atualizar informações padrão.")
        flash("Dados inválidos para atualizar as informações institucionais.", "warning")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao atualizar informacoes padrao.")
        flash("Nao foi possivel salvar as informações padrão.", "danger")

    return redirect(url_for("informacao_padrao.painel_informacao_padrao"))
