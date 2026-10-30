"""A rota pública de teste de e-mail foi removida (S1-04).

`GET /teste-email` enviava HTML para o endereço do parâmetro `para`, sem
autenticação e sem limite (relay de e-mail). Foi removida junto com o módulo
`app/main/rota_disparo_email.py` e o registro no blueprint.
"""

from app.database import db
from app.models import User
from _helpers import login_as


def test_endpoint_nao_esta_registrado(app):
    regras = {regra.rule for regra in app.url_map.iter_rules()}
    assert "/teste-email" not in regras
    assert not any(
        endpoint.startswith("main.teste") for endpoint in app.view_functions
    )


def test_teste_email_retorna_404_para_anonimo(client):
    resposta = client.get("/teste-email?para=alvo@example.com")
    assert resposta.status_code == 404


def test_teste_email_retorna_404_para_autenticado(client, app):
    with app.app_context():
        admin = User(
            name="Admin S1-04",
            email="admin.s1-04@example.com",
            role="admin",
            first_login=False,
        )
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id

    login_as(client, admin_id)

    resposta = client.get("/teste-email?para=alvo@example.com")
    assert resposta.status_code == 404
