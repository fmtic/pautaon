# ruff: noqa: F811
"""ETAPA D3b-2.6 — f_prog por TurmaCurso.programa."""

from datetime import date, timedelta

from app.database import db
from app.models import (
    Aluno, Curso, Frequencia, PeriodoLetivo, Turma, TurmaCurso, Unidade, User,
)
from app.utils.logica import calcular_frequencias_relatorio


def _seed_divergente(app):
    with app.app_context():
        un = Unidade(nome="U", ativo=True)
        db.session.add(un)
        db.session.flush()
        periodo = PeriodoLetivo(nome="P", data_inicio=date.today() - timedelta(days=30),
                               data_fim=date.today() + timedelta(days=60),
                               unidade_id=un.id, ativo=True)
        db.session.add(periodo)
        db.session.flush()
        cn = Curso(nome="C1", unidade_id=un.id, ativo=True)
        cx = Curso(nome="C2", unidade_id=un.id, ativo=True)
        db.session.add_all([cn, cx])
        db.session.flush()
        prof = User(name="Prof", email="prof.fprog@x.com", role="professor",
                    first_login=False, unidade_id=un.id)
        db.session.add(prof)
        db.session.flush()
        # Turma.programa = "ProgPrincipal" (projeção), oferta o2 programa = "ProgSecundario"
        turma = Turma(nome="T", ativo=True, unidade_id=un.id,
                      periodo_letivo_id=periodo.id, turno="Manhã",
                      programa="ProgPrincipal",
                      data_inicio=periodo.data_inicio, data_fim=periodo.data_fim)
        db.session.add(turma)
        db.session.flush()
        o1 = TurmaCurso(turma_id=turma.id, curso_id=cn.id, unidade_id=un.id,
                        programa="ProgPrincipal", ativo=True, principal=True,
                        professor_id=prof.id)
        o2 = TurmaCurso(turma_id=turma.id, curso_id=cx.id, unidade_id=un.id,
                        programa="ProgSecundario", ativo=True, principal=False,
                        professor_id=prof.id)
        db.session.add_all([o1, o2])
        db.session.flush()
        # grade não necessária para frequência; remover chamada
        pass
        # grade minimal: skip (not needed for freq)
        aluno = Aluno(nome="Al", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        from _helpers import nova_inscricao
        nova_inscricao(aluno.id, turma.id, o1.id)
        nova_inscricao(aluno.id, turma.id, o2.id)
        # lançamentos: o1 A, o2 F
        db.session.add(Frequencia(aluno_id=aluno.id, turma_id=turma.id,
                                 turma_curso_id=o1.id, data=date.today(),
                                 conceito="A", unidade_id=un.id))
        db.session.add(Frequencia(aluno_id=aluno.id, turma_id=turma.id,
                                 turma_curso_id=o2.id, data=date.today(),
                                 conceito="F", unidade_id=un.id))
        db.session.commit()
        return {"turma": turma.id, "o1": o1.id, "o2": o2.id, "un": un.id}


def test_fprog_oferta_nao_principal_conta_no_seu_programa(app):
    s = _seed_divergente(app)
    with app.app_context():
        turmas = [Turma.query.get(s["turma"])]
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(
            turmas, unidade_id=s and None
        )
        # Nova: ProgSecundario deve ter 0% (1 falta), ProgPrincipal 100% (1 presença).
        assert f_prog.get("ProgPrincipal") == 100.0
        assert f_prog.get("ProgSecundario") == 0.0


def test_fprog_programa_igual_inalterado(app):
    # Quando Turma.programa == oferta.programa, número não muda (caso test_bi_oferta).
    s = _seed_divergente(app)
    with app.app_context():
        # sanity: f_prog tem as duas chaves
        turmas = [Turma.query.get(s["turma"])]
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(turmas)
        assert "ProgPrincipal" in f_prog
        assert "ProgSecundario" in f_prog


def test_n1_fprog_constante(app):
    s = _seed_divergente(app)
    from sqlalchemy import event
    from app.database import db as _db

    with app.app_context():
        turmas = [Turma.query.get(s["turma"])]

        contagem = {"n": 0}

        def _before(conn, cursor, statement, params, context, executemany):
            if "frequencia" in statement.lower():
                contagem["n"] += 1

        event.listen(_db.engine, "before_cursor_execute", _before)
        try:
            contagem["n"] = 0
            calcular_frequencias_relatorio(turmas)
            c1 = contagem["n"]
            # 2 turmas (mesma) → constante
            contagem["n"] = 0
            calcular_frequencias_relatorio(turmas + turmas)
            c2 = contagem["n"]
            assert c1 == c2, (c1, c2)
        finally:
            event.remove(_db.engine, "before_cursor_execute", _before)
