"""Modelos de certificado por centro de custo do período (upload/CRUD).

Fase 1: imagem PNG/JPG por par (período, centro de custo), servida só por rota
autenticada; o uso como fundo do certificado impresso vem depois.
"""

import io
import shutil
import tempfile
from datetime import date
from pathlib import Path

import pytest

from _helpers import login_as

from app import create_app, db
from app.models import CentroCusto, ModeloCertificado, PeriodoLetivo, Unidade, User
from app.services.certificado_modelo import MAX_BYTES, centros_do_periodo
from config import Config

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 256
PNG_2 = b"\x89PNG\r\n\x1a\n" + b"1" * 512


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    # Diretório próprio (e limpo no fim) para os uploads do teste: não deixa
    # sobra no repositório nem depende do basetemp do pytest.
    pasta_uploads = tempfile.mkdtemp(prefix="certificado_modelo_")
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        UPLOAD_FOLDER=pasta_uploads,
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()
    shutil.rmtree(pasta_uploads, ignore_errors=True)


def _usuario(nome, email, role, unidade_id):
    user = User(name=nome, email=email, role=role, first_login=False,
                unidade_id=unidade_id)
    user.set_password("SenhaLocal!123")
    return user


def _seed(app):
    with app.app_context():
        un_a = Unidade(nome="Unidade A", ativo=True)
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add_all([un_a, un_b])
        db.session.flush()

        usuarios = {
            "admin": _usuario("Admin CM", "admin.cm@x.com", "admin", un_a.id),
            "pedagogico": _usuario("Ped CM", "ped.cm@x.com", "pedagogico", un_a.id),
            "secretaria": _usuario("Sec CM", "sec.cm@x.com", "secretaria", un_a.id),
            "gerencia": _usuario("Ger CM", "ger.cm@x.com", "gerencia", un_a.id),
            "professor": _usuario("Prof CM", "prof.cm@x.com", "professor", un_a.id),
            "pedagogico_b": _usuario("Ped B", "pedb.cm@x.com", "pedagogico", un_b.id),
            "gerencia_b": _usuario("Ger B", "gerb.cm@x.com", "gerencia", un_b.id),
        }
        db.session.add_all(usuarios.values())
        db.session.flush()

        cc1 = CentroCusto(nome="Centro A1", unidade_id=un_a.id, ativo=True)
        cc2 = CentroCusto(nome="Centro A2", unidade_id=un_a.id, ativo=True)
        cc3 = CentroCusto(nome="Centro A3", unidade_id=un_a.id, ativo=False)
        cc_b = CentroCusto(nome="Centro B1", unidade_id=un_b.id, ativo=True)
        db.session.add_all([cc1, cc2, cc3, cc_b])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="2026.1", data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 6, 30), unidade_id=un_a.id,
            centro_custo="Centro A1, Centro A2",
        )
        periodo_2 = PeriodoLetivo(
            nome="2026.2", data_inicio=date(2026, 8, 1),
            data_fim=date(2026, 12, 15), unidade_id=un_a.id,
            centro_custo="Centro A1",
        )
        periodo_sem_centros = PeriodoLetivo(
            nome="2027.1", data_inicio=date(2027, 2, 1),
            data_fim=date(2027, 6, 30), unidade_id=un_a.id, centro_custo=None,
        )
        periodo_b = PeriodoLetivo(
            nome="2026.1-B", data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 6, 30), unidade_id=un_b.id,
            centro_custo="Centro B1",
        )
        db.session.add_all(
            [periodo, periodo_2, periodo_sem_centros, periodo_b]
        )
        db.session.commit()

        return {
            "un_a": un_a.id,
            "un_b": un_b.id,
            "usuarios": {chave: u.id for chave, u in usuarios.items()},
            "cc1": cc1.id,
            "cc2": cc2.id,
            "cc3": cc3.id,
            "cc_b": cc_b.id,
            "periodo": periodo.id,
            "periodo_2": periodo_2.id,
            "periodo_sem_centros": periodo_sem_centros.id,
            "periodo_b": periodo_b.id,
        }


def _pasta(app, periodo_id):
    return Path(app.config["UPLOAD_FOLDER"]) / "certificados" / str(periodo_id)


def _arquivos(app, periodo_id):
    pasta = _pasta(app, periodo_id)
    return sorted(p.name for p in pasta.iterdir()) if pasta.is_dir() else []


def _enviar(client, ids, centro_id, *, periodo_id=None, nome="modelo.png",
            conteudo=PNG, seguir=False):
    return client.post(
        f"/periodo-letivo/{periodo_id or ids['periodo']}"
        f"/certificado-modelo/{centro_id}",
        data={"arquivo": (io.BytesIO(conteudo), nome)},
        content_type="multipart/form-data",
        follow_redirects=seguir,
    )


