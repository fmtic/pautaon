import json
from app import create_app
from config import Config

app = create_app(Config)

with app.app_context():
    from app.models import Aluno
    a = Aluno.query.get(1424)
    if not a:
        print('NOT_FOUND')
    else:
        print(json.dumps({'id': a.id, 'nome': a.nome, 'socioeconomico_json': a.socioeconomico_json}, ensure_ascii=False))
