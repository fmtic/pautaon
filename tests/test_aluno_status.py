from datetime import date, datetime

import pytest

from app import create_app, db
from app.models import Aluno, Inscricao, PeriodoLetivo, Turma, Unidade
from app.models.enums import StatusAluno
from app.services.aluno_status import (
    status_aluno,
    status_alunos,
    status_alunos_para_bi,
)
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


def _world():
    unidade = Unidade(nome="NIT")
    db.session.add(unidade)
    db.session.flush()

    periodos = []
    for nome, inicio in (
        ("P-2", date(2025, 1, 1)),
        ("P-1", date(2025, 8, 1)),
        ("P", date(2026, 1, 1)),
    ):
        periodo = PeriodoLetivo(
            nome=nome,
            data_inicio=inicio,
            data_fim=date(inicio.year, 12, 31),
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
        turma = Turma(nome=f"Turma {nome}", unidade_id=unidade.id, periodo_letivo_id=periodo.id)
        db.session.add(turma)
        db.session.flush()
        periodos.append((periodo, turma))

    return unidade, periodos[0], periodos[1], periodos[2]


def test_periodo_nome_exibicao_prefixa_unidade():
    unidade = Unidade(nome="NIT")
    periodo = PeriodoLetivo(nome="2026.2", unidade=unidade)
    assert periodo.nome_exibicao == f"{unidade.nome} {periodo.nome}"
    assert periodo.nome == "2026.2"


def _aluno(unidade, nome, ativo=True):
    aluno = Aluno(nome=nome, unidade_id=unidade.id, ativo=ativo)
    db.session.add(aluno)
    db.session.flush()
    return aluno


def _inscricao(aluno, turma, inicio, ativo=True, desativacao=None):
    inscricao = Inscricao(
        aluno_id=aluno.id,
        turma_id=turma.id,
        data_inicio=inicio,
        ativo=ativo,
        data_desativacao=desativacao,
    )
    db.session.add(inscricao)
    db.session.flush()
    return inscricao


def test_classifica_novo_renovado_retornante_e_limite_inclusivo(app):
    with app.app_context():
        unidade, p2, p1, p = _world()
        novo = _aluno(unidade, "Novo")
        dia_3 = _aluno(unidade, "Renovado dia 3")
        dia_14 = _aluno(unidade, "Renovado dia 14")
        dia_20 = _aluno(unidade, "Retornante dia 20")
        volta_p2 = _aluno(unidade, "Retorno de P-2")

        _inscricao(dia_3, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(dia_3, p[1], date(2026, 1, 4))
        _inscricao(dia_14, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(dia_14, p[1], date(2026, 1, 15))
        _inscricao(dia_20, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(dia_20, p[1], date(2026, 1, 21))
        _inscricao(volta_p2, p2[1], date(2025, 1, 1), ativo=False)
        _inscricao(volta_p2, p[1], date(2026, 1, 3))
        _inscricao(novo, p[1], date(2026, 1, 2))

        resultado = status_alunos(p[0].id, date(2026, 1, 22))

        assert resultado[novo.id] is StatusAluno.NOVO
        assert resultado[dia_3.id] is StatusAluno.RENOVADO
        assert resultado[dia_14.id] is StatusAluno.RENOVADO
        assert resultado[dia_20.id] is StatusAluno.RETORNANTE
        assert resultado[volta_p2.id] is StatusAluno.RETORNANTE


def test_classifica_em_janela_nao_renovado_e_outros(app):
    with app.app_context():
        unidade, _, p1, p = _world()
        em_janela = _aluno(unidade, "Em janela")
        antes_inicio = _aluno(unidade, "Antes do início")
        nao_renovado = _aluno(unidade, "Não renovado")
        outros = _aluno(unidade, "Outros")

        _inscricao(em_janela, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(antes_inicio, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(nao_renovado, p1[1], date(2025, 8, 1), ativo=False)

        resultado_janela = status_alunos(p[0].id, date(2026, 1, 11))
        resultado_antes = status_alunos(p[0].id, date(2025, 12, 20))
        resultado_fechado = status_alunos(p[0].id, date(2026, 1, 21))

        assert resultado_janela[em_janela.id] is StatusAluno.EM_JANELA
        assert resultado_antes[antes_inicio.id] is StatusAluno.EM_JANELA
        assert resultado_fechado[nao_renovado.id] is StatusAluno.NAO_RENOVADO
        assert resultado_fechado[outros.id] is StatusAluno.OUTROS


def test_nao_renovado_que_enturma_depois_vira_retornante(app):
    with app.app_context():
        unidade, _, p1, p = _world()
        aluno = _aluno(unidade, "Voltou depois")
        _inscricao(aluno, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(aluno, p[1], date(2026, 1, 21))

        assert status_aluno(aluno.id, p[0].id, date(2026, 1, 20)) is StatusAluno.NAO_RENOVADO
        assert status_aluno(aluno.id, p[0].id, date(2026, 1, 22)) is StatusAluno.RETORNANTE


def test_desenturmado_transferencia_no_periodo_e_inativo(app):
    with app.app_context():
        unidade, _, p1, p = _world()
        desenturmado = _aluno(unidade, "Desenturmado")
        transferido = _aluno(unidade, "Transferido")
        inativo = _aluno(unidade, "Inativo", ativo=False)

        _inscricao(desenturmado, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(desenturmado, p[1], date(2026, 1, 2), ativo=False,
                   desativacao=datetime(2026, 1, 10, 10, 0))

        outra_turma = Turma(
            nome="Turma P alternativa",
            unidade_id=unidade.id,
            periodo_letivo_id=p[0].id,
        )
        db.session.add(outra_turma)
        db.session.flush()
        _inscricao(transferido, p[1], date(2026, 1, 2), ativo=False)
        _inscricao(transferido, outra_turma, date(2026, 1, 5), ativo=True)
        _inscricao(inativo, p[1], date(2026, 1, 2))

        resultado = status_alunos(p[0].id, date(2026, 1, 12))

        assert resultado[desenturmado.id] is StatusAluno.DESENTURMADO
        assert resultado[transferido.id] is StatusAluno.NOVO
        assert inativo.id not in resultado
        assert len([key for key in resultado if key == transferido.id]) == 1


def test_periodo_inicial_e_total_enturmado_batem_com_tres_status(app):
    with app.app_context():
        unidade = Unidade(nome="Primeira")
        db.session.add(unidade)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="Primeiro",
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
        turma = Turma(nome="Primeira turma", unidade_id=unidade.id, periodo_letivo_id=periodo.id)
        db.session.add(turma)
        db.session.flush()

        alunos = [_aluno(unidade, f"Aluno {idx}") for idx in range(3)]
        _inscricao(alunos[0], turma, date(2026, 1, 1))
        _inscricao(alunos[1], turma, date(2026, 1, 2))
        _inscricao(alunos[1], turma, date(2026, 1, 3))
        _inscricao(alunos[2], turma, date(2026, 1, 4), ativo=False)

        resultado = status_alunos(periodo.id, date(2027, 1, 5))
        total_enturmados = 2
        total_por_status = sum(
            resultado.get(aluno.id) in {
                StatusAluno.NOVO,
                StatusAluno.RENOVADO,
                StatusAluno.RETORNANTE,
            }
            for aluno in alunos
        )

        assert resultado[alunos[0].id] is StatusAluno.NOVO
        assert resultado[alunos[1].id] is StatusAluno.NOVO
        assert total_por_status == total_enturmados


def test_data_historica_usa_inicio_e_desativacao_em_vez_da_flag_atual(app):
    with app.app_context():
        unidade, _, p1, p = _world()
        aluno = _aluno(unidade, "Vínculo histórico")
        _inscricao(aluno, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(
            aluno,
            p[1],
            date(2026, 1, 5),
            ativo=False,
            desativacao=datetime(2026, 1, 10, 10, 0),
        )

        assert status_aluno(aluno.id, p[0].id, date(2026, 1, 8)) is StatusAluno.RENOVADO
        assert status_aluno(aluno.id, p[0].id, date(2026, 1, 11)) is StatusAluno.DESENTURMADO


def test_periodo_inexistente_e_data_ref_invalida_sao_rejeitados(app):
    with app.app_context():
        with pytest.raises(ValueError, match="não encontrado"):
            status_alunos(999)

        unidade = Unidade(nome="NIT")
        db.session.add(unidade)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="P",
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 12, 31),
            unidade_id=unidade.id,
        )
        db.session.add(periodo)
        db.session.flush()
        with pytest.raises(TypeError, match="data_ref"):
            status_alunos(periodo.id, "2026-01-01")


def test_escopo_bi_usa_periodo_vigente_e_coorte_do_turno(app):
    with app.app_context():
        unidade, _, p1, p = _world()
        p1[1].turno = "Manhã"
        p[1].turno = "Tarde"
        renovado = _aluno(unidade, "Mudou de turno")
        novo = _aluno(unidade, "Novo no turno tarde")
        outros = _aluno(unidade, "Sem enturmação")

        _inscricao(renovado, p1[1], date(2025, 8, 1), ativo=False)
        _inscricao(renovado, p[1], date(2026, 1, 3))
        _inscricao(novo, p[1], date(2026, 1, 3))

        resultado_manha = status_alunos_para_bi(
            unidade_id=unidade.id,
            turno="Manhã",
            data_ref=date(2026, 1, 4),
        )
        resultado_tarde = status_alunos_para_bi(
            unidade_id=unidade.id,
            turno="Tarde",
            data_ref=date(2026, 1, 4),
        )
        resultado_periodo_implicito = status_alunos_para_bi(
            unidade_id=unidade.id,
            data_ref=date(2026, 3, 1),
        )

        assert resultado_manha == {renovado.id: StatusAluno.RENOVADO}
        assert resultado_tarde[renovado.id] is StatusAluno.RENOVADO
        assert resultado_tarde[novo.id] is StatusAluno.NOVO
        assert outros.id not in resultado_manha
        assert resultado_periodo_implicito[novo.id] is StatusAluno.NOVO


def test_escopo_bi_rejeita_periodo_de_outra_unidade(app):
    with app.app_context():
        _, _, _, p = _world()
        outra_unidade = Unidade(nome="Outra unidade")
        db.session.add(outra_unidade)
        db.session.flush()

        with pytest.raises(ValueError, match="não pertence à unidade"):
            status_alunos_para_bi(
                periodo_letivo_id=p[0].id,
                unidade_id=outra_unidade.id,
            )