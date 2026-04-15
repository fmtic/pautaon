import sys
import os

# Adiciona o diretório pai ao path para importar os módulos do app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database import db
from models import Unidade, User, Turma, Aluno, Frequencia, RegistroAula, TemaAula, Nivel, ConfiguracaoSistema, ConselhoClasse, ConselhoResposta, LogAcao, Transferencia, Inscricao
from sqlalchemy import text, inspect

def migrate():
    with app.app_context():
        inspector = inspect(db.engine)
        
        # 1. Garante que as novas colunas existam no SQLite
        # (O setup_database no app.py já faz parte disso, mas reforçamos aqui)
        tables = [
            ('user', 'unidade_id', 'INTEGER'),
            ('user', 'first_login', 'BOOLEAN DEFAULT 1'),  # Adiciona coluna first_login com padrão True
            ('turma', 'unidade_id', 'INTEGER'),
            ('aluno', 'unidade_id', 'INTEGER'),
            ('frequencia', 'unidade_id', 'INTEGER'),
            ('registro_aula', 'unidade_id', 'INTEGER'),
            ('tema_aula', 'unidade_id', 'INTEGER'),
            ('registro', 'unidade_id', 'INTEGER'),
            ('nivel', 'unidade_id', 'INTEGER'),
            ('configuracao_sistema', 'unidade_id', 'INTEGER'),
            ('conselho_classe', 'unidade_id', 'INTEGER'),
            ('conselho_resposta', 'unidade_id', 'INTEGER'),
            ('log_acao', 'unidade_id', 'INTEGER'),
            ('inscricoes', 'ativo', 'BOOLEAN DEFAULT 1'),
            ('inscricoes', 'data_desativacao', 'DATETIME'),
            ('inscricoes', 'motivo_desativacao', 'VARCHAR(50)')
        ]

        # Criar tabela Unidade primeiro se não existir
        db.create_all()

        for table, col, col_type in tables:
            columns = [c['name'] for c in inspector.get_columns(table)]
            if col not in columns:
                print(f"Adding {col} to {table}...")
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        
        db.session.commit()

        # 2. Criar a unidade padrão "NIT"
        nit = Unidade.query.filter_by(nome="NIT").first()
        if not nit:
            nit = Unidade(nome="NIT")
            db.session.add(nit)
            db.session.commit()
            print("✅ Unidade 'NIT' criada.")
        else:
            print("ℹ️ Unidade 'NIT' já existe.")

        nit_id = nit.id

        # 3. Atualizar todos os registros órfãos para a unidade NIT
        models_to_update = [
            User, Turma, Aluno, Frequencia, RegistroAula, 
            TemaAula, Nivel, ConfiguracaoSistema, 
            ConselhoClasse, ConselhoResposta, LogAcao
        ]

        for model in models_to_update:
            # Seleciona registros onde unidade_id é nulo
            # Para User e LogAcao, o nulo é permitido, mas os atuais existentes 
            # provavelmente devem ir para NIT conforme o pedido do usuário
            count = model.query.filter(model.unidade_id == None).count()
            if count > 0:
                model.query.filter(model.unidade_id == None).update({model.unidade_id: nit_id})
                print(f"📦 {count} registros de {model.__name__} migrados para NIT.")
        
        db.session.commit()
        print("\n🚀 Migração concluída com sucesso!")

if __name__ == "__main__":
    migrate()
