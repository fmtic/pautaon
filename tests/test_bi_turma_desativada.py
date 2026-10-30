"""Etapa J2 — 'Enturmado em oferta' e turma desativada nas contagens do BI.

Cenário central: turma ativa com 2 alunos + turma desativada com 1 aluno
(inscrição inativa, motivo TURMA_DESATIVADA, frequência preservada). As
contagens agregadas do BI não podem inflar com a turma desativada.
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app import create_app, db
from _helpers import professor_semente
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
)
from app.models.enums import StatusAluno
from app.relatorios.bi_alunos import (
    alunos_por_curso,
    alunos_por_turma,
    alunos_por_unidade,
    frequencia_por_turma,
    inscricoes_desativadas,
    inscricoes_encerradas,
    media_alunos_por_turma,
    total_inscricoes,
    total_turmas,
    turmas_ativas,
    turmas_por_unidade,
)
from app.relatorios.bi_filtros import cond_inscricao_enturmada
from app.services.aluno_status import status_alunos
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    app = create_app(SQLiteTestConfig)
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield app
        db.drop_all()


def _valor_por_nome(resultado):
    return {linha["nome"]: linha["valor"] for linha in resultado}


def _count_inscricoes_enturmadas(turma_id):
    """Quantas inscrições da turma satisfazem o helper 'enturmado em oferta'."""
    return db.session.execute(
        select(func.count(Inscricao.id))
        .where(Inscricao.turma_id == turma_id, cond_inscricao_enturmada())
    ).scalar_one()


@pytest.fixture
def cenario(app):
    """Turma ativa (2 alunos + extras) e turma desativada (1 aluno).

    a1, a2: inscrição ativa apontando para a oferta ativa de turma1.
    a4:     inscrição ativa apontando para a (única) oferta de turma1 -> conta.
    a5:     única inscrição, inativa, na turma desativada (TURMA_DESATIVADA).
    a6:     duas inscrições ativas em duas ofertas da mesma turma -> 1 aluno
          (distinct) mas 2 linhas (media/total).

    A inscrição a3, que exercitava a exclusão do estado legado
    `turma_curso_id NULL` em turma com 2+ ofertas, foi removida: o NOT NULL de
    Inscricao.turma_curso_id (migration c3d4e5f6a7b8) tornou esse estado
    impossível e o ramo NULL de `cond_inscricao_enturmada` virou código morto.

    Retorna IDs (inteiros) para evitar DetachedInstanceError entre contexts.
    """
    hoje = date.today()
    unidade = Unidade(nome="Unidade J2", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    periodo = PeriodoLetivo(
        nome="P J2",
        data_inicio=hoje - timedelta(days=7),
        data_fim=hoje + timedelta(days=90),
        unidade_id=unidade.id,
        ativo=True,
    )
    curso_x = Curso(nome="Curso X", unidade_id=unidade.id)
    curso_y = Curso(nome="Curso Y", unidade_id=unidade.id)
    curso_z = Curso(nome="Curso Z", unidade_id=unidade.id)
    db.session.add_all([periodo, curso_x, curso_y, curso_z])
    db.session.flush()

    turma1 = Turma(
        nome="Turma Ativa 1", ativo=True, unidade_id=unidade.id,
        periodo_letivo_id=periodo.id, curso_id=curso_x.id, turno="Manhã",
    )
    turma2 = Turma(
        nome="Turma Ativa 2", ativo=True, unidade_id=unidade.id,
        periodo_letivo_id=periodo.id, curso_id=curso_x.id, turno="Tarde",
    )
    turma3 = Turma(
        nome="Turma Desativada", ativo=False, unidade_id=unidade.id,
        periodo_letivo_id=periodo.id, curso_id=curso_y.id, turno="Manhã",
    )
    db.session.add_all([turma1, turma2, turma3])
    db.session.flush()

    # Ofertas (TurmaCurso): turma1 e turma3 com 1 oferta; turma2 com 2.
    o1 = TurmaCurso(turma_id=turma1.id, curso_id=curso_x.id,
                    unidade_id=unidade.id, ativo=True, principal=True, programa="Teste",
                    professor_id=professor_semente(unidade.id).id)
    o2 = TurmaCurso(turma_id=turma2.id, curso_id=curso_x.id,
                    unidade_id=unidade.id, ativo=True, principal=True, programa="Teste",
                    professor_id=professor_semente(unidade.id).id)
    o3 = TurmaCurso(turma_id=turma2.id, curso_id=curso_y.id,
                    unidade_id=unidade.id, ativo=True, principal=False, programa="Teste",
                    professor_id=professor_semente(unidade.id).id)
    o4 = TurmaCurso(turma_id=turma3.id, curso_id=curso_y.id,
                    unidade_id=unidade.id, ativo=True, principal=True, programa="Teste",
                    professor_id=professor_semente(unidade.id).id)
    # Segunda oferta ativa de turma1 (curso distinto): permite ao aluno a6 ter
    # duas inscrições ativas sem violar uix_inscricao_ativa_aluno_oferta
    # (índice parcial por (aluno_id, turma_curso_id)). Serve para provar que
    # o helper conta LINHAS (media/total) enquanto as métricas distinct contam 1.
    o1b = TurmaCurso(turma_id=turma1.id, curso_id=curso_z.id,
                     unidade_id=unidade.id, ativo=True, principal=False, programa="Teste",
                     professor_id=professor_semente(unidade.id).id)
    db.session.add_all([o1, o2, o3, o4, o1b])
    db.session.flush()

    alunos = [
        Aluno(nome=f"Aluno {i}", unidade_id=unidade.id, ativo=True)
        for i in range(1, 6)
    ]
    db.session.add_all(alunos)
    db.session.flush()
    a1, a2, a4, a5, a6 = alunos

    def inscricao(aluno, turma, oferta=None, ativo=True, motivo=None):
        registro = Inscricao(
            aluno_id=aluno.id,
            turma_id=turma.id,
            turma_curso_id=oferta.id if oferta else None,
            data_inicio=hoje - timedelta(days=2),
            ativo=ativo,
        )
        if not ativo:
            registro.data_desativacao = datetime.now()
            registro.motivo_desativacao = motivo
        db.session.add(registro)

    inscricao(a1, turma1, o1)
    inscricao(a2, turma1, o1)
    inscricao(a4, turma1, o1)
    inscricao(a5, turma3, o4, ativo=False, motivo="TURMA_DESATIVADA")
    inscricao(a6, turma1, o1)
    inscricao(a6, turma1, o1b)

    # Frequência preservada também na turma desativada (legado).
    db.session.add_all([
        Frequencia(aluno_id=a1.id, turma_id=turma1.id, data=hoje,
                   conceito="A", unidade_id=unidade.id),
        Frequencia(aluno_id=a2.id, turma_id=turma1.id, data=hoje,
                   conceito="A", unidade_id=unidade.id),
        Frequencia(aluno_id=a5.id, turma_id=turma3.id, data=hoje,
                   conceito="A", unidade_id=unidade.id),
    ])
    db.session.commit()

    return {
        "unidade_id": unidade.id,
        "periodo_id": periodo.id,
        "turma1_id": turma1.id,
        "turma2_id": turma2.id,
        "turma3_id": turma3.id,
        "a1_id": a1.id,
        "a5_id": a5.id,
    }


def test_helper_oferta_apontada_e_turma_desativada(cenario):
    """Prova direta do helper: inscrição ativa com oferta ativa conta; turma
    desativada não conta; a6 (2 inscrições) é contado pelas 2 linhas."""
    # turma1: a1, a2, a4 e a6 (2 linhas) => 5 inscrições enturmadas.
    assert _count_inscricoes_enturmadas(cenario["turma1_id"]) == 5
    # turma2: sem inscrições enturmadas => nenhuma conta.
    assert _count_inscricoes_enturmadas(cenario["turma2_id"]) == 0
    # turma3: desativada; inscrição inativa => nenhuma conta.
    assert _count_inscricoes_enturmadas(cenario["turma3_id"]) == 0


def test_total_turmas_exclui_desativada_e_coincide_com_turmas_ativas(cenario):
    # Só Turma.ativo importa para contadores de turmas (sem exigir oferta).
    assert total_turmas() == 2
    # Item 5: total_turmas passa a coincidir com turmas_ativas.
    assert total_turmas() == turmas_ativas()
    assert _valor_por_nome(turmas_por_unidade()) == {"Unidade J2": 2}


def test_media_alunos_por_turma_usa_helper(cenario):
    # Numerador (inscrições enturmadas): turma1=5 (a1,a2,a4,a6x2), turma2=0;
    # denominador = 2 turmas ativas. 5 / 2 = 2,5.
    assert media_alunos_por_turma() == pytest.approx(2.5)


def test_alunos_por_unidade_conta_cada_aluno_uma_vez(cenario):
    # count(distinct Aluno): a1, a2, a4, a6 (uma vez) = 4; sem a3 e sem a5.
    valores = _valor_por_nome(alunos_por_unidade(periodo_letivo_id=cenario["periodo_id"]))
    assert valores["Unidade J2"] == 4


def test_inscricoes_desativadas_e_encerradas_excluem_turma_desativada(cenario):
    # A única inscrição inativa é a da turma desativada: não entra.
    assert inscricoes_desativadas() == 0
    assert inscricoes_encerradas() == 0
    # As 5 ativas das turmas ativas continuam contando (a6 tem 2 linhas).
    assert total_inscricoes() == 5


def test_frequencia_por_turma_nao_lista_turma_desativada(cenario):
    resultados = frequencia_por_turma()
    nomes = {linha["nome"] for linha in resultados}
    assert "Turma Desativada" not in nomes
    assert nomes == {"Turma Ativa 1", "Turma Ativa 2"}
    assert _valor_por_nome(resultados)["Turma Ativa 1"] == 100.0


def test_alunos_por_turma_e_por_curso_excluem_turma_desativada(cenario):
    # Etapa J3: alunos_por_curso/turma usam o helper estrito (enturmado em
    # oferta ativa): a1, a2, a4 e a6 (uma vez) contam; a3 (NULL + 2 ofertas)
    # e a5 (turma desativada) ficam fora.
    por_turma = _valor_por_nome(alunos_por_turma())
    assert "Turma Desativada" not in por_turma
    assert por_turma["Turma Ativa 1"] == 4  # a1, a2, a4, a6 (uma vez)
    assert "Turma Ativa 2" not in por_turma  # sem inscrições enturmadas
    # Curso Y só tinha enturmados na turma desativada: não aparece.
    assert "Curso Y" not in _valor_por_nome(alunos_por_curso())
    # Curso X: a1, a2, a4, a6 (uma vez); a3 não contribui.
    assert _valor_por_nome(alunos_por_curso())["Curso X"] == 4


def test_status_nao_infla_desenturmado_com_turma_desativada(cenario):
    """Item 1: inscrição desativada por TURMA_DESATIVADA não vira DESENTURMADO."""
    status = status_alunos(periodo_id=cenario["periodo_id"])
    a1_id, a5_id = cenario["a1_id"], cenario["a5_id"]
    # Sem o ajuste, a5 caía em DESENTURMADO (inscrição inativa na turma do
    # período); agora a turma desativada é ignorada e a5 vira OUTROS.
    assert status.get(a5_id) == StatusAluno.OUTROS
    assert status[a1_id] == StatusAluno.NOVO


def test_regressao_sem_turma_desativada(app):
    """Sem turma desativada, contagem de turmas/inscrições não muda (1 cada)."""
    hoje = date.today()
    unidade = Unidade(nome="Unidade Só Ativas", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    periodo = PeriodoLetivo(
        nome="P", data_inicio=hoje - timedelta(days=5),
        data_fim=hoje + timedelta(days=60), unidade_id=unidade.id, ativo=True,
    )
    db.session.add(periodo)
    db.session.flush()
    turma = Turma(nome="Única", ativo=True, unidade_id=unidade.id,
                  periodo_letivo_id=periodo.id)
    db.session.add(turma)
    curso = Curso(nome="Curso Única", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    oferta = TurmaCurso(
        turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
        ativo=True, principal=True, programa="Teste",
        professor_id=professor_semente(unidade.id).id,
    )
    db.session.add(oferta)
    aluno = Aluno(nome="A", unidade_id=unidade.id, ativo=True)
    db.session.add(aluno)
    db.session.flush()
    db.session.add(Inscricao(
        aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id,
        data_inicio=hoje - timedelta(days=2), ativo=True,
    ))
    db.session.commit()

    assert total_turmas() == 1
    assert total_turmas() == turmas_ativas()
    assert total_inscricoes() == 1
    assert inscricoes_desativadas() == 0
