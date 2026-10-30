"""Upload e entrega da foto do aluno (S1-08).

`salvar_foto` aceitava qualquer arquivo: `foto.html`/`foto.svg` era gravado em
`uploads/fotos` e servido por `/aluno/<id>/foto`. Agora a gravação valida
whitelist de extensão, conteúdo real (assinatura de bytes — o Pillow não está no
`requirements.txt`), limite de 2 MB e nome gerado pelo servidor; a entrega usa
mimetype fixo pela extensão validada e `X-Content-Type-Options: nosniff`.
"""

import base64
import io
import re
import struct
import zlib

import pytest
from werkzeug.datastructures import FileStorage

from app import create_app, db
from app.models import Aluno, Unidade, User
from app.utils.fotos import (
    FOTO_MAX_BYTES,
    MSG_CONTEUDO,
    MSG_EXTENSAO,
    MSG_TAMANHO,
    MSG_VAZIA,
    validar_foto,
)
from config import Config
from _helpers import login_as

#: 1x1 JPEG de verdade (160 bytes) — a validação de conteúdo é por assinatura.
JPG_VALIDO = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)


def _png_1x1() -> bytes:
    """PNG 1x1 RGB montado na mão (assinatura + IHDR + IDAT + IEND)."""
    def bloco(tipo: bytes, dados: bytes) -> bytes:
        crc = zlib.crc32(tipo + dados) & 0xFFFFFFFF
        return struct.pack(">I", len(dados)) + tipo + dados + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + bloco(b"IHDR", ihdr) + bloco(b"IDAT", idat) + bloco(b"IEND", b"")


PNG_VALIDO = _png_1x1()


class FotoTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app(tmp_path):
    test_app = create_app(FotoTestConfig)
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
        ua = Unidade(nome="Unidade Foto A", ativo=True)
        ub = Unidade(nome="Unidade Foto B", ativo=True)
        db.session.add_all([ua, ub])
        db.session.flush()

        admin_a = User(
            name="Admin Foto A", email="admin.foto.a@example.com", role="admin",
            unidade_id=ua.id, is_active=True, first_login=False,
        )
        professor_a = User(
            name="Professor Foto A", email="prof.foto.a@example.com", role="professor",
            unidade_id=ua.id, is_active=True, first_login=False,
        )
        db.session.add_all([admin_a, professor_a])

        aluno_a = Aluno(nome="Aluno Foto A", ativo=True, unidade_id=ua.id)
        aluno_b = Aluno(nome="Aluno Foto B", ativo=True, unidade_id=ub.id)
        db.session.add_all([aluno_a, aluno_b])
        db.session.commit()

        return {
            "unidade_a": ua.id,
            "unidade_b": ub.id,
            "admin": admin_a.id,
            "professor": professor_a.id,
            "aluno_a": aluno_a.id,
            "aluno_b": aluno_b.id,
            "pasta_fotos": app.config["UPLOAD_FOLDER"] + "/fotos",
        }


def _foto(nome: str, conteudo: bytes) -> FileStorage:
    return FileStorage(stream=io.BytesIO(conteudo), filename=nome)


def _enviar(client, aluno_id, nome_arquivo, conteudo):
    """POST de edição do aluno com a foto; devolve a resposta (302 esperado)."""
    return client.post(
        f"/aluno/editar/{aluno_id}",
        data={
            "nome": "Aluno Foto A",
            "cpf": "11144477735",
            "foto": (io.BytesIO(conteudo), nome_arquivo),
        },
        content_type="multipart/form-data",
    )


def _flashes(client) -> list[str]:
    with client.session_transaction() as sess:
        return [mensagem for _categoria, mensagem in sess.get("_flashes", [])]


def _arquivos(dados) -> list[str]:
    from pathlib import Path

    pasta = Path(dados["pasta_fotos"])
    return sorted(p.name for p in pasta.iterdir()) if pasta.is_dir() else []


# ---------------------------------------------------------------------------
# Validação pura
# ---------------------------------------------------------------------------

def test_extensoes_fora_da_whitelist_sao_recusadas():
    for nome in ("foto.svg", "foto.html", "foto.gif", "foto.php", "foto", "foto.svgz"):
        erro, extensao = validar_foto(_foto(nome, PNG_VALIDO))
        assert erro == MSG_EXTENSAO, nome
        assert extensao is None


def test_html_renomeado_como_png_e_recusado():
    erro, _ = validar_foto(_foto("foto.png", b"<html><script>alert(1)</script></html>"))
    assert erro == MSG_CONTEUDO


def test_extensao_valida_com_conteudo_invalido_e_recusada():
    erro, _ = validar_foto(_foto("foto.jpg", b"isto nao e uma imagem"))
    assert erro == MSG_CONTEUDO


