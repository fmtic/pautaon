"""Migração aditiva da situação escolar; segura para SQLite e PostgreSQL."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.database import db
from sqlalchemy import inspect, text
from app.models import SituacaoEscolar


def add_column_if_missing(table_name: str, column_name: str, column_type: str) -> bool:
    inspector = inspect(db.engine)
    existing_columns = {column['name'] for column in inspector.get_columns(table_name)}
    if column_name in existing_columns:
        return False

    with db.engine.begin() as connection:
        connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'))
    return True


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        SituacaoEscolar.__table__.create(db.engine, checkfirst=True)
        added_columns = [
            name for name, column_type in (
                ('status', 'VARCHAR(20)'),
                ('status_outro', 'VARCHAR(150)'),
            )
            if add_column_if_missing('situacao_escolar', name, column_type)
        ]
        if added_columns:
            print(f"Colunas adicionadas em situacao_escolar: {', '.join(added_columns)}.")
        else:
            print('Tabela situacao_escolar criada ou já existente; nenhum dado foi alterado.')
