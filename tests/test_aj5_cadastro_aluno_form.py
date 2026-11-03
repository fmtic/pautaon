"""AJ5-A — Correções de dados do formulário de cadastro de aluno.

Cobre os três achados de dados da Etapa 1 (relatório `AJ5A_CadastroAluno.md`):

a) `novo.html` oferecia "Não se aplica" com `value="Motora/Física"` — gravava
   deficiência motora para quem disse o contrário. O valor próprio exige o
   catálogo `TIPOS_DEFICIENCIA` (que só tinha as sete opções reais);
b) `editar.html` comparava o tipo salvo com `'Outra'`, valor que o catálogo
   nunca gravou (o canônico é `'Outro'`) — a opção nunca voltava selecionada
   e um re-POST sem mexer perdia o tipo;
c) acompanhante com texto livre (salvo via "Outro") não tem a opção
   correspondente na lista fixa: `editar.html` precisa selecionar "Outro",
   pré-preencher `acompanhante_aulas_outro` e mostrar o div — senão o
   round-trip "salvar com Outro='Tia' -> abrir editar -> salvar sem mexer"
   apaga o valor (o select voltava vazio e `_aplicar_campos_civis` gravava
   `None`).

Nenhum dado pessoal real: nomes são marcações de teste sem valor nominativo.
"""

import re

import pytest

from app import create_app, db
from app.models import Aluno, Unidade, User
from app.models.perfis import PerfilDiversidade
from config import Config
from _helpers import login_as


class Aj5TestConfig(Config):
    SECRET_KEY = "chave-de-teste-aj5-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app(tmp_path):
    test_app = create_app(Aj5TestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        UPLOAD_FOLDER=str(tmp_path / "uploads"),
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def dados(app):
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ5 A", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        admin = User(
            name="Admin AJ5", email="admin.aj5@example.com", role="admin",
            unidade_id=unidade.id, is_active=True, first_login=False,
        )
        db.session.add(admin)

        aluno = Aluno(
            nome="Marca AJ5 Aluno", ativo=True, unidade_id=unidade.id,
            vai_acompanhado_aulas=True,
        )
        db.session.add(aluno)
        db.session.commit()

        return {
            "unidade": unidade.id,
            "admin": admin.id,
            "aluno": aluno.id,
        }


def _texto(resposta) -> str:
    """HTML da resposta com o ruído de layout removido (espaços/quebras)."""
    return re.sub(r"\s+", " ", resposta.get_data(as_text=True))


# ---------------------------------------------------------------------------
# a) "Não se aplica" com valor próprio em novo.html
# ---------------------------------------------------------------------------


def test_novo_oferece_nao_se_aplica_com_valor_proprio(app, client, dados):
    login_as(client, dados["admin"], dados["unidade"])

    corpo = _texto(client.get("/aluno/novo"))

    assert '<option value="Não se aplica">Não se aplica</option>' in corpo, (
        "[AJ5-A] a opção 'Não se aplica' de tipo_deficiencia precisa carregar "
        "o próprio valor (não 'Motora/Física')"
    )
    assert 'value="Motora/Física">Não se aplica' not in corpo


def test_tipo_nao_se_aplica_persiste_pelo_catalogo(app, client, dados):
    """O valor novo tem de sobreviver à validação do catálogo no POST."""
    login_as(client, dados["admin"], dados["unidade"])

    resposta = client.post(
        "/aluno/novo",
        data={
            "nome": "Marca AJ5 Novo",
            "saude_laudo": "on",
            "tipo_deficiencia": "Não se aplica",
        },
    )
    assert resposta.status_code == 302

    with app.app_context():
        # `formatar_nome_proprio` pode ajustar caixa — busca por substring.
        aluno = Aluno.query.filter(Aluno.nome.ilike("%Novo%")).first()
        assert aluno is not None, "[AJ5-A] cadastro com 'Não se aplica' foi perdido"
        assert aluno.unidade_id == dados["unidade"]
        perfil = PerfilDiversidade.query.filter_by(aluno_id=aluno.id).first()
        assert perfil is not None
        assert perfil.tipo_deficiencia == "Não se aplica"


