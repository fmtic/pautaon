import io
import json
import re
import struct
import zlib
from datetime import date
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from _helpers import login_as
from app import create_app, db
from app.models import (
    Aluno,
    Atendimento,
    CentroCusto,
    ModeloCertificado,
    PeriodoLetivo,
    Unidade,
    User,
)
from app.services.certificado_modelo import MAX_BYTES
from config import Config

MB = 1024 * 1024
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _png_valido():
    def bloco(tipo, dados):
        return (
            struct.pack(">I", len(dados))
            + tipo
            + dados
            + struct.pack(">I", zlib.crc32(tipo + dados) & 0xFFFFFFFF)
        )

    cabecalho = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00")
    return (
        cabecalho
        + bloco(b"IHDR", ihdr)
        + bloco(b"IDAT", idat)
        + bloco(b"IEND", b"")
    )


PNG = _png_valido()
JPEG = b"\xff\xd8\xff" + b"conteudo sintetico"


def _docx_valido():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as arquivo_zip:
        tipos = (
            b"<Types><Override ContentType=\""
            b"application/vnd.openxmlformats-officedocument."
            b"wordprocessingml.document.main+xml\"/></Types>"
        )
        arquivo_zip.writestr("[Content_Types].xml", tipos)
        arquivo_zip.writestr("word/document.xml", b"<document/>")
    return buffer.getvalue()


def _odt_valido():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as arquivo_zip:
        arquivo_zip.writestr("mimetype", b"application/vnd.oasis.opendocument.text", compress_type=ZIP_STORED)
        arquivo_zip.writestr("content.xml", b"<document/>")
    return buffer.getvalue()


def _zip_generico():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as arquivo_zip:
        arquivo_zip.writestr("payload.txt", b"texto")
    return buffer.getvalue()


class Aj5dTestConfig(Config):
    SECRET_KEY = "chave-de-teste-aj5d-upload-1234567890-ab"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app(tmp_path):
    test_app = create_app(Aj5dTestConfig)
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
def ids(app):
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ5D", ativo=True)
        outra_unidade = Unidade(nome="Unidade AJ5D B", ativo=True)
        db.session.add_all([unidade, outra_unidade])
        db.session.flush()

        usuarios = {
            "admin": User(
                name="Admin AJ5D", email="admin.aj5d@example.test",
                role="admin", unidade_id=unidade.id, is_active=True,
                first_login=False,
            ),
            "professor": User(
                name="Professor AJ5D", email="professor.aj5d@example.test",
                role="professor", unidade_id=unidade.id, is_active=True,
                first_login=False,
            ),
            "pedagogico_b": User(
                name="Pedagogico AJ5D B", email="pedagogico-b.aj5d@example.test",
                role="pedagogico", unidade_id=outra_unidade.id, is_active=True,
                first_login=False,
            ),
        }
        for usuario in usuarios.values():
            usuario.set_password("SenhaSintetica!123")
        db.session.add_all(usuarios.values())
        db.session.flush()

        aluno = Aluno(nome="Aluno Sintetico AJ5D", ativo=True, unidade_id=unidade.id)
        centro = CentroCusto(
            nome="Centro Sintetico AJ5D", unidade_id=unidade.id, ativo=True
        )
        db.session.add_all([aluno, centro])
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="2026.1 AJ5D",
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 6, 30),
            unidade_id=unidade.id,
            centro_custo=centro.nome,
        )
        db.session.add(periodo)
        db.session.commit()
        return {
            "unidade": unidade.id,
            "outra_unidade": outra_unidade.id,
            "admin": usuarios["admin"].id,
            "professor": usuarios["professor"].id,
            "pedagogico_b": usuarios["pedagogico_b"].id,
            "aluno": aluno.id,
            "centro": centro.id,
            "periodo": periodo.id,
        }


def _arquivos(app):
    raiz = Path(app.config["UPLOAD_FOLDER"])
    return sorted(caminho for caminho in raiz.rglob("*") if caminho.is_file()) if raiz.exists() else []


