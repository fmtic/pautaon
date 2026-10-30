# ruff: noqa: F811
"""A1 — cadastro de "Valores do Esportista" no planejamento pedagógico.

Cobre: criar/editar/inativar/reativar, nome vazio/duplicado (sem diferenciar
maiúsculas), tamanho, permissões (403), CSRF real e isolamento por unidade.
O valor é um catálogo do planejamento: não interfere em frequência.

Rotas: `registros.planejamento` (POST `tipo_post="valor"`),
`registros.editar_valor` e `registros.inativar_valor`.
"""

from html.parser import HTMLParser

import pytest
from _helpers import login_as

from app import create_app
from app import db as db_module
from app.models import Unidade, User, ValorEsportista
from config import Config


@pytest.fixture
def app_csrf():
    """App com CSRF LIGADO (a fixture padrão da suíte o desliga)."""
    class Cfg(Config):
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    test_app = create_app(Cfg)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        db_module.create_all()
        yield test_app
        db_module.session.remove()
        db_module.drop_all()


def _unidade(nome):
    unidade = Unidade(nome=nome, ativo=True)
    db_module.session.add(unidade)
    db_module.session.flush()
    return unidade


def _usuario(nome, email, role="admin", unidade=None):
    user = User(
        name=nome, email=email, role=role, first_login=False,
        unidade_id=unidade.id if unidade else None,
    )
    user.set_password("SenhaLocal!123")
    db_module.session.add(user)
    db_module.session.flush()
    return user


def _cenario(app):
    with app.app_context():
        un_a = _unidade("Unidade A")
        un_b = _unidade("Unidade B")
        admin_a = _usuario("Admin A", "admin.a@x.com", unidade=un_a)
        admin_b = _usuario("Admin B", "admin.b@x.com", unidade=un_b)
        prof_a = _usuario("Prof A", "prof.a@x.com", role="professor", unidade=un_a)
        db_module.session.commit()
        return {
            "un_a": un_a.id, "un_b": un_b.id,
            "admin_a": admin_a.id, "admin_b": admin_b.id,
            "prof_a": prof_a.id,
        }


def _criar(client, nome, unidade_id, user_id):
    login_as(client, user_id, unidade_id)
    return client.post(
        "/planejamento",
        data={"tipo_post": "valor", "nome_valor": nome},
        follow_redirects=False,
    )


def _obter(app, nome):
    with app.app_context():
        return ValorEsportista.query.filter(
            ValorEsportista.nome.ilike(nome)
        ).first()


def test_cria_edita_inativa_e_reativa(app, client):
    ids = _cenario(app)
    resposta = _criar(client, "Alegria", ids["un_a"], ids["admin_a"])
    assert resposta.status_code == 302

    valor = _obter(app, "Alegria")
    assert valor is not None and valor.ativo is True
    assert valor.unidade_id == ids["un_a"]

    # Editar
    client.post(
        f"/planejamento/valor/editar/{valor.id}",
        data={"nome_valor": "Alegria e foco"},
    )
    assert _obter(app, "Alegria e foco") is not None

    # Inativar / reativar (toggle)
    client.post(f"/planejamento/valor/inativar/{valor.id}")
    with app.app_context():
        assert db_module.session.get(ValorEsportista, valor.id).ativo is False
    client.post(f"/planejamento/valor/inativar/{valor.id}")
    with app.app_context():
        assert db_module.session.get(ValorEsportista, valor.id).ativo is True


def test_bloqueia_nome_vazio(app, client):
    ids = _cenario(app)
    _criar(client, "   ", ids["un_a"], ids["admin_a"])
    with app.app_context():
        assert ValorEsportista.query.count() == 0


def test_bloqueia_duplicado_sem_diferenciar_maiusculas(app, client):
    ids = _cenario(app)
    _criar(client, "Alegria", ids["un_a"], ids["admin_a"])
    _criar(client, "ALEGRIA", ids["un_a"], ids["admin_a"])
    with app.app_context():
        assert ValorEsportista.query.filter_by(unidade_id=ids["un_a"]).count() == 1


