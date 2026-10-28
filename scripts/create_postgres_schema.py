import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app import create_app
from app.database import db

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não encontrado. Defina DATABASE_URL no ambiente ou em um arquivo .env."
    )

OUTPUT_SQL = Path(__file__).resolve().parent / "postgres_schema.sql"


def ensure_models_imported() -> None:
    # Importa os modelos para registrar todas as tabelas no metadata do SQLAlchemy.
    import app.models  # noqa: F401


def generate_schema_sql(path: Path) -> None:
    ensure_models_imported()

    with path.open("w", encoding="utf-8") as out_file:
        out_file.write("-- SQL de criação de schema para PostgreSQL gerado a partir dos modelos do app\n")
        out_file.write("-- Execute no psql ou no cliente SQL do seu servidor PostgreSQL.\n\n")

        for table in db.metadata.sorted_tables:
            ddl = CreateTable(table).compile(dialect=postgresql.dialect())
            out_file.write(str(ddl).rstrip())
            out_file.write(";\n\n")

    print(f"Arquivo de schema gerado em: {path}")


def create_tables_in_database() -> None:
    # Guard (H3a-P0): o script lê o DATABASE_URL do .env, que normalmente
    # aponta para o banco principal — criação direta só com opt-in explícito;
    # a evolução de schema do principal é por `flask db upgrade`.
    if os.getenv("PAUTAON_ALLOW_CREATE_ALL") != "1":
        raise RuntimeError(
            "Criação direta de tabelas está bloqueada para proteger bancos "
            "existentes (use `flask db upgrade`). Para criar um banco novo a "
            "partir dos modelos, defina PAUTAON_ALLOW_CREATE_ALL=1 e rode o "
            "script novamente."
        )
    engine = create_engine(DATABASE_URL, future=True)
    ensure_models_imported()
    db.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso no banco PostgreSQL configurado.")


if __name__ == "__main__":
    print("Gerando SQL de criação de schema para PostgreSQL...")
    generate_schema_sql(OUTPUT_SQL)
    print("Criando tabelas no PostgreSQL conectado...")
    create_tables_in_database()
    print("Pronto.")