def _enviar_anexo(client, ids, nome, conteudo):
    payload = {
        "data_atendimento": "2026-11-04",
        "setor": "pedagogico",
        "resumo": "Atendimento sintetico",
        "dados": {"origem": "Educando", "motivo": "Motivo sintetico"},
    }
    return client.post(
        f"/alunos/{ids['aluno']}/atendimentos/novo",
        data={
            "payload": json.dumps(payload),
            "anexo": (io.BytesIO(conteudo), nome),
        },
        content_type="multipart/form-data",
    )


def _enviar_modelo(client, ids, nome, conteudo, *, seguir=True):
    return client.post(
        f"/periodo-letivo/{ids['periodo']}/certificado-modelo/{ids['centro']}",
        data={"arquivo": (io.BytesIO(conteudo), nome)},
        content_type="multipart/form-data",
        follow_redirects=seguir,
    )


@pytest.mark.parametrize(
    ("nome", "conteudo", "mensagem"),
    [
        ("fraude.pdf", b"texto comum", "PDF"),
        ("fraude.png", b"<html>nao e PNG</html>", "PNG"),
        ("binario.txt", b"MZ\x90\x00", "TXT"),
        ("zip-falso.docx", _zip_generico(), "DOCX"),
        ("zip-falso.odt", _zip_generico(), "ODT"),
        ("vazio.pdf", b"", "vazio"),
        ("grande.pdf", PDF + b"x" * (2 * MB), "2 MB"),
    ],
    ids=(
        "pdf-falso",
        "png-falso",
        "texto-binario",
        "zip-falso-docx",
        "zip-falso-odt",
        "arquivo-vazio",
        "acima-do-limite",
    ),
)
def test_anexo_invalido_nao_grava_e_informa_motivo(
    app, client, ids, nome, conteudo, mensagem
):
    login_as(client, ids["admin"], ids["unidade"])

    resposta = _enviar_anexo(client, ids, nome, conteudo)

    assert resposta.status_code == 400
    assert mensagem.lower() in resposta.json["erro"].lower()
    assert _arquivos(app) == []
    assert not Path(app.config["UPLOAD_FOLDER"]).exists()
    with app.app_context():
        assert Atendimento.query.count() == 0


def test_anexo_pdf_valido_usa_uuid_e_download_protegido(app, client, ids):
    login_as(client, ids["admin"], ids["unidade"])
    resposta = _enviar_anexo(client, ids, "..\\..\\anexo.pdf", PDF)

    assert resposta.status_code == 201
    with app.app_context():
        atendimento = Atendimento.query.one()
        informacao = atendimento.dados["anexo"]
        caminho_relativo = informacao["arquivo"]
        atendimento_id = atendimento.id
    assert informacao["nome"] == "..\\..\\anexo.pdf"
    assert re.fullmatch(r"atendimentos/[0-9a-f]{32}\.pdf", caminho_relativo)
    arquivo = Path(app.config["UPLOAD_FOLDER"]) / "documentos" / caminho_relativo
    assert arquivo.read_bytes() == PDF
    assert len(_arquivos(app)) == 1

    download = client.get(f"/atendimentos/{atendimento_id}/anexo")
    assert download.status_code == 200
    assert download.data == PDF
    assert download.mimetype == "application/pdf"
    assert download.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in download.headers["Cache-Control"]
    assert download.headers["Content-Disposition"].startswith("inline;")

    login_as(client, ids["pedagogico_b"], ids["outra_unidade"])
    assert client.get(f"/atendimentos/{atendimento_id}/anexo").status_code == 403

    login_as(client, ids["professor"], ids["unidade"])
    assert client.get(f"/atendimentos/{atendimento_id}/anexo").status_code == 403


def test_anexo_upload_bloqueado_para_role_sem_acesso(app, client, ids):
    login_as(client, ids["professor"], ids["unidade"])

    resposta = _enviar_anexo(client, ids, "anexo.pdf", PDF)

    assert resposta.status_code == 403
    assert _arquivos(app) == []
    assert not Path(app.config["UPLOAD_FOLDER"]).exists()
    with app.app_context():
        assert Atendimento.query.count() == 0


