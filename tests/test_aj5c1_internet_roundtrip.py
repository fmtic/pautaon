"""AJ5-C1 — Ida e volta do checkbox "Não possui acesso a internet".

O POST grava o inverso do checkbox em `EnderecoAluno.possui_acesso_internet`
(`upsert_endereco`); `get_perfil_completo(aluno)['endereco']` devolve a
coluna e o contrato `valores_form_aluno` a inverte de volta em
`v.nao_possui_acesso_internet`, que o parcial usa para o atributo `checked`.

Regras provadas aqui:
- cadastrar marcado -> abrir a edição mostra marcado;
- desmarcar na edição -> reabrir mostra desmarcado (o banco virou True);
- POST sem o campo -> estado coerente com o default (possui internet = True,
  checkbox desmarcado).

Nenhum dado pessoal real: nomes/endereços são marcações de teste.
"""

import re

import pytest

from app import db
from app.models import Aluno, EnderecoAluno, Unidade, User
from _helpers import login_as

#: CPF canônico de teste (o validador da rota aceita).
CPF_TESTE = "52998224725"

NOME_NOVO = "Marca Aj5c1 Internet"
NOME_EDITADO = "Marca Aj5c1 Internet Editada"


@pytest.fixture
def dados(app):
    """Unidade + admin com contexto de unidade."""
    with app.app_context():
        unidade = Unidade(nome="Unidade Aj5c1 Internet", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        admin = User(
            name="Admin Aj5c1 Internet",
            email="admin.aj5c1.internet@example.com",
            role="admin",
            unidade_id=unidade.id,
            is_active=True,
            first_login=False,
        )
        db.session.add(admin)
        db.session.commit()
        return {"unidade": unidade.id, "admin": admin.id}


def _form(**por_cima):
    """POST do formulário de aluno com endereço preenchido.

    O endereço é necessário para `upsert_endereco` persistir o checkbox (ele
    não cria a linha quando todos os campos relevantes estão vazios e a
    internet é True).
    """
    base = {
        "nome": NOME_NOVO,
        "cpf": CPF_TESTE,
        "genero": "Feminino",
        "rua": "Rua Teste Aj5c1",
        "numero": "10",
        "bairro": "Centro",
        "cidade": "Cidade Teste",
        "uf": "SP",
        "zona": "Urbana",
    }
    base.update(por_cima)
    return {k: v for k, v in base.items() if v is not None}


def _checkbox_marcado(html: str) -> bool:
    """`checked` no input de id `nao_possui_acesso_internet` (ignora outros)."""
    tag = re.search(
        r'<input[^>]*id="nao_possui_acesso_internet"[^>]*>', html, re.S
    )
    assert tag is not None, 'input "nao_possui_acesso_internet" ausente no HTML'
    return "checked" in tag.group(0)


def _aluno_por_nome(nome: str) -> Aluno:
    aluno = Aluno.query.filter_by(nome=nome).one()
    return aluno


# ---------------------------------------------------------------------------
# 1) Marcar no cadastro -> editar mostra marcado
# ---------------------------------------------------------------------------


def test_marcado_no_cadastro_abre_marcado_no_editar(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])

    resp = client.post(
        "/aluno/novo",
        data=_form(nao_possui_acesso_internet="on"),
    )
    assert resp.status_code == 302, "[AJ5-C1] cadastro válido continua PRG"

    with app.app_context():
        aluno = _aluno_por_nome(NOME_NOVO)
        assert aluno.endereco is not None
        assert aluno.endereco.possui_acesso_internet is False
        aluno_id = aluno.id

    editar = client.get(f"/aluno/editar/{aluno_id}")
    assert editar.status_code == 200
    assert _checkbox_marcado(editar.get_data(as_text=True)), (
        "[AJ5-C1] checkbox marcado no cadastro deve voltar marcado na edição"
    )


# ---------------------------------------------------------------------------
# 2) Desmarcar na edição -> reabrir mostra desmarcado
# ---------------------------------------------------------------------------


def test_desmarcar_no_editar_abre_desmarcado_depois(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])

    client.post("/aluno/novo", data=_form(nao_possui_acesso_internet="on"))
    with app.app_context():
        aluno_id = _aluno_por_nome(NOME_NOVO).id

    assert _checkbox_marcado(
        client.get(f"/aluno/editar/{aluno_id}").get_data(as_text=True)
    )

    resp = client.post(
        f"/aluno/editar/{aluno_id}",
        data=_form(nome=NOME_EDITADO),  # sem nao_possui_acesso_internet
    )
    assert resp.status_code == 302, "[AJ5-C1] edição válida continua PRG"

    with app.app_context():
        aluno = db.session.get(Aluno, aluno_id)
        assert aluno.nome == NOME_EDITADO
        assert aluno.endereco.possui_acesso_internet is True

    editar = client.get(f"/aluno/editar/{aluno_id}")
    assert editar.status_code == 200
    assert not _checkbox_marcado(editar.get_data(as_text=True)), (
        "[AJ5-C1] desmarcar na edição deve persistir e voltar desmarcado"
    )


# ---------------------------------------------------------------------------
# 3) Sem o campo no POST -> default (possui internet = True)
# ---------------------------------------------------------------------------


def test_sem_o_campo_no_post_usa_default(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])

    resp = client.post("/aluno/novo", data=_form())
    assert resp.status_code == 302

    with app.app_context():
        aluno = _aluno_por_nome(NOME_NOVO)
        assert isinstance(aluno.endereco, EnderecoAluno)
        assert aluno.endereco.possui_acesso_internet is True, (
            "[AJ5-C1] campo ausente = default da coluna (possui internet)"
        )
        aluno_id = aluno.id

    assert not _checkbox_marcado(
        client.get(f"/aluno/editar/{aluno_id}").get_data(as_text=True)
    )
