"""AJ5-B — Validação de upload de documento PDF no servidor.

Cobre a Etapa 0.1 do AJ5-A (Achados: `salvar_documento` só olhava a extensão):

- `validar_pdf` em `app/registros/shared.py`, chamado por `salvar_documento`
  ANTES de gravar qualquer byte: `.pdf` exigido, vazio rejeitado, assinatura
  `%PDF-` nos primeiros 1024 bytes, tamanho por seek/tell com teto de 2 MB por
  arquivo (exatamente 2 MB passa; 2 MB + 1 não);
- recusa deixa de ser silenciosa: flash por documento com nome amigável e
  motivo, sem o nome do arquivo do cliente; um inválido não desfaz o cadastro
  nem os documentos válidos do mesmo POST;
- `MAX_CONTENT_LENGTH` global de 20 MB (todas as rotas de upload cabem) com
  handler 413 de flash amigável + redirect, sem stack trace;
- `ver_documento_aluno` serve com `nosniff`, `Cache-Control: private, no-store`
  e `Content-Disposition: inline`, mantendo roles e escopo de unidade.

Storage sempre `tmp_path`; bytes gerados em memória; nenhum dado pessoal.
"""

import io
import re
from pathlib import Path

import pytest

from app import create_app, db
from app.models import Aluno, Unidade, User
from config import Config
from _helpers import login_as

#: PDF mínimo: cabeçalho com a assinatura exigida e trailer `%%EOF`.
PDF_VALIDO = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
#: Começa com `MZ` (cabeça de PE/EXE) — nomenclatura .pdf, conteúdo não-PDF.
NAO_PDF = b"MZ\x90\x03 este arquivo nao e um pdf"
#: Um PDF real de 1 MB + padding para o teste do teto por arquivo.
MB = 1024 * 1024


class Aj5bTestConfig(Config):
    SECRET_KEY = "chave-de-teste-aj5b-upload-1234567890-ab"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app(tmp_path):
    test_app = create_app(Aj5bTestConfig)
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
        ua = Unidade(nome="Unidade AJ5b A", ativo=True)
        ub = Unidade(nome="Unidade AJ5b B", ativo=True)
        db.session.add_all([ua, ub])
        db.session.flush()

        admin = User(
            name="Admin AJ5b", email="admin.aj5b@example.com", role="admin",
            unidade_id=ua.id, is_active=True, first_login=False,
        )
        professor = User(
            name="Prof AJ5b", email="prof.aj5b@example.com", role="professor",
            unidade_id=ua.id, is_active=True, first_login=False,
        )
        db.session.add_all([admin, professor])

        aluno_a = Aluno(nome="Marca Aj5b A", ativo=True, unidade_id=ua.id)
        aluno_b = Aluno(nome="Marca Aj5b B", ativo=True, unidade_id=ub.id)
        db.session.add_all([aluno_a, aluno_b])
        db.session.commit()

        return {
            "unidade_a": ua.id,
            "admin": admin.id,
            "professor": professor.id,
            "aluno_a": aluno_a.id,
            "aluno_b": aluno_b.id,
            "raiz": Path(app.config["UPLOAD_FOLDER"]),
        }


def _editar(client, aluno_id, arquivos, nome="Marca Aj5b A"):
    """POST do form de edição com arquivos `{campo: (bytes, nome_no_cliente)}`."""
    data = {"nome": nome}
    for campo, (conteudo, nome_cliente) in arquivos.items():
        data[campo] = (io.BytesIO(conteudo), nome_cliente)
    return client.post(
        f"/aluno/editar/{aluno_id}",
        data=data,
        content_type="multipart/form-data",
    )


def _pdf_de(tamanho: int) -> bytes:
    """PDF com exatamente `tamanho` bytes: assinatura no início, EOF no fim."""
    cabeca = b"%PDF-1.4\n"
    cauda = b"\n%%EOF\n"
    meio = b" " * (tamanho - len(cabeca) - len(cauda))
    return cabeca + meio + cauda


def _arquivos_pdf(raiz: Path) -> list[Path]:
    return sorted(raiz.rglob("*.pdf")) if raiz.is_dir() else []


