"""AJ5-C (E3b) — `salvar_informacao_padrao` não pode engolir HTTPException.

O `try/except Exception` do POST de informações padrão capturava também a
`RequestEntityTooLarge` (413) que o Werkzeug levanta ao estourar
`MAX_CONTENT_LENGTH` durante `upsert_informacao_padrao(request.form, ...)` —
a mensagem genérica "Nao foi possivel salvar..." escondia a causa real e o
handler global 413 (flash amigável com o teto, AJ5-B) nunca rodava.

Fix no espírito do AJ5-B (`except HTTPException: raise` nas rotas de aluno).
Storage/DB só em tmp_path/:memory:; nenhum dado real.
"""

import io

import pytest

from app import create_app, db
from app.models import Unidade, User
from config import Config
from _helpers import login_as


class Aj5cInfoConfig(Config):
    SECRET_KEY = "chave-de-teste-aj5c-info-1234567890abcdef"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app_info(tmp_path):
    test_app = create_app(Aj5cInfoConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        UPLOAD_FOLDER=str(tmp_path / "uploads"),
        MAX_CONTENT_LENGTH=1024 * 1024,  # 1 MB p/ o teste mandar acima
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin(app_info):
    with app_info.app_context():
        unidade = Unidade(nome="Unidade Info Aj5c", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        user = User(
            name="Admin Info Aj5c", email="admin.info.aj5c@example.com",
            role="admin", unidade_id=unidade.id, is_active=True, first_login=False,
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def test_413_nao_engolido_flash_amigavel_do_handler_global(app_info, admin):
    client = app_info.test_client()
    login_as(client, admin)

    resposta = client.post(
        "/admin/informacao-padrao",
        data={
            "razao_social": "Instituto Fictício Aj5c",
            "logo": (io.BytesIO(b"x" * 2 * 1024 * 1024), "logo_grande.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    corpo = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "Traceback" not in corpo
    # mensagem do handler global de 413 (AJ5-B), não a genérica do except
    assert "Envio recusado" in corpo and "1 MB" in corpo, (
        "[AJ5-C/E3b] o 413 deve chegar ao handler global (flash amigável com "
        "o teto), e não ser engolido pelo `except Exception` da rota"
    )
    assert "Nao foi possivel salvar" not in corpo

    # nada foi gravado
    with app_info.app_context():
        from app.services.informacao_padrao import get_informacao_padrao_values
        valores = get_informacao_padrao_values()
        assert (valores.get("razao_social") or "") != "Instituto Fictício Aj5c"