def test_arquivo_vazio_e_recusado():
    erro, _ = validar_foto(_foto("foto.png", b""))
    assert erro == MSG_VAZIA


def test_acima_de_dois_mb_e_recusado():
    grande = PNG_VALIDO + b"\x00" * (FOTO_MAX_BYTES + 1 - len(PNG_VALIDO))
    erro, _ = validar_foto(_foto("foto.png", grande))
    assert erro == MSG_TAMANHO


def test_conteudo_manda_na_extensao_gravada():
    # Assinatura JPEG num arquivo chamado `.png`: a extensão gravada vem do
    # conteúdo (jpg), não do nome enviado.
    erro, extensao = validar_foto(_foto("foto.png", JPG_VALIDO))
    assert erro is None
    assert extensao == "jpg"


# ---------------------------------------------------------------------------
# Gravação e entrega pela rota
# ---------------------------------------------------------------------------

def test_png_valido_e_gravado_com_nome_do_servidor(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])

    assert _enviar(client, dados["aluno_a"], "minha-foto.png", PNG_VALIDO).status_code == 302

    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno_a"])
        nome_gravado = aluno.foto_path
        assert re.fullmatch(rf"aluno_{dados['aluno_a']}_[0-9a-f]{{32}}\.png", nome_gravado)

    assert _arquivos(dados) == [nome_gravado]

    resposta = client.get(f"/aluno/{dados['aluno_a']}/foto")
    assert resposta.status_code == 200
    assert resposta.headers["Content-Type"] == "image/png"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"


def test_jpg_valido_e_servido_como_jpeg(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])

    assert _enviar(client, dados["aluno_a"], "retrato.jpg", JPG_VALIDO).status_code == 302

    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno_a"])
        assert aluno.foto_path.endswith(".jpg")

    resposta = client.get(f"/aluno/{dados['aluno_a']}/foto")
    assert resposta.status_code == 200
    assert resposta.headers["Content-Type"] == "image/jpeg"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"


def test_nome_do_cliente_nao_chega_ao_disco(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])

    _enviar(client, dados["aluno_a"], "..\\..\\evil script.png", PNG_VALIDO)

    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno_a"])
    assert "evil" not in aluno.foto_path
    assert "/" not in aluno.foto_path and "\\" not in aluno.foto_path


def test_png_invalido_nao_grava_nada_e_avisa_por_flash(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])

    assert _enviar(client, dados["aluno_a"], "foto.png", b"<html>x</html>").status_code == 302

    assert MSG_CONTEUDO in _flashes(client)
    with app.app_context():
        assert db.session.get(Aluno, dados["aluno_a"]).foto_path is None
    assert _arquivos(dados) == []


def test_svg_recusado_pela_extensao_nao_grava_nada(app, client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])

    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert _enviar(client, dados["aluno_a"], "foto.svg", svg).status_code == 302

    assert MSG_EXTENSAO in _flashes(client)
    with app.app_context():
        assert db.session.get(Aluno, dados["aluno_a"]).foto_path is None
    assert _arquivos(dados) == []


# ---------------------------------------------------------------------------
# Acesso continua como antes
# ---------------------------------------------------------------------------

def test_professor_nao_pode_editar_aluno_para_subir_foto(client, dados):
    login_as(client, dados["professor"], dados["unidade_a"])

    assert _enviar(client, dados["aluno_a"], "foto.png", PNG_VALIDO).status_code == 403
    assert _arquivos(dados) == []


def test_aluno_de_outra_unidade_recusa_o_upload(client, dados):
    login_as(client, dados["admin"], dados["unidade_a"])

    assert _enviar(client, dados["aluno_b"], "foto.png", PNG_VALIDO).status_code == 403
    assert _arquivos(dados) == []


def test_professor_sem_vinculo_nao_ve_a_foto(app, client, dados):
    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno_a"])
        aluno.foto_path = "aluno_1_abc.png"
        db.session.commit()

    login_as(client, dados["professor"], dados["unidade_a"])
    assert client.get(f"/aluno/{dados['aluno_a']}/foto").status_code == 403


def test_foto_antiga_fora_da_whitelist_continua_sendo_servida(app, client, dados):
    """Fotos já gravadas não são migradas: o arquivo antigo é servido como antes."""
    from pathlib import Path

    pasta = Path(dados["pasta_fotos"])
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "aluno_1_antiga.bmp").write_bytes(b"BM" + b"\x00" * 30)

    with app.app_context():
        aluno = db.session.get(Aluno, dados["aluno_a"])
        aluno.foto_path = "aluno_1_antiga.bmp"
        db.session.commit()

    login_as(client, dados["admin"], dados["unidade_a"])
    resposta = client.get(f"/aluno/{dados['aluno_a']}/foto")

    assert resposta.status_code == 200
    assert resposta.headers["Content-Type"] == "application/octet-stream"
    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
