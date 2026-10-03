"""Testes automatizados para os novos indicadores e indicadores cruzados do BI."""

from datetime import date, datetime, time, timedelta

import pytest
from app import create_app, db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    PerfilDiversidade,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.relatorios.bi import executar_indicador
from app.services.aluno_status import status_alunos_para_bi
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    app = create_app(SQLiteTestConfig)
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    with app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield app
        db.drop_all()


def test_indicadores_sociais_e_operacionais(app):
    """Valida a execução dos indicadores SOC-001, SOC-002, DIV-001 e ATD-001."""
    with app.app_context():
        # SOC-001: Alunos por faixa de renda familiar (retorna lista de faixas)
        res_soc1 = executar_indicador("SOC-001")
        assert isinstance(res_soc1, list)
        assert len(res_soc1) > 0

        # SOC-002: Alunos beneficiários de programas sociais (retorna inteiro)
        res_soc2 = executar_indicador("SOC-002")
        assert isinstance(res_soc2, int)

        # DIV-001: Alunos por tipo de deficiência (retorna lista)
        res_div1 = executar_indicador("DIV-001")
        assert isinstance(res_div1, list)

        # ATD-001: Total de atendimentos (retorna inteiro)
        res_atd1 = executar_indicador("ATD-001")
        assert isinstance(res_atd1, int)


def test_indicadores_cruzados(app):
    """Valida a execução dos indicadores cruzados CRU-001 a CRU-005."""
    codes = ["CRU-001", "CRU-002", "CRU-003", "CRU-004", "CRU-005"]
    
    with app.app_context():
        for code in codes:
            resultado = executar_indicador(code)
            assert isinstance(resultado, list), f"Indicador {code} deve retornar uma lista."


