# ruff: noqa: F811
"""ETAPA D3b-2.7 — testes da regra D2 no f_prog (Parte A)."""

from datetime import date, timedelta

from test_conselho_oferta import app, client  # noqa: F401
from app.database import db
from app.models import (
    Aluno, Curso, Frequencia, PeriodoLetivo, Turma, TurmaCurso, Unidade, User,
)
from app.utils.logica import calcular_frequencias_relatorio
from _helpers import nova_inscricao


def test_fprog_legado_oferta_unica_vai_ao_programa_da_oferta(app):
    with app.app_context():
        un = Unidade(nome="U2", ativo=True)
        db.session.add(un)
        db.session.flush()
        periodo = PeriodoLetivo(nome="P2", data_inicio=date.today() - timedelta(days=30),
                               data_fim=date.today() + timedelta(days=60),
                               unidade_id=un.id, ativo=True)
        db.session.add(periodo)
        db.session.flush()
        curso = Curso(nome="C", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        prof = User(name="Prof2", email="prof2.fprog@x.com", role="professor",
                    first_login=False, unidade_id=un.id)
        db.session.add(prof)
        db.session.flush()
        turma = Turma(nome="T2", ativo=True, unidade_id=un.id,
                      periodo_letivo_id=periodo.id, turno="Manhã",
                      programa="ProgTurma",
                      data_inicio=periodo.data_inicio, data_fim=periodo.data_fim)
        db.session.add(turma)
        db.session.flush()
        oferta = TurmaCurso(turma_id=turma.id, curso_id=curso.id, unidade_id=un.id,
                           programa="ProgOferta", ativo=True, principal=True,
                           professor_id=prof.id)
        db.session.add(oferta)
        db.session.flush()
        aluno = Aluno(nome="Al2", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, oferta.id)
        db.session.add(Frequencia(aluno_id=aluno.id, turma_id=turma.id,
                                 turma_curso_id=None, data=date.today(),
                                 conceito="A", unidade_id=un.id))
        db.session.commit()
        turmas = [Turma.query.get(turma.id)]
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(turmas)
        assert f_prog.get("ProgOferta") == 100.0
        assert "ProgTurma" not in f_prog

def test_fprog_legado_sem_oferta_unica_cai_em_turma_programa(app):
    with app.app_context():
        un = Unidade(nome="U3", ativo=True)
        db.session.add(un)
        db.session.flush()
        periodo = PeriodoLetivo(nome="P3", data_inicio=date.today() - timedelta(days=30),
                               data_fim=date.today() + timedelta(days=60),
                               unidade_id=un.id, ativo=True)
        db.session.add(periodo)
        db.session.flush()
        c1 = Curso(nome="C1b", unidade_id=un.id, ativo=True)
        c2 = Curso(nome="C2b", unidade_id=un.id, ativo=True)
        db.session.add_all([c1, c2])
        db.session.flush()
        prof = User(name="Prof3", email="prof3.fprog@x.com", role="professor",
                    first_login=False, unidade_id=un.id)
        db.session.add(prof)
        db.session.flush()
        turma = Turma(nome="T3", ativo=True, unidade_id=un.id,
                      periodo_letivo_id=periodo.id, turno="Manhã",
                      programa="ProgTurma",
                      data_inicio=periodo.data_inicio, data_fim=periodo.data_fim)
        db.session.add(turma)
        db.session.flush()
        o1 = TurmaCurso(turma_id=turma.id, curso_id=c1.id, unidade_id=un.id,
                        programa="ProgA", ativo=True, principal=True,
                        professor_id=prof.id)
        o2 = TurmaCurso(turma_id=turma.id, curso_id=c2.id, unidade_id=un.id,
                        programa="ProgB", ativo=True, principal=False,
                        professor_id=prof.id)
        db.session.add_all([o1, o2])
        db.session.flush()
        aluno = Aluno(nome="Al3", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        from _helpers import nova_inscricao
        nova_inscricao(aluno.id, turma.id, o1.id)
        db.session.add(Frequencia(aluno_id=aluno.id, turma_id=turma.id,
                                 turma_curso_id=None, data=date.today(),
                                 conceito="A", unidade_id=un.id))
        db.session.commit()
        turmas = [Turma.query.get(turma.id)]
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(turmas)
        assert f_prog.get("ProgTurma") == 100.0


def test_fprog_turma_sem_lancamento_sem_divisao_por_zero(app):
    with app.app_context():
        un = Unidade(nome="U4", ativo=True)
        db.session.add(un)
        db.session.flush()
        periodo = PeriodoLetivo(nome="P4", data_inicio=date.today() - timedelta(days=30),
                               data_fim=date.today() + timedelta(days=60),
                               unidade_id=un.id, ativo=True)
        db.session.add(periodo)
        db.session.flush()
        curso = Curso(nome="C4", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        prof = User(name="Prof4", email="prof4.fprog@x.com", role="professor",
                    first_login=False, unidade_id=un.id)
        db.session.add(prof)
        db.session.flush()
        turma = Turma(nome="T4", ativo=True, unidade_id=un.id,
                      periodo_letivo_id=periodo.id, turno="Manhã",
                      programa="ProgVazio",
                      data_inicio=periodo.data_inicio, data_fim=periodo.data_fim)
        db.session.add(turma)
        db.session.flush()
        oferta = TurmaCurso(turma_id=turma.id, curso_id=curso.id, unidade_id=un.id,
                           programa="ProgOferta4", ativo=True, principal=True,
                           professor_id=prof.id)
        db.session.add(oferta)
        db.session.flush()
        db.session.commit()
        turmas = [Turma.query.get(turma.id)]
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(turmas)
        assert f_prog.get("ProgOferta4", 0.0) == 0.0

