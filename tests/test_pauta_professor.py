from app import create_app, db
from app.models import Aluno, Curso, Inscricao, Turma, Unidade, User
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


def test_professor_pauta_mostra_somente_alunos_da_turma_associada():
    app = create_app(SQLiteTestConfig)
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="Unidade da pauta", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        professor = User(
            name="Professor da Natação",
            email="pauta.professor@example.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        curso = Curso(nome="Natação", unidade_id=unidade.id, ativo=True)
        db.session.add_all([professor, curso])
        db.session.flush()

        turma_associada = Turma(
            nome="Natação - Turma A",
            unidade_id=unidade.id,
            curso_id=curso.id,
            professor_id=professor.id,
            ativo=True,
        )
        turma_nao_associada = Turma(
            nome="Natação - Turma B",
            unidade_id=unidade.id,
            curso_id=curso.id,
            ativo=True,
        )
        aluno_associado = Aluno(
            nome="Aluno da Turma A",
            nome_social="Aluno A",
            unidade_id=unidade.id,
            ativo=True,
        )
        aluno_de_outra_turma = Aluno(
            nome="Aluno da Turma B",
            nome_social="Aluno B",
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add_all(
            [
                turma_associada,
                turma_nao_associada,
                aluno_associado,
                aluno_de_outra_turma,
            ]
        )
        db.session.flush()
        db.session.add_all(
            [
                Inscricao(
                    aluno_id=aluno_associado.id,
                    turma_id=turma_associada.id,
                    ativo=True,
                ),
                Inscricao(
                    aluno_id=aluno_de_outra_turma.id,
                    turma_id=turma_nao_associada.id,
                    ativo=True,
                ),
            ]
        )
        db.session.commit()

        professor_id = professor.id
        turma_associada_id = turma_associada.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(professor_id)
        session["_fresh"] = True

    pauta_frequencia = client.get(
        f"/frequencia?turma_id={turma_associada_id}"
    )
    assert pauta_frequencia.status_code == 200
    assert "Aluno da Turma A" in pauta_frequencia.get_data(as_text=True)
    assert "Aluno da Turma B" not in pauta_frequencia.get_data(as_text=True)

    pauta_impressa = client.get(
        f"/turma/{turma_associada_id}/imprimir-pauta"
    )
    assert pauta_impressa.status_code == 200
    assert "Aluno da Turma A" in pauta_impressa.get_data(as_text=True)
    assert "Aluno da Turma B" not in pauta_impressa.get_data(as_text=True)

    with app.app_context():
        db.drop_all()


def test_professor_nao_acessa_pauta_de_turma_de_outro_professor():
    app = create_app(SQLiteTestConfig)
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="Unidade da pauta", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        professor = User(
            name="Professor",
            email="pauta.nao.autorizada@example.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        outro_professor = User(
            name="Outro Professor",
            email="outro.professor@example.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        curso = Curso(nome="Natação", unidade_id=unidade.id, ativo=True)
        db.session.add_all([professor, outro_professor, curso])
        db.session.flush()

        turma = Turma(
            nome="Natação - Turma de Outro Professor",
            unidade_id=unidade.id,
            curso_id=curso.id,
            professor_id=outro_professor.id,
            ativo=True,
        )
        aluno = Aluno(
            nome="Aluno não autorizado",
            nome_social="Aluno",
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add_all([turma, aluno])
        db.session.flush()
        db.session.add(
            Inscricao(aluno_id=aluno.id, turma_id=turma.id, ativo=True)
        )
        db.session.commit()

        professor_id = professor.id
        turma_id = turma.id

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(professor_id)
        session["_fresh"] = True

    detalhe = client.get(f"/turma/{turma_id}")
    impressao = client.get(f"/turma/{turma_id}/imprimir-pauta")
    frequencia = client.get(f"/frequencia?turma_id={turma_id}")

    assert detalhe.status_code == 403
    assert impressao.status_code == 403
    assert frequencia.status_code in (302, 403)

    with app.app_context():
        db.drop_all()
