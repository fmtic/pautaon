from flask import Blueprint, request, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from app.database import db
from app.models import ConfiguracaoSistema, Turma
from app.services.turma_curso import ofertas_ativas
from app.utils.logica import get_unidade_id
from app.registros.shared import assert_unidade_context

bp_planejamento = Blueprint("planejamento", __name__)

@bp_planejamento.route("/configurar-conselho", methods=["POST"])
@login_required
def salvar_configuracao_conselho():
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)
    if current_user.role != "admin" and get_unidade_id() is None:
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
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    turma = Turma.query.get_or_404(turma_id)
    unidade_id = get_unidade_id()
    # ETAPA B4: isolamento por unidade vale para todos os perfis, inclusive
    # admin (Visão Global é somente leitura; B3 §4, item 6).
    assert_unidade_context(turma.unidade_id, unidade_id)

    # ETAPA D5.2 (Passo 6): o encerramento do conselho é da OFERTA
    # (TurmaCurso.conselho_concluido, coluna criada na D5.1). Padrão M1:
    # 1 oferta ativa = usa direto; 2+ exige turma_curso_id válido (no POST,
    # também aceita ?oferta= para links já existentes); 0 ofertas recusa —
    # turma sem oferta ativa não abre conselho.
    ativas = ofertas_ativas(turma.id)
    if not ativas:
        flash(
            "Esta turma ainda não possui curso (oferta) ativa — o conselho "
            "não pode ser alterado.",
            "warning",
        )
        return redirect(url_for("registros.planejamento"))

    oferta_id = request.form.get("turma_curso_id", type=int) or request.form.get(
        "oferta_id", type=int
    ) or request.args.get("oferta", type=int)
    if len(ativas) == 1:
        # Mesmo com oferta única, um id enviado explicitamente que não é a
        # oferta ativa da turma é recusado (não cai na oferta silenciosamente).
        if oferta_id is not None and oferta_id != ativas[0].id:
            flash("A oferta enviada não é uma oferta ativa desta turma.", "warning")
            return redirect(url_for("registros.planejamento"))
        oferta = ativas[0]
    else:
        oferta = next((o for o in ativas if o.id == oferta_id), None)
        if oferta is None:
            flash(
                "Selecione o curso (oferta) cujo conselho será alterado.",
                "warning",
            )
            return redirect(url_for("registros.planejamento"))

    try:
        oferta.conselho_concluido = not oferta.conselho_concluido
        # D5.5: a turma não guarda mais o encerramento — ele é exclusivamente
        # da oferta e a visão da turma é derivada na leitura.
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash("Erro ao salvar mudança de Status do conselho.", "danger")

    return redirect(url_for("registros.planejamento"))
