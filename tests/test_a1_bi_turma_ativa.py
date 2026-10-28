# ruff: noqa: F811
"""A1 (item 3) — critério de "turma ativa" nos indicadores de frequência/aulas.

Achado M1: FRE-005 (``frequencia_media``) somava a frequência de turma
excluída logicamente (``Turma.ativo = False``), enquanto Resumo, FRE-009
(``frequencia_por_turma``), FRE-010 (``frequencia_por_curso``) e o painel
pedagógico já filtravam ``Turma.ativo``. Este módulo caracteriza a divergência
e fixa o alinhamento de ``_base_frequencia`` / ``_base_registro_aula``.

Cenário mínimo (números do achado M1, banco de ensaio):
    - Turma ATIVA .......... 9 A + 6 F = 60,0%
    - Turma EXCLUÍDA ....... 2 A (100%) — preservada no banco
Antes: FRE-005 = 11/17 = 64,7% (soma das duas). Depois: 9/15 = 60,0%.
"""

from datetime import date, timedelta

from _helpers import nova_oferta
from test_conselho_oferta import app, client  # noqa: F401

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    Unidade,
)
from app.relatorios.bi_alunos import (
    alunos_frequencia_75_89,
    alunos_frequencia_90,
    alunos_frequencia_inferior_75,
    aulas_por_turma,
    frequencia_media,
    frequencia_por_curso,
    frequencia_por_turma,
    total_aulas_registradas,
    total_faltas,
    total_lancamentos_frequencia,
    total_presencas,
)

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _semeia(app):
    with app.app_context():
        un = Unidade(nome="Unidade A1B", ativo=True)
        db.session.add(un)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="P A1B",
            data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            unidade_id=un.id,
            ativo=True,
        )
        curso = Curso(nome="Curso A1B", unidade_id=un.id, ativo=True)
        db.session.add_all([periodo, curso])
        db.session.flush()

        def _turma(nome, ativo):
            turma = Turma(
                nome=nome,
                turno="Manhã",
                data_inicio=DATA_INI,
                data_fim=DATA_FIM,
                periodo_letivo_id=periodo.id,
                unidade_id=un.id,
                ativo=ativo,
            )
            db.session.add(turma)
            db.session.flush()
            return turma

        ativa = _turma("Turma Ativa", ativo=True)
        excluida = _turma("Turma Excluída", ativo=False)
        # Oferta da turma ativa (FRE-010 usa a oferta) e da excluída (inativa,
        # como o `desativar_oferta` deixa ao excluir a turma).
        nova_oferta(ativa.id, curso.id, un.id, principal=True)
        nova_oferta(excluida.id, curso.id, un.id, principal=True, ativo=False)

        def _aluno(nome, turma, presencas, faltas):
            aluno = Aluno(nome=nome, unidade_id=un.id, ativo=True)
            db.session.add(aluno)
            db.session.flush()
            # UNIQUE (aluno, turma, data): cada lançamento em um dia distinto.
            for i in range(presencas):
                db.session.add(
                    Frequencia(
                        aluno_id=aluno.id,
                        turma_id=turma.id,
                        data=DATA_INI + timedelta(days=i),
                        conceito="A",
                        unidade_id=un.id,
                    )
                )
            for i in range(faltas):
                db.session.add(
                    Frequencia(
                        aluno_id=aluno.id,
                        turma_id=turma.id,
                        data=DATA_INI + timedelta(days=presencas + i),
                        conceito="F",
                        unidade_id=un.id,
                    )
                )
            return aluno

        _aluno("Aluno Ativo", ativa, 9, 6)
        _aluno("Aluno Excluído", excluida, 2, 0)

        # RegistroAula: 2 na ativa, 3 na excluída (preservados no banco).
        db.session.add_all(
            [
                RegistroAula(
                    turma_id=ativa.id, data=DATA_INI + timedelta(days=i),
                    unidade_id=un.id,
                )
                for i in range(2)
            ]
            + [
                RegistroAula(
                    turma_id=excluida.id, data=DATA_INI + timedelta(days=i),
                    unidade_id=un.id,
                )
                for i in range(3)
            ]
        )
        db.session.commit()
        return {"unidade": un.id, "ativa": ativa.id, "excluida": excluida.id}


def test_frequencia_media_ignora_turma_excluida(app):
    """Antes 64,7% (11/17, somando a turma excluída); agora 60,0% (9/15)."""
    ids = _semeia(app)
    with app.app_context():
        assert frequencia_media(unidade_id=ids["unidade"]) == 60.0


def test_frequencia_media_por_turma_e_por_curso_concordam(app):
    """Os três leitores devem devolver o MESMO 60,0% para a turma ativa."""
    ids = _semeia(app)
    with app.app_context():
        por_turma = {linha["nome"]: linha["valor"] for linha in frequencia_por_turma(
            unidade_id=ids["unidade"]
        )}
        por_curso = {linha["nome"]: linha["valor"] for linha in frequencia_por_curso(
            unidade_id=ids["unidade"]
        )}
    assert por_turma == {"Turma Ativa": 60.0}
    assert por_curso == {"Curso A1B": 60.0}


def test_contadores_de_frequencia_ignoram_turma_excluida(app):
    ids = _semeia(app)
    with app.app_context():
        assert total_lancamentos_frequencia(unidade_id=ids["unidade"]) == 15
        assert total_presencas(unidade_id=ids["unidade"]) == 9
        assert total_faltas(unidade_id=ids["unidade"]) == 6

def test_faixas_de_frequencia_ignoram_turma_excluida(app):
    """FRE-006/007/008 saem de `_totais_por_aluno` (mesma base de FRE-005)."""
    ids = _semeia(app)
    with app.app_context():
        # O aluno da turma excluída tem 100% (hi) e não pode mais entrar.
        assert alunos_frequencia_90(unidade_id=ids["unidade"]) == 0
        assert alunos_frequencia_75_89(unidade_id=ids["unidade"]) == 0
        # Só o aluno da turma ativa (60,0%) fica abaixo de 75.
        assert alunos_frequencia_inferior_75(unidade_id=ids["unidade"]) == 1


def test_aulas_registradas_ignoram_turma_excluida(app):
    ids = _semeia(app)
    with app.app_context():
        assert total_aulas_registradas(unidade_id=ids["unidade"]) == 2
        assert {linha["nome"] for linha in aulas_por_turma(
            unidade_id=ids["unidade"]
        )} == {"Turma Ativa"}


def test_filtro_por_turma_excluida_continua_zerando(app):
    """Filtro explícito por turma excluída devolve 0 — nunca "ressuscita" dados."""
    ids = _semeia(app)
    with app.app_context():
        assert frequencia_media(turma_id=ids["excluida"]) == 0.0
        assert total_aulas_registradas(turma_id=ids["excluida"]) == 0
