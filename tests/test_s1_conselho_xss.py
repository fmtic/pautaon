"""XSS no nome do período de conselho (S1-07).

O botão de edição interpolava `'{{ c.nome }}'` dentro de um `onclick`. O Jinja
escapa a aspa como `&#39;`, mas o parser HTML decodifica a entidade antes de
entregar o atributo ao JS — um nome `x');alert(1);//` fechava a string e
executava código. Agora o nome viaja em `data-nome` (atributo, onde a entidade
fica escapada) e o listener lê o dataset.
"""

import re
from datetime import date

import pytest

from app import db
from app.models import PeriodoConselho, PeriodoLetivo, Unidade, User
from _helpers import login_as


@pytest.fixture
def conselhos(app):
    with app.app_context():
        unidade = Unidade(nome="Unidade S1-07", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="2026.1",
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        admin = User(
            name="Admin S1-07",
            email="admin.s1-07@example.com",
            role="admin",
            unidade_id=unidade.id,
            is_active=True,
            first_login=False,
        )
        db.session.add(admin)
        db.session.flush()

        aspas = PeriodoConselho(
            nome="x');alert(1);//",
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 2),
            periodo_letivo_id=periodo.id,
            unidade_id=unidade.id,
        )
        script = PeriodoConselho(
            nome="<script>alert(2)</script>",
            data_inicio=date(2026, 7, 1),
            data_fim=date(2026, 7, 2),
            periodo_letivo_id=periodo.id,
            unidade_id=unidade.id,
        )
        db.session.add_all([aspas, script])
        db.session.commit()

        return {
            "unidade": unidade.id,
            "admin": admin.id,
            "aspas": aspas.nome,
            "script": script.nome,
        }


@pytest.fixture
def pagina(app, client, conselhos):
    login_as(client, conselhos["admin"], conselhos["unidade"])
    resposta = client.get("/informacoes")
    assert resposta.status_code == 200
    return resposta.get_data(as_text=True)


def test_nome_com_aspas_nao_entra_em_string_js(pagina):
    # O valor escapado está no atributo data-nome...
    assert 'data-nome="x&#39;);alert(1);//"' in pagina
    # ...e o padrão vulnerável (interpolação dentro do onclick) não existe mais.
    assert "onclick=\"editConselho(" not in pagina
    assert "x');alert(1);//" not in pagina


def test_nome_com_script_renderiza_escapado(pagina):
    assert 'data-nome="&lt;script&gt;alert(2)&lt;/script&gt;"' in pagina
    assert "<script>alert(2)</script>" not in pagina


def test_botao_de_edicao_usa_listener_com_dataset(pagina):
    assert 'class="btn btn-sm btn-outline-primary border-0 js-editar-conselho"' in pagina
    assert re.search(r"querySelectorAll\('\.js-editar-conselho'\)", pagina)
    assert "botao.addEventListener('click'" in pagina


def test_id_do_conselho_segue_em_atributo_numerico(app, client, conselhos):
    login_as(client, conselhos["admin"], conselhos["unidade"])
    pagina = client.get("/informacoes").get_data(as_text=True)

    ids = re.findall(r'data-conselho-id="(\d+)"', pagina)
    assert ids, "nenhum botão com data-conselho-id"
    assert all(ident.isdigit() for ident in ids)
