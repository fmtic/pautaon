# ruff: noqa: F811
"""Planejamento — a aba (e os filtros da aba Temas) sobrevivem ao salvar.

Antes, todo POST redirecionava para `/planejamento` e o template reabria
sempre em Temas, porque o estado das pills do Bootstrap vivia apenas no DOM.
Agora o formulário envia a aba num hidden (`aba`), o redirect devolve
`?aba=...` e o GET marca pill/painel ativos; os filtros da lista de temas
(`curso_id`, `q`, `page`) também voltam no redirect.
"""

import re
from urllib.parse import parse_qs, urlparse

from _helpers import login_as

from app import db
from app.models import Curso, TemaAula, Unidade, User

IDS_ABA = {
    "temas": ("pill-temas", "tabTemas"),
    "valores": ("pill-valores", "tabValores"),
    "niveis": ("pill-niveis", "tabNiveis"),
}


def _cenario(app):
    with app.app_context():
        unidade = Unidade(nome="Unidade ABAS", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        admin = User(
            name="Admin ABAS", email="admin.abas@x.com", role="admin",
            first_login=False, unidade_id=unidade.id,
        )
        admin.set_password("SenhaLocal!123")
        db.session.add(admin)
        db.session.flush()
        curso = Curso(nome="Curso ABAS", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        tema = TemaAula(titulo="Tema ABAS", curso_id=curso.id, ativo=True)
        db.session.add(tema)
        db.session.commit()
        return {
            "un": unidade.id, "admin": admin.id,
            "curso": curso.id, "tema": tema.id,
        }


def _classes(corpo, elemento_id):
    tag = re.search(r'<[a-z]+[^>]*\bid="%s"[^>]*>' % elemento_id, corpo)
    assert tag, f"elemento #{elemento_id} nao renderizou"
    classes = re.search(r'class="([^"]*)"', tag.group(0))
    return classes.group(1).split() if classes else []


def _assert_aba(corpo, aba):
    """Só a aba pedida tem pill/painel ativos."""
    for nome, (pill_id, painel_id) in IDS_ABA.items():
        classe_pill = _classes(corpo, pill_id)
        classe_painel = _classes(corpo, painel_id)
        if nome == aba:
            assert "active" in classe_pill, f"pill de {nome} sem active"
            assert {"show", "active"} <= set(classe_painel), (
                f"painel de {nome} sem show active"
            )
        else:
            assert "active" not in classe_pill, f"pill de {nome} ativa indevida"
            assert "show" not in classe_painel, f"painel de {nome} visivel"


def _query(location):
    return parse_qs(urlparse(location).query)


def test_criar_valor_volta_para_aba_valores(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        "/planejamento",
        data={"tipo_post": "valor", "nome_valor": "Alegria", "aba": "valores"},
    )
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {"aba": ["valores"]}
    _assert_aba(client.get(resposta.headers["Location"]).get_data(as_text=True), "valores")


def test_criar_nivel_volta_para_aba_niveis(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        "/planejamento",
        data={"tipo_post": "nivel", "nome_nivel": "Nivel ABAS", "aba": "niveis"},
    )
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {"aba": ["niveis"]}
    _assert_aba(client.get(resposta.headers["Location"]).get_data(as_text=True), "niveis")


def test_criar_tema_fica_na_aba_padrao(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        "/planejamento",
        data={"curso_id": str(ids["curso"]), "titulo": "Tema novo", "aba": "temas"},
    )
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {}
    _assert_aba(client.get(resposta.headers["Location"]).get_data(as_text=True), "temas")


def test_editar_e_inativar_valor_preservam_aba(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    client.post(
        "/planejamento",
        data={"tipo_post": "valor", "nome_valor": "Foco", "aba": "valores"},
    )
    from app.models import ValorEsportista

    with app.app_context():
        valor_id = ValorEsportista.query.filter_by(nome="Foco").one().id

    editar = client.post(
        f"/planejamento/valor/editar/{valor_id}",
        data={"nome_valor": "Foco total", "aba": "valores"},
    )
    assert _query(editar.headers["Location"]) == {"aba": ["valores"]}

    inativar = client.post(
        f"/planejamento/valor/inativar/{valor_id}", data={"aba": "valores"},
    )
    assert _query(inativar.headers["Location"]) == {"aba": ["valores"]}
    _assert_aba(client.get(inativar.headers["Location"]).get_data(as_text=True), "valores")


def test_editar_e_inativar_nivel_preservam_aba(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    client.post(
        "/planejamento",
        data={"tipo_post": "nivel", "nome_nivel": "Nivel X", "aba": "niveis"},
    )
    from app.models import Nivel

    with app.app_context():
        nivel_id = Nivel.query.filter_by(nome="Nivel X").one().id

    editar = client.post(
        f"/planejamento/nivel/editar/{nivel_id}",
        data={"nome_nivel": "Nivel Y", "aba": "niveis"},
    )
    assert _query(editar.headers["Location"]) == {"aba": ["niveis"]}

    inativar = client.post(
        f"/planejamento/nivel/inativar/{nivel_id}", data={"aba": "niveis"},
    )
    assert _query(inativar.headers["Location"]) == {"aba": ["niveis"]}


def test_editar_tema_preserva_filtros_da_lista(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        f"/planejamento/tema/editar/{ids['tema']}",
        data={
            "titulo": "Tema ABAS editado",
            "aba": "temas",
            "filtro_curso": str(ids["curso"]),
            "filtro_q": "ABAS",
            "filtro_page": "2",
        },
    )
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {
        "curso_id": [str(ids["curso"])],
        "q": ["ABAS"],
        "page": ["2"],
    }
    # O filtro realmente volta aplicado na tela.
    corpo = client.get(resposta.headers["Location"]).get_data(as_text=True)
    assert "Tema ABAS editado" in corpo
    assert 'value="ABAS"' in corpo
    _assert_aba(corpo, "temas")


def test_inativar_tema_preserva_filtros(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        f"/planejamento/tema/inativar/{ids['tema']}",
        data={
            "aba": "temas",
            "filtro_curso": str(ids["curso"]),
            "filtro_q": "ABAS",
            "filtro_page": "1",
        },
    )
    assert _query(resposta.headers["Location"]) == {
        "curso_id": [str(ids["curso"])],
        "q": ["ABAS"],
    }


def test_get_com_aba_valores_abre_a_aba(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    corpo = client.get("/planejamento?aba=valores").get_data(as_text=True)
    _assert_aba(corpo, "valores")


def test_aba_invalida_cai_em_temas(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    corpo = client.get("/planejamento?aba=qualquer").get_data(as_text=True)
    _assert_aba(corpo, "temas")


def test_aba_ausente_mantem_temas(app, client):
    """Nenhuma mudança para quem abre /planejamento sem parâmetro."""
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    corpo = client.get("/planejamento").get_data(as_text=True)
    _assert_aba(corpo, "temas")