def test_indicadores_de_status_e_filtros_globais(app):
    with app.app_context():
        hoje = date.today()
        unidades = [Unidade(nome="Unidade A"), Unidade(nome="Unidade B")]
        db.session.add_all(unidades)
        db.session.flush()

        def criar_periodo(unidade, nome, inicio, fim):
            periodo = PeriodoLetivo(
                nome=nome,
                data_inicio=inicio,
                data_fim=fim,
                unidade_id=unidade.id,
                ativo=True,
            )
            db.session.add(periodo)
            db.session.flush()
            turma = Turma(
                nome=f"Turma {nome}",
                unidade_id=unidade.id,
                periodo_letivo_id=periodo.id,
                turno="Manhã",
            )
            db.session.add(turma)
            db.session.flush()
            return periodo, turma

        anterior_a, turma_anterior_a = criar_periodo(
            unidades[0], "A anterior", hoje - timedelta(days=400), hoje - timedelta(days=31)
        )
        atual_a, turma_atual_a = criar_periodo(
            unidades[0], "A vigente", hoje - timedelta(days=7), hoje + timedelta(days=90)
        )
        anterior_b, turma_anterior_b = criar_periodo(
            unidades[1], "B anterior", hoje - timedelta(days=400), hoje - timedelta(days=31)
        )
        atual_b, turma_atual_b = criar_periodo(
            unidades[1], "B vigente", hoje - timedelta(days=30), hoje + timedelta(days=90)
        )
        cursos = [
            Curso(nome="Curso A", unidade_id=unidades[0].id),
            Curso(nome="Curso B", unidade_id=unidades[1].id),
        ]
        db.session.add_all(cursos)
        db.session.flush()
        turma_anterior_a.curso_id = cursos[0].id
        turma_atual_a.curso_id = cursos[0].id
        turma_anterior_b.curso_id = cursos[1].id
        turma_atual_b.curso_id = cursos[1].id

        def aluno(unidade, nome, ativo=True):
            registro = Aluno(nome=nome, unidade_id=unidade.id, ativo=ativo)
            db.session.add(registro)
            db.session.flush()
            return registro

        def inscricao(registro, turma, inicio, ativo=True):
            db.session.add(Inscricao(
                aluno_id=registro.id,
                turma_id=turma.id,
                data_inicio=inicio,
                ativo=ativo,
            ))

        novo = aluno(unidades[0], "Novo")
        renovado = aluno(unidades[0], "Renovado")
        em_janela = aluno(unidades[0], "Em janela")
        desenturmado = aluno(unidades[0], "Desenturmado")
        outros = aluno(unidades[0], "Outros")
        inativo_cadastro = aluno(unidades[0], "Inativo no cadastro", ativo=False)
        retornante = aluno(unidades[1], "Retornante")
        nao_renovado = aluno(unidades[1], "Não renovado")
        novo.data_nascimento = date(2015, 1, 1)
        renovado.data_nascimento = date(2010, 1, 1)
        retornante.data_nascimento = date(1990, 1, 1)
        db.session.add_all([
            PerfilDiversidade(
                aluno_id=novo.id,
                unidade_id=unidades[0].id,
                saude_laudo=True,
            ),
            PerfilDiversidade(
                aluno_id=outros.id,
                unidade_id=unidades[0].id,
                saude_laudo=True,
            ),
        ])

        inscricao(novo, turma_atual_a, hoje - timedelta(days=2))
        inscricao(renovado, turma_anterior_a, anterior_a.data_inicio, ativo=False)
        inscricao(renovado, turma_atual_a, atual_a.data_inicio + timedelta(days=3))
        inscricao(em_janela, turma_anterior_a, anterior_a.data_inicio, ativo=False)
        inscricao(desenturmado, turma_atual_a, atual_a.data_inicio, ativo=False)
        inscricao(retornante, turma_anterior_b, anterior_b.data_inicio, ativo=False)
        inscricao(retornante, turma_atual_b, atual_b.data_inicio + timedelta(days=20))
        inscricao(nao_renovado, turma_anterior_b, anterior_b.data_inicio, ativo=False)
        db.session.commit()

        codigos = {
            "ALU-011": 3,
            "ALU-012": 4,
            "ALU-013": 1,
            "ALU-014": 1,
            "ALU-015": 1,
            "ALU-016": 1,
            "ALU-017": 1,
            "ALU-018": 1,
        }
        for codigo, esperado in codigos.items():
            assert executar_indicador(codigo) == esperado

        cursos_enturmados = executar_indicador("ALU-009")
        assert {row["nome"]: row["valor"] for row in cursos_enturmados} == {
            "Curso A": 2,
            "Curso B": 1,
        }
        assert executar_indicador("ALU-009", turno="Manhã") == cursos_enturmados
        assert executar_indicador(
            "ALU-009",
            unidade_id=unidades[0].id,
            periodo_letivo_id=atual_a.id,
        ) == [{"id": cursos[0].id, "nome": "Curso A", "valor": 2}]
        turmas_enturmadas = executar_indicador("ALU-010")
        assert {row["nome"]: row["valor"] for row in turmas_enturmadas} == {
            "Turma A vigente": 2,
            "Turma B vigente": 1,
        }
        assert executar_indicador("ALU-010", turno="Manhã") == turmas_enturmadas
        assert executar_indicador(
            "ALU-010",
            unidade_id=unidades[0].id,
            periodo_letivo_id=atual_a.id,
        ) == [{"id": turma_atual_a.id, "nome": "Turma A vigente", "valor": 2}]

        assert sum(row["valor"] for row in executar_indicador("ALU-005")) == 3
        assert executar_indicador("ALU-007") == 1
        assert executar_indicador("ALU-007", turno="Manhã") == 1
        assert sum(
            row["valor"]
            for row in executar_indicador("ALU-005", turno="Manhã")
        ) == 3
        faixas_etarias = executar_indicador("ALU-006")
        assert sum(row["valor"] for row in faixas_etarias) == 3
        assert {row["nome"]: row["valor"] for row in faixas_etarias} == {
            "Menor de 12 anos": 1,
            "12 a 17 anos": 1,
            "25 a 39 anos": 1,
        }
        assert sum(
            row["valor"] for row in executar_indicador("ALU-006", turno="Manhã")
        ) == 3
        assert executar_indicador("ALU-012", turno="Manhã") == 3
        assert executar_indicador("ALU-001") == 7
        assert executar_indicador("ALU-001") == (
            executar_indicador("ALU-011") + executar_indicador("ALU-012")
        )
        assert executar_indicador("ALU-001", turno="Manhã") == 6
        assert executar_indicador("ALU-001", turno="Manhã") == (
            executar_indicador("ALU-011", turno="Manhã")
            + executar_indicador("ALU-012", turno="Manhã")
        )
        assert executar_indicador(
            "ALU-001",
            unidade_id=unidades[0].id,
            periodo_letivo_id=atual_a.id,
        ) == 5
        assert inativo_cadastro.id not in status_alunos_para_bi(
            periodo_letivo_id=atual_a.id,
            unidade_id=unidades[0].id,
        )
        assert executar_indicador(
            "ALU-011",
            unidade_id=unidades[0].id,
            periodo_letivo_id=atual_a.id,
        ) == 2


