"""AJ5-A — Exclusão de documento entregue do aluno.

Rota POST `/alunos/<aluno_id>/documentos/<doc_id>/excluir`:

- remove o arquivo do storage (idempotente — arquivo ausente não é erro);
- seta `entregues[doc_id] = False` preservando as demais chaves do JSONB
  (`documentos_entregues`) e reatribuindo um dict novo para o SQLAlchemy
  detectar a mutação;
- não toca em `saude_laudo` (flag de saúde) ao excluir `doc_laudo`;
- audita em `log_acao` com o rótulo "Excluir documento" e detalhes só com
  ids (aluno_id, doc_id, user id) — nenhum nome de arquivo ou dado pessoal.

Roles/escopo idênticos à edição de aluno (admin/pedagógico/secretaria; aluno
de outra unidade 404 para não existir vazado, sem contexto de unidade 403 via
`assert_unidade_context`). Testes usam `tmp_path` como storage — nada toca no
storage real.
"""

import io
import re
from pathlib import Path

import pytest

from app import create_app, db
from app.auth import categoria_acao
from app.models import Aluno, LogAcao, Unidade, User
from app.models.perfis import PerfilDiversidade
from config import Config
from _helpers import login_as

#: Bytes suficientes para o `salvar_documento` atual (valida só a extensão —
#: Achado da Etapa 0.1; validação de conteúdo/magic bytes é pendência AJ5-B).
PDF_MARCA = b"%PDF-1.4 marca de teste AJ5-A\n"


class Aj5DocTestConfig(Config):
    SECRET_KEY = "chave-de-teste-aj5-docs-1234567890-abcd"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app(tmp_path):
    test_app = create_app(Aj5DocTestConfig)
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
        ua = Unidade(nome="Unidade AJ5 Doc A", ativo=True)
        ub = Unidade(nome="Unidade AJ5 Doc B", ativo=True)
        db.session.add_all([ua, ub])
        db.session.flush()

        admin = User(
            name="Admin AJ5 Doc", email="admin.aj5doc@example.com", role="admin",
            unidade_id=ua.id, is_active=True, first_login=False,
        )
        professor = User(
            name="Prof AJ5 Doc", email="prof.aj5doc@example.com", role="professor",
            unidade_id=ua.id, is_active=True, first_login=False,
        )
        gerencia = User(
            name="Gerencia AJ5 Doc", email="ger.aj5doc@example.com", role="gerencia",
            unidade_id=ua.id, is_active=True, first_login=False,
        )
        db.session.add_all([admin, professor, gerencia])

        aluno_a = Aluno(nome="Marca Doc A", ativo=True, unidade_id=ua.id)
        aluno_b = Aluno(nome="Marca Doc B", ativo=True, unidade_id=ub.id)
        db.session.add_all([aluno_a, aluno_b])
        db.session.commit()

        return {
            "unidade_a": ua.id,
            "admin": admin.id,
            "professor": professor.id,
            "gerencia": gerencia.id,
            "aluno_a": aluno_a.id,
            "aluno_b": aluno_b.id,
            "raiz": Path(app.config["UPLOAD_FOLDER"]) / "documentos",
        }


def _upload(client, aluno_id, doc_id):
    """Entrega um documento pelo fluxo normal de edição (POST editar)."""
    return client.post(
        f"/aluno/editar/{aluno_id}",
        data={
            "nome": "Marca Doc A",
            doc_id: (io.BytesIO(PDF_MARCA), "documento.pdf"),
        },
        content_type="multipart/form-data",
    )


def _excluir(client, aluno_id, doc_id):
    return client.post(f"/alunos/{aluno_id}/documentos/{doc_id}/excluir")


def _arquivos_doc(raiz: Path, doc_id: str) -> list[Path]:
    return sorted(
        p for p in raiz.rglob(f"{doc_id}.pdf")
    ) if raiz.is_dir() else []


def _entregues(app, aluno_id) -> dict:
    with app.app_context():
        docs = db.session.get(Aluno, aluno_id).documentos_entregues or {}
    return docs.get("doc_entregue", {})


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------


