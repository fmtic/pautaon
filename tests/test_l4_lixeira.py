from _helpers import login_as
# ruff: noqa: F811
"""ETAPA L4 — /turmas/lixeira e reativação de turma."""

from datetime import date, timedelta

from test_conselho_oferta import app, client  # noqa: F401
from test_frequencia_oferta import _base

from app.database import db
from app.models import (
    Aluno, Inscricao, LogAcao, Turma, TurmaCurso, Unidade, User,
)


def _login(client, uid, unidade_id=None):
    login_as(client, str(uid), unidade_id)
def _uid(app, email="admin.freq@example.com"):
    with app.app_context():
        return User.query.filter_by(email=email).first().id


def _setup_excluida(app, client):
    s = _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        un_id = un.id
        u = User.query.filter_by(email="admin.freq@example.com").first()
        _login(client, u.id, un_id)
        from app.models import Frequencia
        db.session.add(Frequencia(aluno_id=s and 1, turma_id=s["gema"],
                                 turma_curso_id=s["g"], data=date(2026, 3, 2),
                                 conceito="A", unidade_id=un_id))
        db.session.commit()
    client.post(f"/turma/excluir/{s['gema']}")
    return s, _uid(app), un_id


def test_lixeira_get_200_permitted(app, client):
    s, uid, un_id = _setup_excluida(app, client)
    with app.app_context():
        _login(client, uid, un_id)
    resp = client.get("/turmas/lixeira")
    assert resp.status_code == 200
    assert "Turma Gema" in resp.get_data(as_text=True)


def test_lixeira_get_403_non_permitted(app, client):
    _base(app)
    with app.app_context():
        from app.models import Unidade
        un = Unidade.query.first()
        prof = User(name="ProfX", email="profx@x.com", role="professor",
                    first_login=False, unidade_id=un.id)
        db.session.add(prof)
        db.session.commit()
        _login(client, prof.id, un.id)
    resp = client.get("/turmas/lixeira")
    assert resp.status_code == 403


def test_lixeira_visao_global_sem_botao(app, client):
    _base(app)
    with app.app_context():
        u = User.query.filter_by(email="admin.freq@example.com").first()
        _login(client, u.id, None)
    resp = client.get("/turmas/lixeira")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Somente leitura" in body or "Visão Global" in body


def test_reativar_turma_basico(app, client):
    s, uid, un_id = _setup_excluida(app, client)
    with app.app_context():
        _login(client, uid, un_id)
    resp = client.post(f"/turmas/reativar/{s['gema']}", data={"confirmar_periodo": "1"})
    assert resp.status_code == 302
    with app.app_context():
        t = Turma.query.get(s["gema"])
        assert t.ativo is True
        ofertas = TurmaCurso.query.filter_by(turma_id=s["gema"]).all()
        assert all(o.ativo for o in ofertas)

def test_reativar_periodo_encerrado_exige_confirmacao(app, client):
    s, uid, un_id = _setup_excluida(app, client)
    with app.app_context():
        from app.models import PeriodoLetivo
        t = Turma.query.get(s["gema"])
        p = PeriodoLetivo.query.get(t.periodo_letivo_id)
        p.data_fim = date.today() - timedelta(days=10)
        db.session.commit()
        _login(client, uid, un_id)
    resp = client.post(f"/turmas/reativar/{s['gema']}")
    assert resp.status_code == 302
    with app.app_context():
        t = Turma.query.get(s["gema"])
        assert t.ativo is False
    resp = client.post(f"/turmas/reativar/{s['gema']}", data={"confirmar_periodo": "1"})
    assert resp.status_code == 302
    with app.app_context():
        t = Turma.query.get(s["gema"])
        assert t.ativo is True


def test_reativar_logacao_gravado(app, client):
    s, uid, un_id = _setup_excluida(app, client)
    with app.app_context():
        _login(client, uid, un_id)
    before = LogAcao.query.count()
    client.post(f"/turmas/reativar/{s['gema']}", data={"confirmar_periodo": "1"})
    after = LogAcao.query.count()
    assert after >= before


def test_reativar_isolamento_outra_unidade(app, client):
    s, uid, un_id = _setup_excluida(app, client)
    with app.app_context():
        from app.models import Unidade
        un2 = Unidade(nome="U2", ativo=True)
        db.session.add(un2)
        db.session.commit()
        u = User.query.filter_by(email="admin.freq@example.com").first()
        _login(client, u.id, un2.id)
    resp = client.post(f"/turmas/reativar/{s['gema']}", data={"confirmar_periodo": "1"})
    assert resp.status_code in (302, 403)


def test_reativar_idempotencia(app, client):
    s, uid, un_id = _setup_excluida(app, client)
    with app.app_context():
        _login(client, uid, un_id)
    client.post(f"/turmas/reativar/{s['gema']}", data={"confirmar_periodo": "1"})
    resp = client.post(f"/turmas/reativar/{s['gema']}", data={"confirmar_periodo": "1"})
    assert resp.status_code == 302


def test_ciclo_excluir_reativar(app, client):
    s, uid, un_id = _setup_excluida(app, client)
    with app.app_context():
        _login(client, uid, un_id)
    client.post(f"/turmas/reativar/{s['gema']}", data={"confirmar_periodo": "1"})
    with app.app_context():
        t = Turma.query.get(s["gema"])
        assert t.ativo is True

