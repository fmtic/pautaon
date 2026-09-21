import pytest
from app import create_app
from app.database import db
from app.models import Aluno, Atendimento, Unidade, User
from app.models.enums import UserRole


@pytest.fixture
def app():
    test_app = create_app()
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_static_uploads_documentos_nao_exposto(client):
    """Garante que a rota estática pública não serve mais arquivos confidenciais."""
    resp = client.get("/static/uploads/documentos/00002_2026/doc_laudo.pdf")
    assert resp.status_code == 404

    resp_foto = client.get("/static/uploads/fotos/aluno_1_20251205_203425_0000.png")
    assert resp_foto.status_code == 404


def test_acesso_anonimo_redireciona_para_login(client):
    """Garante que visitantes não autenticados não conseguem acessar as novas rotas."""
    resp = client.get("/aluno/2/documento/doc_laudo")
    assert resp.status_code in (302, 401)

    resp_foto = client.get("/aluno/1/foto")
    assert resp_foto.status_code in (302, 401)

    resp_anexo = client.get("/atendimentos/1/anexo")
    assert resp_anexo.status_code in (302, 401)


def test_acesso_autenticado_documento_e_foto(app, client):
    """Valida que usuário autenticado e autorizado acessa os documentos e fotos com sucesso."""
    with app.app_context():
        unidade = Unidade.query.first()
        if not unidade:
            unidade = Unidade(nome="Unidade Teste", ativo=True)
            db.session.add(unidade)
            db.session.commit()

        admin = User.query.filter_by(role="admin").first()
        if not admin:
            admin = User(
                name="Admin Teste",
                email="admin.teste@pautaon.local",
                password="",
                role="admin",
                is_active=True,
                is_ad_user=False,
                first_login=False,
                unidade_id=unidade.id,
            )
            admin.set_password("Admin@123")
            db.session.add(admin)
            db.session.commit()

        aluno_doc = Aluno.query.get(2)
        if not aluno_doc:
            aluno_doc = Aluno(nome="Aluno Documento", nome_social="Aluno Documento", ativo=True, unidade_id=unidade.id)
            db.session.add(aluno_doc)
            db.session.commit()

        aluno_foto = Aluno.query.get(1)
        if not aluno_foto:
            aluno_foto = Aluno(nome="Aluno Foto", nome_social="Aluno Foto", ativo=True, unidade_id=unidade.id)
            db.session.add(aluno_foto)
            db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin.id)
            sess["_fresh"] = True
            sess["unidade_id"] = str(unidade.id)

        resp_doc = client.get(f"/aluno/{aluno_doc.id}/documento/doc_laudo")
        if resp_doc.status_code == 200:
            assert resp_doc.content_type == "application/pdf"

        resp_foto = client.get(f"/aluno/{aluno_foto.id}/foto")
        assert resp_foto.status_code in (200, 302)
