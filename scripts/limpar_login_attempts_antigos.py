"""Limpa chaves login_attempts:* antigas da tabela configuracao_sistema.

Uso:
  python scripts/limpar_login_attempts_antigos.py [--aplicar] [--autorizar-principal]
Dry-run por padrão. No banco principal (pautaon) exige --autorizar-principal.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app import create_app, db
from app.models import ConfiguracaoSistema


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true")
    parser.add_argument("--autorizar-principal", action="store_true")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        is_principal = "pautaon" in uri and "ensaio" not in uri
        if is_principal and args.aplicar and not args.autorizar_principal:
            print("ERRO: banco principal exige --autorizar-principal.")
            sys.exit(1)

        chaves = db.session.execute(
            select(ConfiguracaoSistema).where(
                ConfiguracaoSistema.chave.like("login_attempts:%")
            )
        ).scalars().all()

        print(f"chaves login_attempts:* encontradas: {len(chaves)}")
        outras_antes = db.session.execute(
            select(ConfiguracaoSistema).where(
                ~ConfiguracaoSistema.chave.like("login_attempts:%")
            )
        ).scalars().all()
        print(f"demais chaves: {len(outras_antes)}")

        if not args.aplicar:
            print("dry-run: nenhuma alteração.")
            return

        # apagar somente essas, na mesma transação
        for c in chaves:
            db.session.delete(c)
        db.session.commit()

        outras_depois = db.session.execute(
            select(ConfiguracaoSistema).where(
                ~ConfiguracaoSistema.chave.like("login_attempts:%")
            )
        ).scalars().all()
        print(f"apagadas: {len(chaves)}")
        print(f"demais chaves após: {len(outras_depois)}")
        if len(outras_antes) != len(outras_depois):
            print("ALERTA: contagem de demais chaves mudou!")
        else:
            print("demais chaves preservadas.")


if __name__ == "__main__":
    main()
