"""
Pacote de rotas principais (portal de entrada, painéis por perfil e troca de unidade).

Mantém um único blueprint público ("main") e distribui a implementação por
sub-módulos, seguindo o mesmo padrão já usado no pacote `registros`.
"""

from flask import Blueprint

bp = Blueprint("main", __name__)

# Importa os módulos após a criação do blueprint para registrar as rotas.
# A rota pública de teste de e-mail (`GET /teste-email`) foi removida no S1-04:
# permitia enviar e-mail para qualquer destinatário sem autenticação.
from . import home, dashboard, secretaria, unidade
