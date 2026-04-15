"""
Pacote de rotas do domínio de registros.

Mantém um único blueprint público e distribui a implementação por submódulos.
"""

from flask import Blueprint

bp = Blueprint("registros", __name__)

# Importa os módulos após a criação do blueprint para registrar as rotas.
from . import alunos, core, periodos, servico_social, turmas  # noqa: E402,F401
