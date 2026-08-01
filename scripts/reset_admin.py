"""Script utilitário para resetar ou criar um usuário administrador local.

Este helper é reservado para o perfil administrativo local do sistema. Ele
não deve ser usado para contas federadas via LDAP/AD, porque essas contas
são validadas no servidor do domínio e não possuem senha local persistida.

Uso:
    python scripts/reset_admin.py admin@example.com nova_senha
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.database import db
from app.models import User

app = create_app()


def setup_admin(email: str, password: str) -> None:
    with app.app_context():
        user = User.query.filter_by(email=email).first()

        if user:
            print(f"Usuário {email} já existe. Atualizando senha local...")
            user.set_password(password)
            user.role = "admin"
            user.is_ad_user = False
            user.is_active = True
            user.first_login = True
        else:
            print(f"Criando novo usuário administrador local: {email}")
            user = User(
                name="Administrador",
                email=email,
                role="admin",
                is_ad_user=False,
                is_active=True,
                first_login=True,
            )
            user.set_password(password)
            db.session.add(user)

        try:
            db.session.commit()
            print("Configuração concluída com sucesso.")
            print(f"E-mail: {email}")
            print("Troca de senha obrigatória no próximo login.")
        except Exception as exc:
            db.session.rollback()
            print(f"Erro ao salvar no banco: {exc}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("Uso: python scripts/reset_admin.py admin@example.com nova_senha")

    setup_admin(sys.argv[1], sys.argv[2])