def _html(client, ids, periodo_id=None, usuario="pedagogico", unidade=None):
    login_as(client, ids["usuarios"][usuario], unidade or ids["un_a"])
    resposta = client.get(
        f"/periodo-letivo/relatorio/{periodo_id or ids['periodo']}"
    )
    return resposta.status_code, resposta.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Serviço / upload
# ---------------------------------------------------------------------------

def test_envia_modelo_e_grava_arquivo(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])

    resposta = _enviar(client, ids, ids["cc1"])

    assert resposta.status_code == 302
    with app.app_context():
        modelo = ModeloCertificado.query.one()
        assert modelo.periodo_letivo_id == ids["periodo"]
        assert modelo.centro_custo_id == ids["cc1"]
        assert modelo.nome_original == "modelo.png"
        assert modelo.tipo == "image/png"
        assert modelo.tamanho == len(PNG)
        arquivo = modelo.arquivo
    assert _arquivos(app, ids["periodo"]) == [arquivo]
    assert (_pasta(app, ids["periodo"]) / arquivo).read_bytes() == PNG


def test_substituir_apaga_arquivo_anterior(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])
    _enviar(client, ids, ids["cc1"])

    with app.app_context():
        primeiro = ModeloCertificado.query.one().arquivo

    _enviar(client, ids, ids["cc1"], nome="modelo2.jpg", conteudo=PNG_2)

    with app.app_context():
        assert ModeloCertificado.query.count() == 1
        modelo = ModeloCertificado.query.one()
        assert modelo.arquivo != primeiro
        assert modelo.nome_original == "modelo2.jpg"
        assert modelo.tipo == "image/jpeg"
        segundo = modelo.arquivo

    assert _arquivos(app, ids["periodo"]) == [segundo]
    assert (_pasta(app, ids["periodo"]) / primeiro).exists() is False


def test_remover_apaga_linha_e_arquivo(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])
    _enviar(client, ids, ids["cc1"])

    resposta = client.post(
        f"/periodo-letivo/{ids['periodo']}/certificado-modelo/{ids['cc1']}/remover"
    )

    assert resposta.status_code == 302
    with app.app_context():
        assert ModeloCertificado.query.count() == 0
    assert _arquivos(app, ids["periodo"]) == []


def test_formato_invalido_nao_grava_nada(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])

    resposta = _enviar(client, ids, ids["cc1"], nome="modelo.pdf", seguir=True)

    assert "Formato inválido" in resposta.get_data(as_text=True)
    with app.app_context():
        assert ModeloCertificado.query.count() == 0
    assert _arquivos(app, ids["periodo"]) == []


def test_arquivo_ausente_nao_grava_nada(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])

    resposta = client.post(
        f"/periodo-letivo/{ids['periodo']}/certificado-modelo/{ids['cc1']}",
        data={},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert "Selecione o arquivo do modelo" in resposta.get_data(as_text=True)
    with app.app_context():
        assert ModeloCertificado.query.count() == 0


def test_limite_de_tamanho(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])

    grande = b"\x89PNG\r\n\x1a\n" + b"0" * (MAX_BYTES + 1)
    resposta = _enviar(client, ids, ids["cc1"], conteudo=grande, seguir=True)

    assert "excede o limite de 5 MB" in resposta.get_data(as_text=True)
    with app.app_context():
        assert ModeloCertificado.query.count() == 0
    assert _arquivos(app, ids["periodo"]) == []


# ---------------------------------------------------------------------------
# Permissões e isolamento
# ---------------------------------------------------------------------------

# Professor segue fora; gerência entrou em 29/10/2026 (decisão do usuário —
# `_ROLES_PERIODO` agora inclui gerencia), então saiu deste parametrize e foi
# para `test_perfis_de_periodos_enviam`.
@pytest.mark.parametrize("perfil", ["professor"])
def test_perfis_sem_acesso_nao_enviam(app, client, perfil):
    ids = _seed(app)
    login_as(client, ids["usuarios"][perfil], ids["un_a"])

    resposta = _enviar(client, ids, ids["cc1"])

    assert resposta.status_code == 403
    with app.app_context():
        assert ModeloCertificado.query.count() == 0


@pytest.mark.parametrize(
    "perfil", ["admin", "pedagogico", "secretaria", "gerencia"]
)
def test_perfis_de_periodos_enviam(app, client, perfil):
    ids = _seed(app)
    login_as(client, ids["usuarios"][perfil], ids["un_a"])

    assert _enviar(client, ids, ids["cc1"]).status_code == 302
    with app.app_context():
        assert ModeloCertificado.query.count() == 1


