# ruff: noqa: F811
"""Conselho — a etapa e o foco das perguntas sobrevivem ao salvar/excluir.

As abas de `conselho/perguntas.html` (etapa INICIAL/PERCURSO/FINAL e foco
TURMA/ALUNO) antes reabriam sempre em INICIAL/TURMA. Agora o estado ativo
vive na querystring (`?etapa=...&foco=...`), o POST de salvar volta para a
aba da pergunta gravada e a exclusão volta para a aba de origem.
"""

import re
from urllib.parse import parse_qs, urlparse

from _helpers import login_as
from test_conselho_oferta import app, client  # noqa: F401

from app import db
from app.models import PerguntaConselho, Unidade, User

ETAPAS = ("inicial", "percurso", "final")


def _cenario(app, role="pedagogico"):
    with app.app_context():
        unidade = Unidade(nome="Unidade CPQ", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        user = User(
            name="Pedagogico CPQ", email="ped.cpq@x.com", role=role,
            first_login=False, unidade_id=unidade.id,
        )
        user.set_password("SenhaLocal!123")
        db.session.add(user)
        db.session.commit()
        return {"un": unidade.id, "user": user.id}


def _pergunta(etapa="INICIAL", tipo="TURMA", texto="Pergunta CPQ"):
    pergunta = PerguntaConselho(
        etapa=etapa, tipo=tipo, texto=texto, opcoes="", ativo=True,
    )
    db.session.add(pergunta)
    db.session.commit()
    return pergunta.id


def _classes(corpo, elemento_id):
    tag = re.search(r'<[a-z]+[^>]*\bid="%s"[^>]*>' % re.escape(elemento_id), corpo)
    assert tag, f"elemento #{elemento_id} nao renderizou"
    classes = re.search(r'class="([^"]*)"', tag.group(0))
    return classes.group(1).split() if classes else []


def _assert_tela(corpo, etapa, foco):
    """Só a etapa/foco pedidos ficam ativos."""
    for nome in ETAPAS:
        if nome == etapa:
            assert "active" in _classes(corpo, f"tab-{nome}")
            assert {"show", "active"} <= set(_classes(corpo, f"pane-{nome}"))
        else:
            assert "active" not in _classes(corpo, f"tab-{nome}")
            assert "show" not in _classes(corpo, f"pane-{nome}")

    outro = "aluno" if foco == "turma" else "turma"
    assert "active" in _classes(corpo, f"pills-{foco}-tab-{etapa}")
    assert {"show", "active"} <= set(_classes(corpo, f"pills-{foco}-{etapa}"))
    assert "active" not in _classes(corpo, f"pills-{outro}-tab-{etapa}")


def _query(location):
    return parse_qs(urlparse(location).query)


def test_salvar_nova_pergunta_abre_aba_dela(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    resposta = client.post(
        "/conselho/pergunta/salvar",
        data={
            "etapa": "PERCURSO", "tipo": "ALUNO",
            "texto": "Como foi o percurso?", "opcoes": "",
        },
    )
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {
        "etapa": ["percurso"], "foco": ["aluno"],
    }
    corpo = client.get(resposta.headers["Location"]).get_data(as_text=True)
    _assert_tela(corpo, "percurso", "aluno")
    assert "Como foi o percurso?" in corpo


def test_editar_pergunta_volta_para_a_aba_nova(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    with app.app_context():
        pergunta_id = _pergunta("INICIAL", "TURMA", "Pergunta original")

    resposta = client.post(
        "/conselho/pergunta/salvar",
        data={
            "id": str(pergunta_id), "etapa": "FINAL", "tipo": "TURMA",
            "texto": "Pergunta final", "opcoes": "",
        },
    )
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {
        "etapa": ["final"], "foco": ["turma"],
    }
    _assert_tela(
        client.get(resposta.headers["Location"]).get_data(as_text=True),
        "final", "turma",
    )


def test_excluir_pergunta_volta_para_a_aba_de_origem(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    with app.app_context():
        pergunta_id = _pergunta("FINAL", "ALUNO", "Pergunta a excluir")

    resposta = client.post(
        f"/conselho/pergunta/excluir/{pergunta_id}",
        data={"aba_etapa": "final", "aba_foco": "aluno"},
    )
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {
        "etapa": ["final"], "foco": ["aluno"],
    }
    with app.app_context():
        assert db.session.get(PerguntaConselho, pergunta_id).ativo is False
    corpo = client.get(resposta.headers["Location"]).get_data(as_text=True)
    _assert_tela(corpo, "final", "aluno")
    assert "Pergunta a excluir" not in corpo


def test_excluir_sem_contexto_usa_aba_padrao(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    with app.app_context():
        pergunta_id = _pergunta("INICIAL", "TURMA", "Sem contexto")

    resposta = client.post(f"/conselho/pergunta/excluir/{pergunta_id}")
    assert resposta.status_code == 302
    assert _query(resposta.headers["Location"]) == {}


def test_get_com_etapa_e_foco_abre_a_aba(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    corpo = client.get("/conselho/perguntas?etapa=final&foco=aluno").get_data(
        as_text=True
    )
    _assert_tela(corpo, "final", "aluno")


def test_parametros_invalidos_caem_no_padrao(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    corpo = client.get("/conselho/perguntas?etapa=qualquer&foco=qualquer").get_data(
        as_text=True
    )
    _assert_tela(corpo, "inicial", "turma")


def test_sem_parametros_mantem_padrao(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    corpo = client.get("/conselho/perguntas").get_data(as_text=True)
    _assert_tela(corpo, "inicial", "turma")


def test_professor_nao_gerencia_perguntas(app, client):
    ids = _cenario(app, role="professor")
    login_as(client, ids["user"], ids["un"])
    assert client.get("/conselho/perguntas").status_code == 403
    assert client.post(
        "/conselho/pergunta/salvar",
        data={"etapa": "INICIAL", "tipo": "TURMA", "texto": "X"},
    ).status_code == 403
