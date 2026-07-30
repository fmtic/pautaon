import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
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
    url = make_url(DATABASE_URL)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    engine = create_engine(url, future=True)
    ensure_models_imported()
    db.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso no banco PostgreSQL configurado.")


if __name__ == "__main__":
    print("Gerando SQL de criação de schema para PostgreSQL...")
    generate_schema_sql(OUTPUT_SQL)
    print("Criando tabelas no PostgreSQL conectado...")
    create_tables_in_database()
    print("Pronto.")
