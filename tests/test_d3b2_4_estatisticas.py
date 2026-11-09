# ruff: noqa: F811
"""ETAPA D3b-2.4 — estatísticas do GET /frequencia por oferta."""

from _helpers import login_as
from test_frequencia_oferta import _base

from app.models import User


def _login(client, uid, unidade_id=None):
    login_as(client, str(uid), unidade_id)
def _uid(app):
    with app.app_context():
        return User.query.filter_by(email="admin.freq@example.com").first().id


def test_estats_oferta_a_nao_ve_b(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o1']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 50.0%" in body


def test_estats_oferta_b_nao_ve_a(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o2']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 0.0%" in body


def test_estats_oferta_unica_legado_inalterada(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)
    resp = client.get(f"/frequencia?turma_id={s['gema']}&turma_curso={s['g']}&data=2026-03-02")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "P: 75.0%" in body


def test_n1_estats_constante(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        _login(client, _uid(app), un.id if un else None)

    from sqlalchemy import event
    from app.database import db as _db

    contagem = {"n": 0}

    def _before(conn, cursor, statement, params, context, executemany):
        if "frequencia" in statement.lower():
            contagem["n"] += 1

    event.listen(_db.engine, "before_cursor_execute", _before)
    try:
        contagem["n"] = 0
        resp = client.get(f"/frequencia?turma_id={s['alfa']}&turma_curso={s['o1']}&data=2026-03-02")
        assert resp.status_code == 200
        assert contagem["n"] <= 2, contagem["n"]
    finally:
        event.remove(_db.engine, "before_cursor_execute", _before)


def test_n1_pauta_constante_com_valores(app, client):
    """AJ16-B: a pauta com valores N:N não ganha N+1 ao crescer a turma.

    O ``selectin`` de ``RegistroAula.valores`` (e ``.temas``) emite UMA
    consulta adicional constante, independente do número de alunos. Este teste
    compara o total de queries com 2 e 10 alunos e exige igualdade.
    """
    from datetime import time, timedelta

    from sqlalchemy import event

    from app import db
    from app.database import db as _db
    from app.models import (
        Aluno,
        Curso,
        PeriodoLetivo,
        RegistroAula,
        Turma,
        Unidade,
        User,
        ValorEsportista,
    )
    from app.utils.datetime_parse import parse_date
    from app.utils.logica import carregar_contexto_turma, get_local_now
    from _helpers import nova_inscricao, nova_oferta

    hoje = get_local_now().date()

    def montar(n_alunos):
        with app.app_context():
            un = Unidade(nome=f"Un N1 {n_alunos}", ativo=True)
            db.session.add(un)
            db.session.flush()
            admin = User(
                name=f"Admin N1 {n_alunos}",
                email=f"admin.n1.{n_alunos}@x.com",
                role="admin", first_login=False, unidade_id=un.id,
            )
            admin.set_password("SenhaLocal!123")
            db.session.add(admin)
            db.session.flush()
            periodo = PeriodoLetivo(
                nome=f"P N1 {n_alunos}",
                data_inicio=hoje - timedelta(days=30),
                data_fim=hoje + timedelta(days=30),
                unidade_id=un.id, ativo=True,
            )
            db.session.add(periodo)
            db.session.flush()
            turma = Turma(
                nome=f"Turma N1 {n_alunos}", turno="Manhã",
                data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
                periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
            )
            db.session.add(turma)
            db.session.flush()
            curso = Curso(
                nome=f"Curso N1 {n_alunos}", unidade_id=un.id, ativo=True,
            )
            db.session.add(curso)
            db.session.flush()
            oferta = nova_oferta(
                turma.id, curso.id, un.id,
                dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
                hora_inicio=time(8), hora_fim=time(10),
            )
            valor = ValorEsportista(
                nome="Alegria", unidade_id=un.id, ativo=True,
            )
            db.session.add(valor)
            db.session.flush()
            for i in range(n_alunos):
                aluno = Aluno(
                    nome=f"Aluno N1 {n_alunos} {i}",
                    unidade_id=un.id, ativo=True,
                )
                db.session.add(aluno)
                db.session.flush()
                nova_inscricao(aluno.id, turma.id, oferta.id)
            # Cria um diário com valor vinculado à aula.
            data = carregar_contexto_turma(turma.id)["datas"][0]
            diario = RegistroAula(
                turma_id=turma.id, turma_curso_id=oferta.id,
                data=parse_date(data), unidade_id=un.id,
            )
            diario.valores = [valor]
            db.session.add(diario)
            db.session.commit()
            return {
                "un": un.id, "admin": admin.id, "turma": turma.id,
                "oferta": oferta.id, "data": data,
            }

    def contar(n_alunos):
        s = montar(n_alunos)
        login_as(client, str(s["admin"]), s["un"])
        contagem = {"n": 0}

        def _before(conn, cursor, statement, params, context, executemany):
            contagem["n"] += 1

        event.listen(_db.engine, "before_cursor_execute", _before)
        try:
            contagem["n"] = 0
            resp = client.get(
                f"/frequencia?turma_id={s['turma']}"
                f"&turma_curso={s['oferta']}&data={s['data']}"
            )
            assert resp.status_code == 200
            return contagem["n"]
        finally:
            event.remove(_db.engine, "before_cursor_execute", _before)

    n2 = contar(2)
    n10 = contar(10)
    assert n2 == n10, (
        f"N+1 detectado: {n2} queries com 2 alunos, {n10} com 10"
    )
