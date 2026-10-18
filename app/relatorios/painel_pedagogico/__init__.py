"""Pacote do Painel Pedagógico.

Expõe `painel_pedagogico` para registro no blueprint `relatorios`.
Importante: importar este pacote DEPOIS que `bp_relatorios` já foi criado
em `app/relatorios/__init__.py`.
"""

from . import rota

__all__ = ["painel_pedagogico"]