"""AJ34 — ajuda contextual, aviso de filtro, TUR-004 e INS-009."""

import io
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from app import create_app, db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import StatusAluno
from app.relatorios.bi import INDICADORES_ALUNOS, executar_indicador
from app.relatorios.bi_alunos import (
    alunos_por_turma,
    inscricoes_iniciadas_no_periodo,
    media_alunos_por_turma,
    total_inscricoes,
)
from app.relatorios.bi_filtros import cond_inscricao_enturmada
from app.relatorios.bi_routes import _metadados_ajuda_central
from app.relatorios.catalogo import (
    ALIASES,
    FILTROS_PARCIAIS,
    INDICADORES,
    GUIA_METADADOS,
    TEXTO_FILTRO_NAO_APLICADO,
    VERSAO_CATALOGO,
    indicadores_para_guia,
    resolver_codigo,
    validar_catalogo_guia,
)
from config import Config
from _helpers import login_as

RAIZ = Path(__file__).resolve().parents[1]
PADRAO_TAREFA = re.compile(r"\bAJ\s*\d+[A-Za-z]?\b", re.IGNORECASE)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-aj34-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    aplicativo = create_app(SQLiteTestConfig)
    aplicativo.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with aplicativo.app_context():
        db.create_all()
        yield aplicativo
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _usuario(unidade, role, email):
    usuario = User(
        name=f"Usuário {role} AJ34",
        email=email,
        role=role,
        unidade_id=unidade.id,
        is_active=True,
        first_login=False,
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture
def cenario(app):
    """Base com duas unidades, turnos, cursos e datas de inscrição distintas."""
    hoje = date.today()
    u_a = Unidade(nome="Unidade AJ34 A", ativo=True)
    u_b = Unidade(nome="Unidade AJ34 B", ativo=True)
    db.session.add_all([u_a, u_b])
    db.session.flush()

    atual_a = PeriodoLetivo(
        nome="AJ34 atual A", data_inicio=hoje - timedelta(days=10),
        data_fim=hoje + timedelta(days=30), unidade_id=u_a.id, ativo=True,
    )
    atual_b = PeriodoLetivo(
        nome="AJ34 atual B", data_inicio=hoje - timedelta(days=9),
        data_fim=hoje + timedelta(days=29), unidade_id=u_b.id, ativo=True,
    )
    antigo_a = PeriodoLetivo(
        nome="AJ34 antigo A", data_inicio=hoje - timedelta(days=300),
        data_fim=hoje - timedelta(days=100), unidade_id=u_a.id, ativo=True,
    )
    db.session.add_all([atual_a, atual_b, antigo_a])
    db.session.flush()

    curso_a1 = Curso(nome="AJ34 A1", unidade_id=u_a.id, ativo=True)
    curso_a2 = Curso(nome="AJ34 A2", unidade_id=u_a.id, ativo=True)
    curso_b1 = Curso(nome="AJ34 B1", unidade_id=u_b.id, ativo=True)
    db.session.add_all([curso_a1, curso_a2, curso_b1])
    db.session.flush()

    turmas = [
        Turma(nome="AJ34 A1", unidade_id=u_a.id, periodo_letivo_id=atual_a.id,
              ativo=True, turno="Manhã"),
        Turma(nome="AJ34 A2", unidade_id=u_a.id, periodo_letivo_id=atual_a.id,
              ativo=True, turno="Tarde"),
        Turma(nome="AJ34 antiga", unidade_id=u_a.id, periodo_letivo_id=antigo_a.id,
              ativo=True, turno="Manhã"),
        Turma(nome="AJ34 desativada", unidade_id=u_a.id,
              periodo_letivo_id=atual_a.id, ativo=False, turno="Manhã"),
        Turma(nome="AJ34 B", unidade_id=u_b.id, periodo_letivo_id=atual_b.id,
              ativo=True, turno="Noite"),
    ]
    db.session.add_all(turmas)
    db.session.flush()

    p1 = User(name="Prof AJ34 um", email="prof.aj34.um@example.test", role="professor",
              unidade_id=u_a.id, is_active=True, first_login=False)
    p2 = User(name="Prof AJ34 dois", email="prof.aj34.dois@example.test", role="professor",
              unidade_id=u_b.id, is_active=True, first_login=False)
    db.session.add_all([p1, p2])
    db.session.flush()

    ofertas = [
        TurmaCurso(turma_id=turmas[0].id, curso_id=curso_a1.id,
                   professor_id=p1.id, unidade_id=u_a.id, turno="Manhã",
                   ativo=True, principal=True, programa="AJ34"),
        TurmaCurso(turma_id=turmas[0].id, curso_id=curso_a2.id,
                   professor_id=p1.id, unidade_id=u_a.id, turno="Tarde",
                   ativo=True, principal=False, programa="AJ34"),
        TurmaCurso(turma_id=turmas[1].id, curso_id=curso_a1.id,
                   professor_id=p2.id, unidade_id=u_a.id, turno="Tarde",
                   ativo=True, principal=True, programa="AJ34"),
        TurmaCurso(turma_id=turmas[2].id, curso_id=curso_a1.id,
                   professor_id=p1.id, unidade_id=u_a.id, turno="Manhã",
                   ativo=True, principal=True, programa="AJ34"),
        TurmaCurso(turma_id=turmas[3].id, curso_id=curso_a1.id,
                   professor_id=p1.id, unidade_id=u_a.id, turno="Manhã",
                   ativo=True, principal=True, programa="AJ34"),
        TurmaCurso(turma_id=turmas[4].id, curso_id=curso_b1.id,
                   professor_id=p2.id, unidade_id=u_b.id, turno="Noite",
                   ativo=True, principal=True, programa="AJ34"),
    ]
    db.session.add_all(ofertas)
    db.session.flush()

    alunos = []
    for indice in range(1, 9):
        aluno = Aluno(
            nome=f"Aluno AJ34 {indice}",
            unidade_id=u_a.id if indice < 8 else u_b.id,
            ativo=True,
            created_at=hoje - timedelta(days=indice),
        )
        db.session.add(aluno)
        db.session.flush()
        alunos.append(aluno)

    # (aluno, oferta, data_inicio, data_entrada_oferta, ativo)
    lancamentos = [
        (alunos[0], ofertas[0], atual_a.data_inicio, None, True),
        (alunos[1], ofertas[1], atual_a.data_fim, atual_a.data_fim, False),
        (alunos[2], ofertas[0], atual_a.data_inicio - timedelta(days=1), None, True),
        (alunos[3], ofertas[2], atual_a.data_fim + timedelta(days=1), None, True),
        (alunos[4], ofertas[3], antigo_a.data_inicio + timedelta(days=1), None, True),
        (alunos[5], ofertas[4], atual_a.data_inicio + timedelta(days=1), None, True),
        (alunos[6], ofertas[5], atual_b.data_inicio, None, True),
        (alunos[7], ofertas[0], atual_a.data_inicio + timedelta(days=2),
         hoje + timedelta(days=90), True),
    ]
    for aluno, oferta, inicio, entrada, ativo in lancamentos:
        db.session.add(Inscricao(
            aluno_id=aluno.id,
            turma_id=oferta.turma_id,
            turma_curso_id=oferta.id,
            data_inicio=inicio,
            data_entrada_oferta=entrada,
            ativo=ativo,
        ))
    db.session.commit()

    return {
        "hoje": hoje,
        "unidade_a": u_a.id,
        "unidade_b": u_b.id,
        "periodo_atual_a": atual_a.id,
        "periodo_antigo_a": antigo_a.id,
        "turma_a1": turmas[0].id,
        "curso_a2": curso_a2.id,
        "professor_p1": p1.id,
    }


def test_catalogo_aj34_versao_e_texto_sem_codigo_de_tarefa(app):
    with app.app_context():
        assert validar_catalogo_guia() is True
        assert VERSAO_CATALOGO == "1.2"
        assert len(INDICADORES) == 62
        assert INDICADORES["INS-009"]["tipo"] == "contagem"
        assert INDICADORES["INS-009"]["unidade"] == "inscrições"
        assert resolver_codigo("INS-004") == "INS-001"
        assert "INS-009" not in ALIASES
        assert "alunos distintos" in INDICADORES["TUR-004"]["nome"].lower()

        for item in indicadores_para_guia():
            texto = " ".join([
                item["nome"], item["mede"], item["regra"], *item["observacoes"],
            ])
            assert PADRAO_TAREFA.search(texto) is None


def test_inscricoes_iniciadas_no_periodo_bordas_e_escopo(app, cenario):
    with app.app_context():
        # Sem período: vigente de cada unidade. boundary inicial/final contam;
        # foras, período antigo e turma desativada ficam de fora.
        assert inscricoes_iniciadas_no_periodo() == 4
        assert inscricoes_iniciadas_no_periodo(unidade_id=cenario["unidade_a"]) == 3
        assert inscricoes_iniciadas_no_periodo(unidade_id=cenario["unidade_b"]) == 1
        assert inscricoes_iniciadas_no_periodo(
            periodo_letivo_id=cenario["periodo_atual_a"]
        ) == 3
        assert inscricoes_iniciadas_no_periodo(
            periodo_letivo_id=cenario["periodo_antigo_a"]
        ) == 1

        # Curso e professor pela OFERTA, não pelo campo legado da turma.
        assert inscricoes_iniciadas_no_periodo(
            curso_id=cenario["curso_a2"]
        ) == 1
        assert inscricoes_iniciadas_no_periodo(
            professor_id=cenario["professor_p1"]
        ) == 3
        assert inscricoes_iniciadas_no_periodo(
            turma_id=cenario["turma_a1"]
        ) == 3


def test_inscricoes_iniciadas_respeita_turno_e_usa_data_inicio(app, cenario):
    with app.app_context():
        assert inscricoes_iniciadas_no_periodo(turno="Manhã") == 2
        assert inscricoes_iniciadas_no_periodo(turno="Tarde") == 1
        assert inscricoes_iniciadas_no_periodo(turno="Noite") == 1
        assert inscricoes_iniciadas_no_periodo(turno="Outros") == 0

        # A oitava inscrição tem `data_entrada_oferta` no futuro, mas
        # `data_inicio` dentro do período: entra pelo campo correto.
        assert inscricoes_iniciadas_no_periodo(
            unidade_id=cenario["unidade_a"], turno="Manhã"
        ) == 2
        assert executar_indicador("INS-009") == 4


def test_ins009_nao_e_estoque_de_inscricoes_nem_cadastro(app, cenario):
    with app.app_context():
        # INS-001 inclui inscrições fora das bordas e de período anterior.
        assert total_inscricoes() == 7
        assert inscricoes_iniciadas_no_periodo() == 4
        assert INDICADORES["INS-009"]["nome"] != INDICADORES["INS-004"]["nome"]
        observacoes = " ".join(GUIA_METADADOS["INS-009"]["observacoes"])
        for trecho in ("INS-001", "INS-004", "ALU-004", "ALU-013", "data de início"):
            assert trecho in observacoes


def test_tur004_usa_alunos_distintos_e_mantem_denominador(app, cenario):
    with app.app_context():
        por_turma = alunos_por_turma(
            periodo_letivo_id=cenario["periodo_atual_a"],
            unidade_id=cenario["unidade_a"],
        )
        soma = sum(item["valor"] for item in por_turma)
        turmas_ativas = db.session.scalar(
            select(func.count(Turma.id)).where(
                Turma.ativo.is_(True),
                Turma.unidade_id == cenario["unidade_a"],
                Turma.periodo_letivo_id == cenario["periodo_atual_a"],
            )
        )
        atual = media_alunos_por_turma(
            periodo_letivo_id=cenario["periodo_atual_a"],
            unidade_id=cenario["unidade_a"],
        )
        assert turmas_ativas == 2
        assert soma > 0
        assert atual == round(soma / turmas_ativas, 1)

        # Cálculo ANTES da AJ34: linhas de inscrição enturmadas por turma.
        antes = 0
        for turma in db.session.scalars(
            select(Turma).where(
                Turma.ativo.is_(True),
                Turma.unidade_id == cenario["unidade_a"],
                Turma.periodo_letivo_id == cenario["periodo_atual_a"],
            )
        ).all():
            antes += db.session.scalar(
                select(func.count(Inscricao.id)).where(
                    Inscricao.turma_id == turma.id,
                    cond_inscricao_enturmada(),
                )
            )
        assert antes >= soma
        assert antes / turmas_ativas != atual


def test_metadados_da_central_sao_iguais_ao_guia_nos_casos_parciais(app):
    with app.app_context():
        metadados = _metadados_ajuda_central()

        aul = metadados["AUL-006"]
        periodo = next(f for f in aul["filtros"] if f["chave"] == "periodo")
        assert periodo["situacao"] == "nao_aplicavel"
        assert periodo["texto"] == FILTROS_PARCIAIS["AUL-006"]["periodo"]
        assert aul["ignorados"]["periodo"] == FILTROS_PARCIAIS["AUL-006"]["periodo"]
        assert aul["ignorados"]["periodo"] in GUIA_METADADOS["AUL-006"]["observacoes"]

        alu = metadados["ALU-009"]
        turno = next(f for f in alu["filtros"] if f["chave"] == "turno")
        assert turno["situacao"] == "parcial"
        assert alu["ignorados"]["turno"] == FILTROS_PARCIAIS["ALU-009"]["turno"]
        assert alu["ignorados"]["turno"] in GUIA_METADADOS["ALU-009"]["observacoes"]

        # Nenhum código oculto da AJ33 é exposto na ajuda da Central.
        texto = repr(metadados)
        for codigo in ("INS-004", "INS-005", "TUR-001", "TUR-003", "INS-006", "INS-007"):
            assert codigo not in texto


def test_central_e_guia_exibem_modais_aviso_e_opcao_de_impressao(app, client, cenario):
    with app.app_context():
        admin_id = _usuario(
            db.session.get(Unidade, cenario["unidade_a"]), "admin",
            "admin.aj34@example.test",
        ).id
    login_as(client, admin_id, cenario["unidade_a"])

    central = client.get("/relatorios/bi").get_data(as_text=True)
    for trecho in (
        "modalComoLerCentral",
        "ajudaCategorias",
        "modalAjudaIndicador",
        "avisoFiltroNaoAplicado",
        "btnAjudaIndicador",
        "Como ler a Central",
        "Imprimir/baixar guia (PDF)",
        "imprimir=1",
        "avisarFiltrosIgnorados",
    ):
        assert trecho in central
    for codigo in ("INS-004", "INS-005", "TUR-001", "TUR-003", "INS-006", "INS-007"):
        assert codigo not in central

    guia = client.get("/relatorios/bi/indicadores").get_data(as_text=True)
    assert "INS-009" in guia
    assert "Inscrições iniciadas no período" in guia
    assert FILTROS_PARCIAIS["AUL-006"]["periodo"] in guia
    assert FILTROS_PARCIAIS["ALU-009"]["turno"] in guia
    # O texto do catálogo é verificado sem códigos de tarefa no teste do guia;
    # aqui apenas confere que os avisos parciais chegaram à página.

    js_guia = (RAIZ / "app/static/js/relatorios/guia_indicadores.js").read_text("utf-8")
    assert 'params.get("imprimir")' in js_guia
    assert "window.print()" in js_guia


def test_api_e_xlsx_preservam_codigo_ins009(app, client, cenario):
    with app.app_context():
        admin_id = _usuario(
            db.session.get(Unidade, cenario["unidade_a"]), "admin",
            "admin.aj34.api@example.test",
        ).id
    login_as(client, admin_id, cenario["unidade_a"])

    resposta = client.get(
        "/relatorios/bi/indicador/INS-009",
        query_string={"unidade_id": cenario["unidade_a"]},
    )
    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["indicador"] == "INS-009"
    assert corpo["resultado"] == 3

    xlsx = client.get(
        "/relatorios/bi/exportar/xlsx",
        query_string={"codigo": "INS-009", "unidade_id": cenario["unidade_a"]},
    )
    assert xlsx.status_code == 200
    plano = load_workbook(io.BytesIO(xlsx.data), data_only=True)
    assert "Código: INS-009" in plano["Resultado"]["A2"].value
