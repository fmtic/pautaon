"""Pacote do Painel Pedagógico.

Expõe as rotas para registro no blueprint `relatorios`.
Importante: importar este pacote DEPOIS que `bp_relatorios` já foi criado
em `app/relatorios/__init__.py`.
"""

from . import rota

__all__ = ["rota"]