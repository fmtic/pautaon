"app/relatorios/__init__.py"

"""
Pacote de rotas do domínio de relatórios.

Mantém um único blueprint público ("relatorios") e distribui a implementação
por submódulos.
"""

from flask import Blueprint

bp_relatorios = Blueprint(
    "relatorios",
    __name__,
    url_prefix="/relatorios",
)


# Importa os módulos após a criação do blueprint para registrar as rotas.
from . import geral, alunos, conselho  # noqa: E402,F401
from . import bi_routes  # noqa: E402,F401
from . import painel_pedagogico  # noqa: E402,F401
