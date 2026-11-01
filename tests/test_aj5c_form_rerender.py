"""AJ5-C — Re-render do formulário com os dados digitados quando a validação falha.

Achado 0.4 do AJ5-A: nas falhas (nome vazio, CPF inválido, unidade ausente/
inválida) a rota fazia `redirect` e o navegador descartava tudo o que foi
digitado. Agora a rota re-renderiza o próprio formulário (status 200) com `v`
construído a partir de `request.form`, flash com o erro, e o formulário abre no
passo 1 (identificação, onde estão nome/CPF), que é o passo ativo padrão da
carga. Sucesso continua com redirect (PRG).

Regras provadas aqui:
- nada é gravado no banco nem no disco quando a validação falha;
- arquivos (foto/PDFs) não são restaurados pelo navegador -> flash de aviso;
- todo valor digitado volta escapado (autoescape Jinja);
- paridade de `name=` entre novo e editar (exceto lista permitida do editar).

Nenhum dado pessoal real: nomes são marcações de teste sem valor nominativo.
"""

import re

import pytest

from app import db
from app.models import Aluno, Unidade, User
from _helpers import login_as


@pytest.fixture
def dados(app):
    """Unidade + admin fixo + admin global (sem contexto) + aluno editável."""
    with app.app_context():
        unidade = Unidade(nome="Unidade Aj5c R", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        admin = User(
            name="Admin Aj5c R", email="admin.aj5cr@example.com", role="admin",
            unidade_id=unidade.id, is_active=True, first_login=False,
        )
        admin_global = User(
            name="Admin Global Aj5c R", email="admin.global.aj5cr@example.com",
            role="admin", unidade_id=None, is_active=True, first_login=False,
        )
        aluno = Aluno(
            nome="Marca Aj5c R Aluno", ativo=True, unidade_id=unidade.id,
            cpf="52998224725",  # CPF canônico de teste (válidador aceita)
        )
        db.session.add_all([admin, admin_global, aluno])
        db.session.commit()
        return {
            "unidade": unidade.id,
            "admin": admin.id,
            "admin_global": admin_global.id,
            "aluno": aluno.id,
        }


def _texto(resposta) -> str:
    return re.sub(r"\s+", " ", resposta.get_data(as_text=True))


#: POST válido no /aluno/novo, exceto os campos que cada teste quebra.
def _form_ok(**por_cima):
    base = {
        "nome": "Alvo ReRender Aj5c",
        "cpf": "52998224725",
        "genero": "Feminino",
        "zona": "Rural",
        "vai_acompanhado_aulas": "on",
        "acompanhante_aulas": "Outro",
        "acompanhante_aulas_outro": "Vizinha do Bem",
        "beneficio_social_nome": ["Bolsa Família", "BPC"],
        "unidade_id": None,  # preenchido pelos testes que precisam
    }
    base.update(por_cima)
    return {k: v for k, v in base.items() if v is not None}


# ---------------------------------------------------------------------------
# 1) Falha no cadastro novo: re-render com tudo o que foi digitado
# ---------------------------------------------------------------------------


def test_falha_nome_vazio_reRenderiza_passo1_com_valores(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])

    corpo_resp = client.post(
        "/aluno/novo",
        data=_form_ok(nome="", data_nascimento="2012-05-05", rua="Rua Teste Aj5c"),
    )
    assert corpo_resp.status_code == 200, "[AJ5-C] falha não pode redirecionar"
    texto = _texto(corpo_resp)

    # valores de texto voltam digitados
    assert 'value="2012-05-05"' in texto
    assert 'value="Rua Teste Aj5c"' in texto
    # selects/checkboxes/"Outro" livre/tags de benefício voltam
    assert '<option value="Feminino" selected>Feminino</option>' in texto
    assert "checked" in texto  # vai_acompanhado_aulas reidratado
    assert '<option value="Outro" selected>Outro</option>' in texto
    assert 'value="Vizinha do Bem"' in texto
    assert 'name="beneficio_social_nome"' in texto
    assert "Bolsa Família" in texto and "BPC" in texto
    # flash do erro presente
    assert "Nome" in texto and "vazio" in texto
    # abre no passo 1 (nome/CPF), o passo ativo padrão da carga
    assert 'class="form-step active" id="step-1"' in texto
    # nada foi criado
    with app.app_context():
        assert Aluno.query.filter(Aluno.nome.ilike("%ReRender%")).count() == 0


def test_falha_cpf_invalido_reRenderiza_mantendo_nome(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])

    resp = client.post(
        "/aluno/novo",
        data=_form_ok(cpf="123"),  # CPF inválido (não passa no validador)
    )
    assert resp.status_code == 200
    texto = _texto(resp)
    assert "CPF inválido" in texto
    assert 'value="Alvo ReRender Aj5c"' in texto
    assert 'class="form-step active" id="step-1"' in texto
    with app.app_context():
        assert Aluno.query.count() == 1  # só o da fixture