def test_bloqueia_nome_acima_de_100(app, client):
    ids = _cenario(app)
    _criar(client, "X" * 101, ids["un_a"], ids["admin_a"])
    with app.app_context():
        assert ValorEsportista.query.count() == 0
    _criar(client, "Y" * 100, ids["un_a"], ids["admin_a"])
    with app.app_context():
        assert ValorEsportista.query.count() == 1


def test_editar_nao_permite_duplicar(app, client):
    ids = _cenario(app)
    _criar(client, "Alegria", ids["un_a"], ids["admin_a"])
    _criar(client, "Foco", ids["un_a"], ids["admin_a"])
    foco = _obter(app, "Foco")

    client.post(
        f"/planejamento/valor/editar/{foco.id}",
        data={"nome_valor": "alegria"},
    )
    assert _obter(app, "Foco") is not None  # renomeação recusada


def test_perfil_sem_permissao_recebe_403(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof_a"], ids["un_a"])
    resposta = client.post(
        "/planejamento", data={"tipo_post": "valor", "nome_valor": "X"},
    )
    assert resposta.status_code == 403


def test_isolamento_por_unidade(app, client):
    ids = _cenario(app)
    _criar(client, "Respeito", ids["un_a"], ids["admin_a"])
    valor_a = _obter(app, "Respeito")
    # Consome o flash da criação (a sessão do client é compartilhada).
    client.get("/planejamento")

    # A unidade B não vê o valor da A no planejamento...
    login_as(client, ids["admin_b"], ids["un_b"])
    corpo = client.get("/planejamento").get_data(as_text=True)
    assert "Respeito" not in corpo

    # ... e não consegue editá-lo (403) nem inativá-lo.
    assert client.post(
        f"/planejamento/valor/editar/{valor_a.id}", data={"nome_valor": "Outro"},
    ).status_code == 403
    assert client.post(
        f"/planejamento/valor/inativar/{valor_a.id}",
    ).status_code == 403


def test_visao_global_nao_cria(app, client):
    """Sem unidade efetiva, escrever é recusado (Visão Global somente leitura)."""
    ids = _cenario(app)
    login_as(client, ids["admin_a"], None)
    resposta = client.post(
        "/planejamento", data={"tipo_post": "valor", "nome_valor": "X"},
    )
    assert resposta.status_code == 403


def test_csrf_e_exigido(app_csrf):
    app_ = app_csrf
    with app_.app_context():
        unidade = _unidade("Unidade CSRF")
        admin = _usuario("Admin CSRF", "admin.csrf@x.com", unidade=unidade)
        db_module.session.commit()
        unidade_id, admin_id = unidade.id, admin.id

    client_ = app_.test_client()
    login_as(client_, admin_id, unidade_id)
    sem_token = client_.post(
        "/planejamento", data={"tipo_post": "valor", "nome_valor": "Sem token"},
    )
    assert sem_token.status_code == 400
    with app_.app_context():
        assert ValorEsportista.query.count() == 0


def test_renderiza_aba_kpi_e_pill(app, client):
    """Renderização: KPI conta os valores e a aba existe dentro do tab-content."""
    ids = _cenario(app)
    _criar(client, "Alegria", ids["un_a"], ids["admin_a"])
    _criar(client, "Disciplina", ids["un_a"], ids["admin_a"])

    corpo = client.get("/planejamento").get_data(as_text=True)
    assert 'id="pill-valores"' in corpo
    assert 'data-bs-target="#tabValores"' in corpo
    assert 'id="tabValores"' in corpo
    assert "Valores do Esportista" in corpo
    assert ">2<" in corpo  # KPI com a contagem

    # Estrutural: o painel precisa estar DENTRO de `.tab-content` (o defeito
    # do template deixava a aba depois do fechamento do container).
    ancestrais = _ancestrais(corpo)["tabValores"]
    assert any("tab-content" in classes for _, classes in ancestrais)


VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class _ColetorAncestrais(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pilha = []
        self.mapa = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = tuple((attrs.get("class") or "").split())
        if attrs.get("id"):
            self.mapa[attrs["id"]] = list(self.pilha)
        if tag not in VOID:
            self.pilha.append((tag, classes))

    def handle_endtag(self, tag):
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                del self.pilha[i:]
                break


def _ancestrais(html):
    coletor = _ColetorAncestrais()
    coletor.feed(html)
    return coletor.mapa