# ---------------------------------------------------------------------------
# b) editar.html: comparação do tipo 'Outro'
# ---------------------------------------------------------------------------


def test_editar_seleciona_outro_para_tipo_deficiencia_outro(app, client, dados):
    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno"])
        db.session.add(
            PerfilDiversidade(
                aluno_id=aluno.id, saude_laudo=True, tipo_deficiencia="Outro"
            )
        )
        db.session.commit()

    login_as(client, dados["admin"], dados["unidade"])
    corpo = _texto(client.get(f"/aluno/editar/{dados['aluno']}"))

    assert '<option value="Outro" selected>Outro</option>' in corpo, (
        "[AJ5-A] o tipo salvo 'Outro' (único que o catálogo grava) precisa "
        "voltar selecionado na edição"
    )


# ---------------------------------------------------------------------------
# c) acompanhante "Outro" com texto livre — round-trip completo
# ---------------------------------------------------------------------------


def test_editar_mostra_outro_selecionado_e_preenchido(app, client, dados):
    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno"])
        aluno.acompanhante_aulas = "Tia"
        db.session.commit()

    login_as(client, dados["admin"], dados["unidade"])
    corpo = _texto(client.get(f"/aluno/editar/{dados['aluno']}"))

    assert '<option value="Outro" selected>Outro</option>' in corpo, (
        "[AJ5-A] valor salvo fora da lista fixa deve selecionar 'Outro'"
    )
    assert 'id="acompanhante_aulas_outro_div"' in corpo
    assert re.search(
        r'<div class="mt-2" id="acompanhante_aulas_outro_div">', corpo
    ), "[AJ5-A] o div do outro acompanhante deve vir visível na carga inicial"
    assert re.search(
        r'name="acompanhante_aulas_outro"[^>]*value="Tia"', corpo
    ), "[AJ5-A] o campo livre deve voltar pré-preenchido com o valor salvo"


def test_roundtrip_acompanhante_outro_sem_perder_valor(app, client, dados):
    """Salvar com Outro='Tia' -> abrir editar -> salvar sem mexer -> 'Tia'."""
    login_as(client, dados["admin"], dados["unidade"])

    resposta = client.post(
        f"/aluno/editar/{dados['aluno']}",
        data={
            "nome": "Marca AJ5 Aluno",
            "vai_acompanhado_aulas": "on",
            "acompanhante_aulas": "Outro",
            "acompanhante_aulas_outro": "Tia",
        },
    )
    assert resposta.status_code == 302
    with app.app_context():
        assert db.session.get(Aluno, dados["aluno"]).acompanhante_aulas == "Tia"

    # "Salvar sem mexer": o browser reenvia exatamente o que a página mostra.
    client.post(
        f"/aluno/editar/{dados['aluno']}",
        data={
            "nome": "Marca AJ5 Aluno",
            "vai_acompanhado_aulas": "on",
            "acompanhante_aulas": "Outro",
            "acompanhante_aulas_outro": "Tia",
        },
    )
    with app.app_context():
        assert db.session.get(Aluno, dados["aluno"]).acompanhante_aulas == "Tia", (
            "[AJ5-A] o round-trip apagou o acompanhante livre"
        )


def test_acompanhante_canonico_nao_ganha_outro(app, client, dados):
    """Região de comportamento: valor da lista fixa continua ele mesmo."""
    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno"])
        aluno.acompanhante_aulas = "Mãe"
        db.session.commit()

    login_as(client, dados["admin"], dados["unidade"])
    corpo = _texto(client.get(f"/aluno/editar/{dados['aluno']}"))

    assert '<option value="Mãe" selected>Mãe</option>' in corpo
    assert '<option value="Outro" selected' not in corpo
