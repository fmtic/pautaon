from flask import render_template

from . import bp


@bp.route("/")
def home():
    """Portal de Entrada do Sistema."""
    return render_template("login.html")


@bp.route("/politica_privacidade")
def politica_privacidade():
    """Exibe a política de privacidade."""
    return render_template("termos/politica_privacidade.html")


@bp.route("/termos_servico")
def termos_servico():
    """Exibe os termos de serviço."""
    return render_template("termos/termos_servico.html")