def _entregues(app, aluno_id) -> dict:
    with app.app_context():
        docs = db.session.get(Aluno, aluno_id).documentos_entregues or {}
    return docs.get("doc_entregue", {})


def _texto(resposta) -> str:
    return re.sub(r"\s+", " ", resposta.get_data(as_text=True))


# ---------------------------------------------------------------------------
# Caminho feliz e substituição
# ---------------------------------------------------------------------------


def test_pdf_minimo_valido_aceito_e_flag_true(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _editar(client, dados["aluno_a"], {"doc_aluno": (PDF_VALIDO, "doc.pdf")}).status_code == 302

    assert _entregues(app, dados["aluno_a"]).get("doc_aluno") is True
    gravados = _arquivos_pdf(dados["raiz"])
    assert len(gravados) == 1
    assert gravados[0].read_bytes().startswith(b"%PDF-")


def test_reupload_de_pdf_valido_substitui(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    _editar(client, dados["aluno_a"], {"doc_aluno": (PDF_VALIDO, "doc.pdf")})
    novo = PDF_VALIDO + b"% revisao\n%%EOF\n"
    assert _editar(client, dados["aluno_a"], {"doc_aluno": (novo, "doc.pdf")}).status_code == 302

    gravados = _arquivos_pdf(dados["raiz"])
    assert len(gravados) == 1
    assert gravados[0].read_bytes() == novo
    assert _entregues(app, dados["aluno_a"]).get("doc_aluno") is True


# ---------------------------------------------------------------------------
# Recusas: conteúdo, extensão, tamanho, vazio
# ---------------------------------------------------------------------------


def test_conteudo_nao_pdf_com_extensao_pdf_e_rejeitado(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    resposta = _editar(client, dados["aluno_a"], {"doc_aluno": (NAO_PDF, "doc.pdf")})
    assert resposta.status_code == 302

    assert _arquivos_pdf(dados["raiz"]) == [], (
        "[AJ5-B] arquivo recusado foi gravado no storage"
    )
    assert _entregues(app, dados["aluno_a"]).get("doc_aluno") is not True, (
        "[AJ5-B] flag virou True com documento rejeitado"
    )
    corpo = _texto(client.get(f"/aluno/editar/{dados['aluno_a']}"))
    assert "RG/CPF Aluno" in corpo and "não aceito" in corpo, (
        "[AJ5-B] recusa continua silenciosa"
    )


def test_conteudo_pdf_com_extensao_diferente_e_rejeitado(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _editar(client, dados["aluno_a"], {"doc_aluno": (PDF_VALIDO, "doc.txt")}).status_code == 302

    assert _arquivos_pdf(dados["raiz"]) == []
    assert _entregues(app, dados["aluno_a"]).get("doc_aluno") is not True


def test_exatamente_2mb_e_aceito(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _editar(client, dados["aluno_a"], {"doc_aluno": (_pdf_de(2 * MB), "doc.pdf")}).status_code == 302

    assert _entregues(app, dados["aluno_a"]).get("doc_aluno") is True
    assert _arquivos_pdf(dados["raiz"])[0].stat().st_size == 2 * MB


def test_2mb_mais_um_byte_e_rejeitado(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _editar(client, dados["aluno_a"], {"doc_aluno": (_pdf_de(2 * MB + 1), "doc.pdf")}).status_code == 302

    assert _arquivos_pdf(dados["raiz"]) == []
    assert _entregues(app, dados["aluno_a"]).get("doc_aluno") is not True
    corpo = _texto(client.get(f"/aluno/editar/{dados['aluno_a']}"))
    assert "2 MB" in corpo, "[AJ5-B] flash não informou o motivo (tamanho)"


def test_arquivo_vazio_e_rejeitado(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    assert _editar(client, dados["aluno_a"], {"doc_aluno": (b"", "doc.pdf")}).status_code == 302

    assert _arquivos_pdf(dados["raiz"]) == []
    assert _entregues(app, dados["aluno_a"]).get("doc_aluno") is not True
    corpo = _texto(client.get(f"/aluno/editar/{dados['aluno_a']}"))
    assert "vazio" in corpo, "[AJ5-B] flash não informou o motivo (vazio)"


# ---------------------------------------------------------------------------
#POST misto, privacidade do flash e limite global
# ---------------------------------------------------------------------------


def test_post_misto_salva_valido_e_rejeita_invalido(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    resposta = _editar(
        client,
        dados["aluno_a"],
        {
            "doc_aluno": (PDF_VALIDO, "ok.pdf"),
            "doc_termo": (NAO_PDF, "ruim.pdf"),
        },
    )
    assert resposta.status_code == 302

    entregues = _entregues(app, dados["aluno_a"])
    assert entregues.get("doc_aluno") is True, (
        "[AJ5-B] documento válido do mesmo POST foi perdido junto com o inválido"
    )
    assert entregues.get("doc_termo") is not True
    nomes = [p.name for p in _arquivos_pdf(dados["raiz"])]
    assert nomes == ["doc_aluno.pdf"]
    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno_a"])
        assert aluno is not None, "[AJ5-B] upload inválido desfez o cadastro"


def test_flash_nao_revela_nome_do_arquivo_do_cliente(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    _editar(client, dados["aluno_a"], {"doc_aluno": (NAO_PDF, "cnh_nuvem_pessoal.pdf")})

    corpo = _texto(client.get(f"/aluno/editar/{dados['aluno_a']}"))
    assert "não aceito" in corpo
    assert "cnh_nuvem_pessoal" not in corpo, (
        "[AJ5-B] flash vazou o nome do arquivo enviado pelo cliente"
    )


def test_max_content_length_global_e_20mb(app):
    assert app.config["MAX_CONTENT_LENGTH"] == 20 * MB


def test_413_responde_flash_amigavel_sem_stack_trace(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    # O teto global (20 MB) é o mecanismo; baixamos o valor nesta aplicação
    # para o teste mandar um corpo acima dele sem alocação pesada.
    app.config["MAX_CONTENT_LENGTH"] = MB

    destino = f"http://localhost/aluno/editar/{dados['aluno_a']}"
    resposta = client.post(
        f"/aluno/editar/{dados['aluno_a']}",
        data={
            "nome": "Marca Aj5b A",
            "doc_aluno": (io.BytesIO(_pdf_de(2 * MB)), "gigante.pdf"),
        },
        content_type="multipart/form-data",
        headers={"Referer": destino},
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "Traceback" not in resposta.get_data(as_text=True)
    corpo = _texto(resposta)
    assert "Envio recusado" in corpo and "1 MB" in corpo, (
        "[AJ5-B] 413 sem mensagem amigável"
    )
    assert _arquivos_pdf(dados["raiz"]) == [], "[AJ5-B] 413 gravou arquivo parcial"


# ---------------------------------------------------------------------------
# ver_documento_aluno: headers e guards intactos
# ---------------------------------------------------------------------------


def _entrega_valido(client, aluno_id, doc_id="doc_aluno"):
    return _editar(client, aluno_id, {doc_id: (PDF_VALIDO, "doc.pdf")})


def test_ver_documento_servi_com_headers_seguros(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    _entrega_valido(client, dados["aluno_a"])

    resposta = client.get(f"/aluno/{dados['aluno_a']}/documento/doc_aluno")
    assert resposta.status_code == 200
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["Cache-Control"] == "private, no-store"
    assert resposta.headers["Content-Disposition"] == 'inline; filename="doc_aluno.pdf"'
    assert resposta.mimetype == "application/pdf"


def test_ver_documento_roles_e_escopo_permanecem(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])
    _entrega_valido(client, dados["aluno_a"])

    # Anônimo: redirect para login (comportamento antigo). GET /logout é
    # inócuo de propósito (S1-16) — só o POST encerra a sessão.
    client.post("/logout")
    anonima = client.get(f"/aluno/{dados['aluno_a']}/documento/doc_aluno")
    assert anonima.status_code == 302
    assert "login" in anonima.headers["Location"].lower()

    # Professor sem role apta: 403, mesmo com header novo na rota.
    login_as(client, dados["professor"], dados["unidade_a"])
    assert client.get(f"/aluno/{dados['aluno_a']}/documento/doc_aluno").status_code == 403

    # Aluno de outra unidade no mesmo contexto: bloqueado (403 do helper).
    login_as(client, dados["admin"], dados["unidade_a"])
    assert client.get(f"/aluno/{dados['aluno_b']}/documento/doc_aluno").status_code == 403
