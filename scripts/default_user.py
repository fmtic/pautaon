"""Compatibilidade com o fluxo antigo de provisionamento local.

Este arquivo é mantido apenas como ponte para o fluxo explícito de criação
administrativa local, sem credenciais hardcoded dentro do banco. A fonte de
verdade para o bootstrap do administrador é o comando `flask --app run seed-admin`.
"""

raise SystemExit(
    "Use 'flask --app run seed-admin' ou 'python scripts/reset_admin.py <email> <senha>'."
)
