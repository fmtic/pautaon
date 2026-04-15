import click
from flask import Flask

from app.database import db


def initialize_database() -> None:
    """
    Cria as tabelas conhecidas no banco atual.

    Mantém o comportamento simples do projeto original, mas remove a migração
    implícita durante import. A evolução natural daqui é Alembic/Flask-Migrate.
    """
    db.create_all()


def ensure_admin_user(
    *,
    email: str,
    password: str,
    name: str = "Administrador",
    role: str = "admin",
    force_reset: bool = True,
) -> bool:
    """Cria o primeiro usuário administrador quando ele ainda não existe."""
    from app.models import User

    existing_admin = User.query.filter_by(role=role).first()
    if existing_admin:
        return False

    admin = User(
        name=name,
        email=email,
        role=role,
        is_active=True,
        first_login=force_reset,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    return True


def register_bootstrap_commands(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Inicializa o schema atual do banco."""
        initialize_database()
        click.echo("Banco inicializado com a estrutura atual.")

    @app.cli.command("seed-admin")
    @click.option("--email", default=None, help="E-mail do administrador inicial.")
    @click.option("--password", default=None, help="Senha do administrador inicial.")
    def seed_admin_command(email: str | None, password: str | None) -> None:
        """Cria o admin inicial apenas quando solicitado explicitamente."""
        admin_email = email or app.config["ADMIN_EMAIL"]
        admin_password = password or app.config["ADMIN_DEFAULT_PASSWORD"]

        if not admin_password:
            raise click.ClickException(
                "Defina ADMIN_DEFAULT_PASSWORD no ambiente ou via --password."
            )

        created = ensure_admin_user(
            email=admin_email,
            password=admin_password,
            name=app.config["ADMIN_NAME"],
            force_reset=app.config["ADMIN_FORCE_PASSWORD_CHANGE"],
        )
        if created:
            click.echo(f"Administrador inicial criado para {admin_email}.")
        else:
            click.echo("Já existe um administrador cadastrado; nenhuma alteração foi feita.")