@pytest.mark.parametrize(
    ("nome", "conteudo"),
    [
        ("anexo.pdf", PDF),
        (
            "anexo.doc",
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            + "WordDocument".encode("utf-16le")
            + b"\x00\x00",
        ),
        ("anexo.docx", _docx_valido()),
        ("anexo.odt", _odt_valido()),
        ("anexo.rtf", b"{\\rtf1 texto}"),
        ("anexo.txt", b"texto sintetico"),
        ("anexo.png", PNG),
        ("anexo.jpg", JPEG),
        ("anexo.jpeg", JPEG),
    ],
    ids=("pdf", "doc", "docx", "odt", "rtf", "txt", "png", "jpg", "jpeg"),
)
def test_todos_os_tipos_permitidos_com_assinatura_sao_aceitos(
    app, client, ids, nome, conteudo
):
    login_as(client, ids["admin"], ids["unidade"])

    resposta = _enviar_anexo(client, ids, nome, conteudo)

    assert resposta.status_code == 201
    with app.app_context():
        informacao = Atendimento.query.one().dados["anexo"]
    assert Path(informacao["arquivo"]).suffix == Path(nome).suffix
    assert len(_arquivos(app)) == 1


@pytest.mark.parametrize(
    ("nome", "conteudo", "mensagem"),
    [
        ("fraude.png", b"texto comum", "conteúdo"),
        ("extensao-divergente.jpg", PNG, "conteúdo"),
        ("vazio.png", b"", "vazio"),
        ("grande.png", PNG + b"x" * (MAX_BYTES + 1), "5 MB"),
    ],
    ids=("png-falso", "extensao-divergente", "arquivo-vazio", "acima-do-limite"),
)
def test_modelo_invalido_nao_grava_e_informa_motivo(
    app, client, ids, nome, conteudo, mensagem
):
    login_as(client, ids["admin"], ids["unidade"])

    resposta = _enviar_modelo(client, ids, nome, conteudo)

    assert resposta.status_code == 200
    assert mensagem.lower() in resposta.get_data(as_text=True).lower()
    assert _arquivos(app) == []
    assert not Path(app.config["UPLOAD_FOLDER"]).exists()
    with app.app_context():
        assert ModeloCertificado.query.count() == 0


def test_modelo_png_valido_usa_uuid_headers_e_download(app, client, ids):
    login_as(client, ids["admin"], ids["unidade"])
    resposta = _enviar_modelo(client, ids, "..\\..\\modelo.png", PNG)
    assert resposta.status_code == 200

    with app.app_context():
        modelo = ModeloCertificado.query.one()
        nome_disco = modelo.arquivo
        assert modelo.tipo == "image/png"
        assert modelo.nome_original == "..\\..\\modelo.png"
    assert re.fullmatch(r"[0-9a-f]{32}\.png", nome_disco)
    assert (_arquivos(app)[0]).read_bytes() == PNG

    url = (
        f"/periodo-letivo/{ids['periodo']}/certificado-modelo/"
        f"{ids['centro']}/arquivo"
    )
    preview = client.get(url)
    assert preview.status_code == 200
    assert preview.data == PNG
    assert preview.mimetype == "image/png"
    assert preview.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in preview.headers["Cache-Control"]
    assert preview.headers["Content-Disposition"].startswith("inline;")

    download = client.get(url + "?download=1")
    assert download.status_code == 200
    assert "attachment" in download.headers["Content-Disposition"]


def test_modelo_upload_e_download_bloqueados_para_role_sem_acesso(
    app, client, ids
):
    login_as(client, ids["admin"], ids["unidade"])
    _enviar_modelo(client, ids, "modelo.png", PNG)
    login_as(client, ids["professor"], ids["unidade"])

    assert _enviar_modelo(client, ids, "outro.png", PNG, seguir=False).status_code == 403
    url = (
        f"/periodo-letivo/{ids['periodo']}/certificado-modelo/"
        f"{ids['centro']}/arquivo"
    )
    assert client.get(url).status_code == 403

    login_as(client, ids["pedagogico_b"], ids["outra_unidade"])
    assert client.get(url).status_code == 403
