from flask import redirect, render_template, url_for

from . import bp


@bp.route("/")
def home():
    """Portal de entrada: delega ao login, fonte única da tela inicial."""
    return redirect(url_for("auth.login"))


@bp.route("/politica_privacidade")
def politica_privacidade():
    """Exibe a política de privacidade."""
    return render_template("termos/politica_privacidade.html")


@bp.route("/termos_servico")
def termos_servico():
    """Exibe os termos de serviço."""
    return render_template("termos/termos_servico.html")
