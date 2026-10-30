# ruff: noqa: F811
"""ETAPA D3b-2.3 — remoção de N+1 de frequência no histórico do aluno."""

from datetime import date

from _helpers import login_as, nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401
from test_frequencia_oferta import _base

from app.database import db
from app.models import (
    Aluno, Curso, Frequencia, PeriodoLetivo, Turma, TurmaCurso, Unidade, User,
)
from app.services.frequencia_oferta import frequencias_aluno_por_inscricao
from app.utils.logica import calcular_estatisticas_frequencia


def _login(client, uid):
    login_as(client, str(uid))
def test_equivalencia_batch_vs_antigo(app):
    s = _base(app)
    with app.app_context():
        aluno = Aluno(nome="Zoe", unidade_id=s and 1, ativo=True)
        # reusa unidade do _base: buscar unidade
        un = Unidade.query.first()
        aluno.unidade_id = un.id
        db.session.add(aluno)
        db.session.flush()
        # inscrição em Alfa/o1 + legado
        nova_inscricao(aluno.id, s["alfa"], s["o1"])
        # lançamentos misturados
        db.session.add_all([
            Frequencia(aluno_id=aluno.id, turma_id=s["alfa"], turma_curso_id=s["o1"],
                       data=date(2026, 3, 2), conceito="A", unidade_id=un.id),
            Frequencia(aluno_id=aluno.id, turma_id=s["alfa"], turma_curso_id=s["o1"],
                       data=date(2026, 3, 3), conceito="F", unidade_id=un.id),
            Frequencia(aluno_id=aluno.id, turma_id=s["alfa"], turma_curso_id=None,
                       data=date(2026, 3, 4), conceito="J", unidade_id=un.id),
        ])
        db.session.commit()

        from app.models import Inscricao
        inscs = Inscricao.query.filter_by(aluno_id=aluno.id).all()
        pares = [(i.turma_id, i.turma_curso_id) for i in inscs]

        # antigo: consulta por inscrição
        antigo = {}
        for tid, oid in pares:
            fs = Frequencia.query.filter_by(
                aluno_id=aluno.id, turma_id=tid, turma_curso_id=oid
            ).all()
            antigo[(tid, oid)] = calcular_estatisticas_frequencia(
                f.conceito for f in fs
            )

        batch = frequencias_aluno_por_inscricao(aluno.id, pares)
        assert batch == antigo


def test_n1_historico_constante(app, client):
    s = _base(app)
    with app.app_context():
        un = Unidade.query.first()
        aluno = Aluno(nome="N1Hist", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        # 2 inscrições
        nova_inscricao(aluno.id, s["alfa"], s["o1"])
        nova_inscricao(aluno.id, s["gema"], s["g"])
        db.session.commit()
        uid = User.query.filter_by(email="admin.freq@example.com").first().id
        un = Unidade.query.first()
        login_as(client, uid, un.id)
        aid = aluno.id

    from sqlalchemy import event
    from app.database import db as _db

    contagem = {"n": 0}

    def _before(conn, cursor, statement, params, context, executemany):
        if "frequencia" in statement.lower():
            contagem["n"] += 1

    event.listen(_db.engine, "before_cursor_execute", _before)
    try:
        contagem["n"] = 0
        resp = client.get(f"/aluno/{aid}/historico")
        assert resp.status_code == 200
        # UMA consulta em frequencia (o histórico não deve fazer N+1).
        assert contagem["n"] <= 1, contagem["n"]
    finally:
        event.remove(_db.engine, "before_cursor_execute", _before)