def test_indicadores_de_status_isolam_unidade_do_usuario_na_rota(app):
    with app.app_context():
        hoje = date.today()
        unidades = [Unidade(nome="Permitida"), Unidade(nome="Restrita")]
        db.session.add_all(unidades)
        db.session.flush()
        periodos = []
        for unidade in unidades:
            periodo = PeriodoLetivo(
                nome="Vigente",
                data_inicio=hoje - timedelta(days=1),
                data_fim=hoje + timedelta(days=30),
                unidade_id=unidade.id,
                ativo=True,
            )
            db.session.add(periodo)
            db.session.flush()
            turma = Turma(
                nome="Turma vigente",
                unidade_id=unidade.id,
                periodo_letivo_id=periodo.id,
                turno="Manhã",
            )
            db.session.add(turma)
            db.session.flush()
            estudante = Aluno(nome="Aluno", unidade_id=unidade.id, ativo=True)
            db.session.add(estudante)
            db.session.flush()
            db.session.add(Inscricao(
                aluno_id=estudante.id,
                turma_id=turma.id,
                data_inicio=hoje,
                ativo=True,
            ))
            periodos.append(periodo)

        usuario = User(
            name="Pedagógico",
            email="pedagogico@example.com",
            role="pedagogico",
            unidade_id=unidades[0].id,
            first_login=False,
        )
        usuario.set_password("Teste123!")
        db.session.add(usuario)
        db.session.commit()
        usuario_id = usuario.id
        unidade_restrita_id = unidades[1].id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(usuario_id)
        sess["_fresh"] = True

    resposta_propria = client.get("/relatorios/bi/indicador/ALU-011")
    assert resposta_propria.status_code == 200
    assert resposta_propria.get_json()["resultado"] == 1
    resposta_sexo = client.get("/relatorios/bi/indicador/ALU-005")
    assert resposta_sexo.status_code == 200
    assert sum(row["valor"] for row in resposta_sexo.get_json()["resultado"]) == 1
    resposta_idade = client.get("/relatorios/bi/indicador/ALU-006")
    assert resposta_idade.status_code == 200
    assert sum(row["valor"] for row in resposta_idade.get_json()["resultado"]) == 1
    resposta_pcd = client.get("/relatorios/bi/indicador/ALU-007")
    assert resposta_pcd.status_code == 200
    resposta_curso = client.get("/relatorios/bi/indicador/ALU-009")
    assert resposta_curso.status_code == 200
    resposta_turma = client.get("/relatorios/bi/indicador/ALU-010")
    assert resposta_turma.status_code == 200

    resposta_outra = client.get(
        f"/relatorios/bi/indicador/ALU-011?unidade_id={unidade_restrita_id}"
    )
    assert resposta_outra.status_code == 403
    resposta_sexo_outra = client.get(
        f"/relatorios/bi/indicador/ALU-005?unidade_id={unidade_restrita_id}"
    )
    assert resposta_sexo_outra.status_code == 403
    resposta_idade_outra = client.get(
        f"/relatorios/bi/indicador/ALU-006?unidade_id={unidade_restrita_id}"
    )
    assert resposta_idade_outra.status_code == 403
    resposta_pcd_outra = client.get(
        f"/relatorios/bi/indicador/ALU-007?unidade_id={unidade_restrita_id}"
    )
    assert resposta_pcd_outra.status_code == 403
    resposta_curso_outra = client.get(
        f"/relatorios/bi/indicador/ALU-009?unidade_id={unidade_restrita_id}"
    )
    assert resposta_curso_outra.status_code == 403
    resposta_turma_outra = client.get(
        f"/relatorios/bi/indicador/ALU-010?unidade_id={unidade_restrita_id}"
    )
    assert resposta_turma_outra.status_code == 403


def test_alu004_conta_cadastros_no_intervalo_sem_exigir_enturmacao(app):
    with app.app_context():
        hoje = date.today()
        unidade = Unidade(nome="Unidade ALU-004")
        db.session.add(unidade)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="Período atual",
            data_inicio=hoje - timedelta(days=10),
            data_fim=hoje + timedelta(days=30),
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        dentro = Aluno(
            nome="Cadastro no período",
            unidade_id=unidade.id,
            ativo=True,
            created_at=datetime.combine(hoje, time(hour=12)),
        )
        fora = Aluno(
            nome="Cadastro anterior",
            unidade_id=unidade.id,
            ativo=True,
            created_at=datetime.combine(periodo.data_inicio - timedelta(days=1), time.min),
        )
        sem_data = Aluno(nome="Cadastro sem data", unidade_id=unidade.id, ativo=True)
        db.session.add_all([dentro, fora, sem_data])
        db.session.flush()
        sem_data.created_at = None
        db.session.commit()

        assert executar_indicador(
            "ALU-004",
            unidade_id=unidade.id,
            periodo_letivo_id=periodo.id,
        ) == 1
        assert executar_indicador("ALU-004", unidade_id=unidade.id) == 1
        assert executar_indicador(
            "ALU-013",
            unidade_id=unidade.id,
            periodo_letivo_id=periodo.id,
        ) == 0
        assert Aluno.query.filter(Aluno.created_at.is_(None)).count() == 1