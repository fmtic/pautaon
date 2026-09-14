from flask import render_template

from . import bp


@bp.route("/")
def home():
    """Portal de Entrada do Sistema."""
    return render_template("login.html")