def test_excluir_remove_arquivo_e_flag_preservando_as_demais(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _upload(client, dados["aluno_a"], "doc_aluno").status_code == 302
    assert _upload(client, dados["aluno_a"], "doc_termo").status_code == 302
    assert _arquivos_doc(dados["raiz"], "doc_aluno")
    assert _entregues(app, dados["aluno_a"])["doc_aluno"] is True

    resposta = _excluir(client, dados["aluno_a"], "doc_aluno")
    assert resposta.status_code == 302

    assert _arquivos_doc(dados["raiz"], "doc_aluno") == [], (
        "[AJ5-A] o arquivo do documento excluído continua no storage"
    )
    entregues = _entregues(app, dados["aluno_a"])
    assert entregues["doc_aluno"] is False
    assert entregues["doc_termo"] is True, (
        "[AJ5-A] a exclusão pisou em outras chaves do JSONB"
    )
    # A reatribuição do dict é o que o SQLAlchemy vê como mudança:
    assert _arquivos_doc(dados["raiz"], "doc_termo"), "sanidade: o outro segue no disco"


def test_log_gravado_classificado_e_sem_dado_pessoal(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    _upload(client, dados["aluno_a"], "doc_aluno")

    assert _excluir(client, dados["aluno_a"], "doc_aluno").status_code == 302

    with app.app_context():
        logs = LogAcao.query.filter_by(acao="Excluir documento").all()
    assert len(logs) == 1
    log = logs[0]
    assert categoria_acao(log.acao) == "exclusao"
    assert f"aluno_id={dados['aluno_a']}" in log.detalhes
    assert "doc_aluno" in log.detalhes
    # Nada de nome de arquivo, nome de aluno ou e-mail nos detalhes:
    assert "documento.pdf" not in log.detalhes
    assert "Marca" not in log.detalhes
    assert "@" not in log.detalhes


def test_excluir_laudo_nao_toca_em_saude_laudo(app, client, dados):
    with app.app_context():
        db.session.add(
            PerfilDiversidade(
                aluno_id=dados["aluno_a"], saude_laudo=True, tipo_deficiencia="TEA"
            )
        )
        db.session.commit()

    login_as(client, dados["admin"], dados["unidade_a"])
    _upload(client, dados["aluno_a"], "doc_laudo")

    assert _excluir(client, dados["aluno_a"], "doc_laudo").status_code == 302

    with app.app_context():
        perfil = PerfilDiversidade.query.filter_by(aluno_id=dados["aluno_a"]).first()
        assert perfil.saude_laudo is True, (
            "[AJ5-A] excluir o arquivo não pode mexer na flag de saúde"
        )
        assert perfil.tipo_deficiencia == "TEA"
    assert _entregues(app, dados["aluno_a"])["doc_laudo"] is False


def test_reupload_depois_da_exclusao_volta_flag_true(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    _upload(client, dados["aluno_a"], "doc_aluno")
    _excluir(client, dados["aluno_a"], "doc_aluno")
    assert _entregues(app, dados["aluno_a"])["doc_aluno"] is False

    assert _upload(client, dados["aluno_a"], "doc_aluno").status_code == 302
    assert _entregues(app, dados["aluno_a"])["doc_aluno"] is True
    assert _arquivos_doc(dados["raiz"], "doc_aluno"), "reupload não gravou o arquivo"


# ---------------------------------------------------------------------------
# Guardas
# ---------------------------------------------------------------------------


def test_doc_id_fora_de_doc_ids_e_404(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _excluir(client, dados["aluno_a"], "doc_inventado").status_code == 404


def test_aluno_de_outra_unidade_e_404(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _excluir(client, dados["aluno_b"], "doc_aluno").status_code == 404


@pytest.mark.parametrize("papel", ["professor", "gerencia"])
def test_papel_sem_permissao_e_403(app, client, dados, papel):
    login_as(client, dados[papel], dados["unidade_a"])
    assert _excluir(client, dados["aluno_a"], "doc_aluno").status_code == 403


def test_anonimo_e_redirecionado_para_login(app, client, dados):
    resposta = _excluir(client, dados["aluno_a"], "doc_aluno")
    assert resposta.status_code == 302
    assert "login" in resposta.headers["Location"].lower()


def test_get_na_rota_de_exclusao_e_405(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    resposta = client.get(f"/alunos/{dados['aluno_a']}/documentos/doc_aluno/excluir")
    assert resposta.status_code == 405


def test_segunda_exclusao_e_idempotente(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    _upload(client, dados["aluno_a"], "doc_aluno")
    _upload(client, dados["aluno_a"], "doc_termo")

    assert _excluir(client, dados["aluno_a"], "doc_aluno").status_code == 302
    # Segunda vez: arquivo já não existe — não pode ser erro.
    assert _excluir(client, dados["aluno_a"], "doc_aluno").status_code == 302

    entregues = _entregues(app, dados["aluno_a"])
    assert entregues["doc_aluno"] is False
    assert entregues["doc_termo"] is True


# ---------------------------------------------------------------------------
# Template editar.html
# ---------------------------------------------------------------------------


def _corpo(client, aluno_id) -> str:
    return re.sub(r"\s+", " ", client.get(f"/aluno/editar/{aluno_id}").get_data(as_text=True))


def test_html_mostra_botao_so_com_arquivo_entregue(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])

    corpo = _corpo(client, dados["aluno_a"])
    assert "form-excluir-doc_aluno" not in corpo, (
        "[AJ5-A] sem arquivo entregue não pode haver botão de exclusão"
    )

    _upload(client, dados["aluno_a"], "doc_aluno")
    corpo = _corpo(client, dados["aluno_a"])
    assert 'form="form-excluir-doc_aluno"' in corpo
    assert "Excluir" in corpo
    # O box inteiro abre o seletor de arquivo — o botão precisa bloquear:
    assert 'event.stopPropagation()' in corpo
    # Rota de visualização existe (Etapa 0.2) -> link "Ver" ao lado.
    assert f"/aluno/{dados['aluno_a']}/documento/doc_aluno" in corpo
    # O form de exclusão fica FORA do multiStepForm (form aninhado é inválido).
    form_pos = corpo.index('id="multiStepForm"')
    fechar_pos = corpo.index("</form>", form_pos)
    excluir_pos = corpo.index('id="form-excluir-doc_aluno"')
    assert excluir_pos > fechar_pos, (
        "[AJ5-A] o <form> de exclusão não pode estar aninhado no multiStepForm"
    )
    # Confirmação antes de enviar:
    assert "confirm(" in corpo[excluir_pos : excluir_pos + 400]
