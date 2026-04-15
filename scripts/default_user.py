"""
Compatibilidade com o fluxo antigo.

Este script foi mantido apenas para apontar para o novo fluxo explícito de
criação de administrador, evitando credenciais hardcoded dentro da base.
"""

raise SystemExit(
    "Use 'flask --app run seed-admin' ou 'python scripts/reset_admin.py <email> <senha>'."
)
