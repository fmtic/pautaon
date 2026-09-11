import json
from app import create_app
from config import Config

app = create_app(Config)

with app.app_context():
    from app.models import Aluno
    total = 0
    presente = 0
    verdadeiros = 0
    exemplos = []
    for a in Aluno.query.order_by(Aluno.id.desc()).all():
        total += 1
        socio = a.socioeconomico_json or {}
        if 'vulnerabilidade_social' in socio:
            presente += 1
            if socio.get('vulnerabilidade_social'):
                verdadeiros += 1
                if len(exemplos) < 10:
                    exemplos.append({'id': a.id, 'nome': a.nome, 'vulnerabilidade_social': socio.get('vulnerabilidade_social')})
    print(json.dumps({'total_alunos': total, 'presente_chave': presente, 'valor_true': verdadeiros, 'exemplos_true': exemplos}, ensure_ascii=False))
