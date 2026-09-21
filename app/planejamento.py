from flask import Blueprint, request, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from app.database import db
from app.models import ConfiguracaoSistema, Turma

bp_planejamento = Blueprint("planejamento", __name__)

@bp_planejamento.route("/configurar-conselho", methods=["POST"])
@login_required
def salvar_configuracao_conselho():
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    inicio = request.form.get("inicio_conselho")
    fim = request.form.get("fim_conselho")

    if inicio and fim:
        try:
            for chave, valor in [("inicio_conselho", inicio), ("fim_conselho", fim)]:
                conf = ConfiguracaoSistema.query.filter_by(chave=chave).first()
                if not conf:
                    conf = ConfiguracaoSistema(chave=chave)
                    db.session.add(conf)
                conf.valor = valor

            db.session.commit()
            flash("Parâmetros do conselho gravados de forma segura!", "success")
        except Exception as e:
            from app.utils.errors import flash_and_log
            db.session.rollback()
            flash_and_log(e, location='planejamento.salvar_configuracao_conselho', hint='db')

    return redirect(url_for("registros.planejamento"))

@bp_planejamento.route("/turma/alternar-conselho/<int:turma_id>", methods=["POST"])
@login_required
def alternar_conselho(turma_id):
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    try:
        turma = Turma.query.get_or_404(turma_id)
        turma.conselho_concluido = not turma.conselho_concluido
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash("Erro ao salvar mudança de Status do conselho.", "danger")

    return redirect(url_for("registros.planejamento"))