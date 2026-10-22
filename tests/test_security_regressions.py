import pytest
from flask_login import login_user
from werkzeug.exceptions import Forbidden

from app import create_app
from app.database import db
from app.models import User, Unidade, Aluno, Turma, Curso, TemaAula
from app.registros.shared import assert_unidade_context
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with test_app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_local_login_succeeds_with_audited_turma_model(client, app):
    with app.app_context():
        user = User(
            name="Administrador",
            email="admin@example.com",
            role="admin",
            first_login=False,
        )
        user.set_password("SenhaLocal!123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "SenhaLocal!123"},
    )

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session["_user_id"]


def test_pending_user_redirected_to_approval_screen(client, app):
    with app.app_context():
        user = User(
            name="Usuário Pendente",
            email="pendente@example.com",
            role="pendente",
            first_login=False,
        )
        user.set_password("Abc12345!")
        db.session.add(user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/aguardando-aprovacao")


def test_first_login_user_redirected_to_password_change(client, app):
    with app.app_context():
        user = User(
            name="Usuário Primeiro Acesso",
            email="primeiro@example.com",
            role="professor",
            first_login=True,
        )
        user.set_password("Abc12345!")
        db.session.add(user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        resp = client.get("/dashboard", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/trocar-senha")


def test_change_password_requires_current_password(client, app):
    with app.app_context():
        user = User(
            name="Usuário Senha",
            email="senha@example.com",
            role="professor",
            first_login=False,
        )
        user.set_password("SenhaAtual!1")
        db.session.add(user)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        resp = client.post(
            "/trocar-senha",
            data={
                "nova_senha": "NovaSenha!2",
                "confirma_senha": "NovaSenha!2",
                "senha_atual": "SenhaErrada!9",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/trocar-senha")

        updated = db.session.get(User, user.id)
        assert updated.check_password("SenhaAtual!1")
        assert not updated.check_password("NovaSenha!2")


def test_assert_unidade_context_rejects_missing_local_unidade():
    with pytest.raises(Forbidden):
        assert_unidade_context(10, None)


def test_historico_aluno_rejects_unrelated_professor(client, app):
    with app.app_context():
        unidade = Unidade(nome="Unidade A", ativo=True)
        db.session.add(unidade)
        db.session.commit()

        professor = User(
            name="Professor Sem Turma",
            email="professor_sem_turma@example.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        professor.set_password("Abc12345!")
        db.session.add(professor)
        db.session.commit()

        aluno = Aluno(nome="Aluno X", nome_social="Aluno", ativo=True, unidade_id=unidade.id)
        db.session.add(aluno)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(professor.id)
            sess["_fresh"] = True

        resp = client.get(f"/aluno/{aluno.id}/historico")
        assert resp.status_code == 403


def test_api_alunos_requires_authorized_role(client, app):
    with app.app_context():
        unidade = Unidade(nome="Unidade B", ativo=True)
        db.session.add(unidade)
        db.session.commit()

        professor = User(
            name="Professor Sem Acesso",
            email="professor_sem_acesso@example.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        professor.set_password("Abc12345!")
        db.session.add(professor)
        db.session.commit()

        turma = Turma(nome="Turma 7A", ativo=True, unidade_id=unidade.id)
        db.session.add(turma)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(professor.id)
            sess["_fresh"] = True

        resp = client.get(f"/api/alunos/{turma.id}")
        assert resp.status_code == 403


def test_mutating_routes_reject_get_requests(client):
    routes = [
        "/aluno/excluir/1",
        "/aluno/inativar/1",
        "/turma/desenturmar/1",
        "/periodo-letivo/inativar/1",
        "/periodo-letivo/ativar/1",
        "/servico-social/excluir-agendamento/1",
    ]

    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 405


def _criar_admin_cursos(client, app):
    with app.app_context():
        unidade_a = Unidade(nome="Unidade Cursos A", ativo=True)
        unidade_b = Unidade(nome="Unidade Cursos B", ativo=True)
        db.session.add_all([unidade_a, unidade_b])
        db.session.flush()

        admin = User(
            name="Admin Cursos",
            email="admin.cursos@example.com",
            role="admin",
            first_login=False,
        )
        admin.set_password("SenhaLocal!123")
        db.session.add(admin)
        db.session.flush()

        with app.test_request_context():
            login_user(admin)
            curso_a = Curso(nome="Curso A", unidade_id=unidade_a.id, ativo=True)
            curso_b = Curso(nome="Curso B", unidade_id=unidade_b.id, ativo=True)
            db.session.add_all([curso_a, curso_b])
            db.session.commit()
        user_id = admin.id
        unidade_a_id = unidade_a.id
        curso_a_id = curso_a.id
        curso_b_id = curso_b.id

    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
        sess["unidade_id"] = unidade_a_id

    return curso_a_id, curso_b_id


def test_cursos_exigem_unidade_e_isolam_cursos_de_outra_unidade(client, app):
    curso_a_id, curso_b_id = _criar_admin_cursos(client, app)

    response = client.get("/cursos")
    assert response.status_code == 200
    assert [curso["id"] for curso in response.json] == [curso_a_id]

    response = client.post(
        f"/cursos/{curso_b_id}/editar",
        json={"nome": "Alterado", "descricao": "", "carga_horaria": None},
    )
    assert response.status_code == 403

    response = client.post(f"/cursos/{curso_b_id}/inativar")
    assert response.status_code == 403

    with client.session_transaction() as sess:
        sess.pop("unidade_id", None)

    assert client.get("/cursos").status_code == 403
    assert client.post("/cursos/novo", json={"nome": "Sem unidade"}).status_code == 400
    assert client.post(
        f"/cursos/{curso_a_id}/editar", json={"nome": "Alterado"}
    ).status_code == 403
    assert client.post(f"/cursos/{curso_a_id}/inativar").status_code == 403


def test_curso_criar_editar_inativar_e_validar_carga_horaria(client, app):
    curso_a_id, _ = _criar_admin_cursos(client, app)

    response = client.post(
        "/cursos/novo",
        json={"nome": "Novo curso", "descricao": "Descrição", "carga_horaria": 40},
    )
    assert response.status_code == 200
    curso_novo_id = response.json["id"]

    response = client.post(
        "/cursos/novo",
        json={"nome": "Carga inválida", "carga_horaria": "inválida"},
    )
    assert response.status_code == 400

    response = client.post(
        f"/cursos/{curso_a_id}/editar",
        json={"nome": "Curso editado", "descricao": "Atualizado", "carga_horaria": 60},
    )
    assert response.status_code == 200
    assert response.json["nome"] == "Curso editado"
    assert response.json["carga_horaria"] == 60

    response = client.post(f"/cursos/{curso_a_id}/inativar")
    assert response.status_code == 200
    assert response.json["success"] is True

    with app.app_context():
        curso_excluido = db.session.get(Curso, curso_a_id)
        assert curso_excluido.ativo is False

    response = client.get("/cursos")
    assert response.status_code == 200
    assert [curso["id"] for curso in response.json] == [curso_novo_id]


def test_inativar_curso_preserva_temas_e_permite_reativacao(client, app):
    curso_id, _ = _criar_admin_cursos(client, app)
    with app.app_context():
        curso = db.session.get(Curso, curso_id)
        tema = TemaAula(
            curso_id=curso.id,
            unidade_id=curso.unidade_id,
            titulo="Tema histórico preservado",
            ordem=1,
            ativo=True,
        )
        db.session.add(tema)
        db.session.commit()
        tema_id = tema.id

    response = client.post(f"/cursos/{curso_id}/inativar")
    assert response.status_code == 200
    assert response.json["success"] is True
    assert "preservados" in response.json["message"]
    assert client.get("/cursos").json == []
    assert [curso["id"] for curso in client.get("/cursos/inativos").json] == [curso_id]

    response = client.get("/planejamento")
    assert response.status_code == 200
    assert b"Tema hist" not in response.data

    response = client.post(f"/cursos/{curso_id}/reativar")
    assert response.status_code == 200
    assert [curso["id"] for curso in client.get("/cursos").json] == [curso_id]

    response = client.get("/planejamento")
    assert "Tema histórico preservado".encode() in response.data

    with app.app_context():
        curso = db.session.get(Curso, curso_id)
        tema = db.session.get(TemaAula, tema_id)
        assert curso.ativo is True
        assert tema.ativo is True
        assert tema.titulo == "Tema histórico preservado"


def test_nao_permite_criar_tema_em_curso_inativo(client, app):
    curso_id, _ = _criar_admin_cursos(client, app)
    client.post(f"/cursos/{curso_id}/inativar")

    response = client.post(
        "/planejamento",
        data={"curso_id": str(curso_id), "titulo": "Tema não permitido"},
    )
    assert response.status_code == 302

    with app.app_context():
        assert TemaAula.query.filter_by(
            curso_id=curso_id,
            titulo="Tema não permitido",
        ).first() is None


def test_nao_permite_vincular_curso_inativo_a_nova_turma(client, app):
    curso_id, _ = _criar_admin_cursos(client, app)
    client.post(f"/cursos/{curso_id}/inativar")

    response = client.post(
        "/turma/nova",
        data={
            "turma": "Turma sem curso inativo",
            "dias_semana": ["Segunda"],
            "curso_id": str(curso_id),
            "turno": "Manhã",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        assert Turma.query.filter_by(nome="Turma sem curso inativo").first() is None
