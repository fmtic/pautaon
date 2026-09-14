"""
Pacote de rotas do domínio de relatórios.

Mantém um único blueprint público ("relatorios") e distribui a implementação
por submódulos, seguindo o mesmo padrão já usado no pacote `registros`.
"""

from flask import Blueprint

bp_relatorios = Blueprint("relatorios", __name__, url_prefix="/relatorios")

# Importa os módulos após a criação do blueprint para registrar as rotas.
from . import geral, alunos, conselho  # noqa: E402,F401
