import json
import sys
from app import create_app
from config import Config

app = create_app(Config)

with app.app_context():
    try:
        from app.models import Aluno
        alunos = Aluno.query.order_by(Aluno.id.desc()).limit(10).all()
        if not alunos:
            print('NO_RECORDS')
            sys.exit(0)
        for a in alunos:
            try:
                socio = a.socioeconomico_json
            except Exception as e:
                socio = f'ERROR_LOADING_JSON: {e}'
            print(json.dumps({'id': a.id, 'nome': a.nome, 'nome_social': a.nome_social, 'socioeconomico_json': socio}, default=str, ensure_ascii=False))
    except Exception as exc:
        print('EXCEPTION', exc)
        raise