def test_falha_unidade_ausente_global_reRenderiza(app, client, dados):
    """Global sem contexto de unidade: POST sem unidade_id re-renderiza com o
    seletor de unidade marcado com a tentativa (se havia)."""
    login_as(client, dados["admin_global"])  # sem sessão de unidade

    resp = client.post("/aluno/novo", data=_form_ok())
    assert resp.status_code == 200
    texto = _texto(resp)
    assert "Selecione a unidade" in texto
    assert 'name="unidade_id"' in texto
    with app.app_context():
        assert Aluno.query.count() == 1


def test_falha_com_arquivo_avisa_reanexar(app, client, dados, tmp_path):
    import io

    login_as(client, dados["admin"], dados["unidade"])
    resp = client.post(
        "/aluno/novo",
        data={**_form_ok(cpf="123"),
              "foto": (io.BytesIO(b"fake"), "foto_fake.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    texto = _texto(resp)
    assert "reanexe" in texto.lower(), (
        "[AJ5-C] se o POST tinha arquivo, o usuário deve ser avisado de que o "
        "navegador não reanexa nada"
    )


def test_escape_de_valores_digitados(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])
    malicioso = '"><script>x</script>'

    resp = client.post("/aluno/novo", data=_form_ok(nome="", rua=malicioso))
    assert resp.status_code == 200
    bruto = resp.get_data(as_text=True)
    assert "<script>x</script>" not in bruto, (
        "[AJ5-C] valor digitado não pode sair cru no HTML (autoescape Jinja)"
    )
    assert "&gt;&lt;script&gt;" in bruto


def test_nada_gravado_no_disco_na_falha(app, client, dados):
    import os

    login_as(client, dados["admin"], dados["unidade"])
    with app.app_context():
        pasta = app.config.get("UPLOAD_FOLDER") or app.config.get("EXPORT_FOLDER")
    if not pasta or not os.path.isdir(pasta):
        pytest.skip("pasta de upload não existe no ambiente de teste")
    antes = set(os.listdir(pasta))

    client.post("/aluno/novo", data=_form_ok(cpf="123"))
    depois = set(os.listdir(pasta))
    assert depois == antes, "[AJ5-C] falha não pode escrever arquivos"


# ---------------------------------------------------------------------------
# 2) Falha na edição: re-render com dados digitados, banco inalterado
# ---------------------------------------------------------------------------


def test_editar_falha_cpf_reRenderiza_sem_tocar_banco(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])
    with app.app_context():
        antes = db.session.get(Aluno, dados["aluno"]).nome

    resp = client.post(
        f"/aluno/editar/{dados['aluno']}",
        data=_form_ok(cpf="999", nome="Outro Nome Aj5c R"),
    )
    assert resp.status_code == 200
    texto = _texto(resp)
    assert "CPF inválido" in texto
    # os valores DIGITADOS voltam (não os do banco)
    assert 'value="Outro Nome Aj5c R"' in texto
    assert 'class="form-step active" id="step-1"' in texto
    with app.app_context():
        assert db.session.get(Aluno, dados["aluno"]).nome == antes


def test_editar_sucesso_continua_redirect(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])
    resp = client.post(
        f"/aluno/editar/{dados['aluno']}",
        data=_form_ok(nome="Editado Ok Aj5c R"),
    )
    assert resp.status_code == 302, "[AJ5-C] sucesso mantém PRG"


def test_novo_sucesso_continua_redirect(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])
    resp = client.post("/aluno/novo", data=_form_ok())
    assert resp.status_code == 302
    with app.app_context():
        assert Aluno.query.filter(Aluno.nome.ilike("%ReRender%")).count() == 1


# ---------------------------------------------------------------------------
# 3) Paridade de `name=` entre novo e editar (exceto lista permitida)
# ---------------------------------------------------------------------------

#: Campos que só existem num dos modos, deliberadamente (Aj5-C/E2). No
#: estado atual o parcial único não emite nenhum: as caixas de documento,
#: os forms ocultos de exclusão e o seletor de unidade não alteram o
#: conjunto de `name=` (o seletor só aparece no GET global, que este teste
#: não usa). A lista fica aqui como contrato explícito do par.
APENAS_NOVO = set()
APENAS_EDITAR = set()


def _nomes_de_form(html: str) -> set:
    """`name=` dos campos de formulário (input/select/textarea) — ignora
    `<meta name=...>` e afins."""
    from html.parser import HTMLParser

    alvo = {"input", "select", "textarea"}
    nomes = set()

    class _P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in alvo:
                for nome, valor in attrs:
                    if nome == "name" and valor:
                        nomes.add(valor)

    _P(convert_charrefs=True).feed(html)
    return nomes


def test_paridade_names_entre_novo_e_editar(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])
    novo = _nomes_de_form(client.get("/aluno/novo").get_data(as_text=True))
    editar = _nomes_de_form(
        client.get(f"/aluno/editar/{dados['aluno']}").get_data(as_text=True)
    )
    so_no_novo = novo - editar
    so_no_editar = editar - novo
    assert so_no_novo == APENAS_NOVO, (
        f"[AJ5-C] campos só no novo fora da lista permitida: {so_no_novo}"
    )
    assert so_no_editar == APENAS_EDITAR, (
        f"[AJ5-C] campos só no editar fora da lista permitida: {so_no_editar}"
    )
