"""Ambiente de execução do Alembic integrado ao Flask-Migrate.

Este arquivo é carregado pelo Alembic em todos os comandos de migration.
A integração com o Flask garante que:
  - A URL do banco seja lida do Config da aplicação (não do alembic.ini).
  - Os modelos SQLAlchemy sejam importados antes de gerar migrações automáticas.
  - Migrações online (com banco conectado) e offline (SQL puro) sejam suportadas.
"""
from __future__ import annotations

import logging
from logging.config import fileConfig

from flask import current_app
from alembic import context

# ---------------------------------------------------------------------------
# Configuração de log do Alembic
# ---------------------------------------------------------------------------
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_engine():
    """Retorna a engine SQLAlchemy registrada no app Flask atual."""
    try:
        # Flask-SQLAlchemy >= 3.x
        return current_app.extensions["sqlalchemy"].engine
    except (KeyError, AttributeError):
        return current_app.extensions["sqlalchemy"].db.engine


def get_engine_url():
    """Retorna a URL de conexão da engine, sem exibir a senha em logs."""
    try:
        return get_engine().url.render_as_string(hide_password=False)
    except AttributeError:
        return str(get_engine().url)


# Substitui a URL do alembic.ini pela URL real do app Flask.
config.set_main_option("sqlalchemy.url", get_engine_url())

# Importa os modelos para que o Alembic possa comparar o schema atual
# com os metadados e detectar alterações (autogenerate).
target_db = current_app.extensions["sqlalchemy"]

# ---------------------------------------------------------------------------
# Helpers de metadata
# ---------------------------------------------------------------------------

def get_metadata():
    """Retorna os metadados do banco registrados no SQLAlchemy."""
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline() -> None:
    """Executa migrations no modo offline (gera SQL puro sem conectar ao banco).

    Útil para revisar o SQL antes de aplicar ou para ambientes onde a
    conexão direta ao banco não está disponível.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrations no modo online (conecta ao banco e aplica as alterações)."""

    def process_revision_directives(context, revision, directives):
        """Evita gerar arquivo de migration vazio quando não há alterações."""
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("Nenhuma alteração de schema detectada — migration vazia descartada.")

    conf_args = current_app.extensions["migrate"].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