@pytest.mark.parametrize("perfil", ["pedagogico_b", "gerencia_b"])
def test_outra_unidade_recebe_403(app, client, perfil):
    """Não-admin de outra unidade continua 403 (`assert_unidade_context`),
    inclusive a gerência recém-incluída em `_ROLES_PERIODO`."""
    ids = _seed(app)
    login_as(client, ids["usuarios"][perfil], ids["un_b"])

    resposta = _enviar(client, ids, ids["cc_b"])

    assert resposta.status_code == 403
    with app.app_context():
        assert ModeloCertificado.query.count() == 0


def test_centro_de_outra_unidade_recusa(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])

    resposta = _enviar(client, ids, ids["cc_b"])

    assert resposta.status_code == 404
    with app.app_context():
        assert ModeloCertificado.query.count() == 0


def test_modelos_isolados_por_periodo(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])

    _enviar(client, ids, ids["cc1"])

    with app.app_context():
        assert ModeloCertificado.query.filter_by(
            periodo_letivo_id=ids["periodo"]
        ).count() == 1
        assert ModeloCertificado.query.filter_by(
            periodo_letivo_id=ids["periodo_2"]
        ).count() == 0
    assert _arquivos(app, ids["periodo_2"]) == []


# ---------------------------------------------------------------------------
# Arquivo (preview/download)
# ---------------------------------------------------------------------------

def test_arquivo_exige_login(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])
    _enviar(client, ids, ids["cc1"])

    # S1-16: logout só por POST (GET é inócuo).
    client.post("/logout")
    resposta = client.get(
        f"/periodo-letivo/{ids['periodo']}/certificado-modelo/{ids['cc1']}/arquivo"
    )
    assert resposta.status_code in (302, 401)


def test_arquivo_devolve_conteudo_e_download(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])
    _enviar(client, ids, ids["cc1"])

    url = f"/periodo-letivo/{ids['periodo']}/certificado-modelo/{ids['cc1']}/arquivo"
    resposta = client.get(url)
    assert resposta.status_code == 200
    assert resposta.mimetype == "image/png"
    assert resposta.data == PNG

    download = client.get(url + "?download=1")
    assert download.status_code == 200
    assert "attachment" in download.headers["Content-Disposition"]
    assert "modelo.png" in download.headers["Content-Disposition"]


def test_arquivo_sem_modelo_404(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])

    resposta = client.get(
        f"/periodo-letivo/{ids['periodo']}/certificado-modelo/{ids['cc1']}/arquivo"
    )
    assert resposta.status_code == 404


# ---------------------------------------------------------------------------
# Página de certificados
# ---------------------------------------------------------------------------

def test_pagina_lista_centros_do_periodo(app, client):
    ids = _seed(app)
    status, html = _html(client, ids)

    assert status == 200
    assert 'id="modelos-certificado"' in html
    assert "Centro A1" in html
    assert "Centro A2" in html
    assert "Centro B1" not in html
    assert "Enviar" in html


def test_pagina_mostra_modelo_enviado(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])
    _enviar(client, ids, ids["cc1"])

    status, html = _html(client, ids)

    assert status == 200
    assert "Substituir" in html
    assert "Baixar" in html
    assert "Remover" in html
    assert f"/certificado-modelo/{ids['cc1']}/arquivo" in html


def test_periodo_sem_centros_mostra_aviso(app, client):
    ids = _seed(app)
    status, html = _html(client, ids, periodo_id=ids["periodo_sem_centros"])

    assert status == 200
    assert "Nenhum centro de custo definido neste período" in html


def test_centro_fora_do_catalogo_nao_permite_upload(app):
    ids = _seed(app)
    with app.app_context():
        periodo = db.session.get(PeriodoLetivo, ids["periodo"])
        periodo.centro_custo = "Centro A1, Centro Fantasma"
        db.session.commit()
        linhas = {linha["nome"]: linha for linha in centros_do_periodo(periodo)}

    assert linhas["Centro Fantasma"]["centro"] is None
    assert linhas["Centro Fantasma"]["modelo"] is None
    assert linhas["Centro A1"]["centro"] is not None


def test_centro_inativo_aparece_marcado(app):
    ids = _seed(app)
    with app.app_context():
        periodo = db.session.get(PeriodoLetivo, ids["periodo"])
        periodo.centro_custo = "Centro A1, Centro A3"
        db.session.commit()
        linhas = {linha["nome"]: linha for linha in centros_do_periodo(periodo)}

    assert linhas["Centro A3"]["centro"] is not None
    assert linhas["Centro A3"]["ativo"] is False


def test_modelo_de_centro_fora_do_periodo_continua_listado(app, client):
    ids = _seed(app)
    login_as(client, ids["usuarios"]["pedagogico"], ids["un_a"])
    _enviar(client, ids, ids["cc2"])

    with app.app_context():
        periodo = db.session.get(PeriodoLetivo, ids["periodo"])
        periodo.centro_custo = "Centro A1"
        db.session.commit()

    status, html = _html(client, ids)

    assert status == 200
    assert "Centro A2" in html
    assert "fora do período" in html
    assert "Remover" in html
