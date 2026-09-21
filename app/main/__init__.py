"""
Pacote de rotas principais (portal de entrada, painéis por perfil e troca de unidade).

Mantém um único blueprint público ("main") e distribui a implementação por
sub-módulos, seguindo o mesmo padrão já usado no pacote `registros`.
"""

from flask import Blueprint

bp = Blueprint("main", __name__)

# Importa os módulos após a criação do blueprint para registrar as rotas.
from . import home, dashboard, secretaria, unidade  # noqa: E402,F401
