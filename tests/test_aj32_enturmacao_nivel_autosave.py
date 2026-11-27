"""AJ32 — autosave do nível do aluno na enturmação (servidor + contrato).

Cobre: JSON AJAX, idempotência, erros 400/403/404, CSRF, isolamento por
unidade, fallback sem JS (redirect+flash), ausência de escrita extra.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

os.environ.setdefault("APP_ENV", "development")

from _helpers import login_as, nova_inscricao, nova_oferta  # noqa: E402
from app import create_app, db  # noqa: E402
from app.models import Aluno, Curso, Inscricao, Nivel, PeriodoLetivo, Turma, Unidade, User  # noqa: E402
from config import Config  # noqa: E402


class _CsrfTestConfig(Config):
    SECRET_KEY = "chave-aj32-csrf-testes-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app_csrf():
    app = create_app(_CsrfTestConfig)
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client_csrf(app_csrf):
    return app_csrf.test_client()


DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _seed(app):
    with app.app_context():
        un = Unidade(nome="Unidade AJ32", ativo=True)
        outra = Unidade(nome="Outra AJ32", ativo=True)
        db.session.add_all([un, outra])
        db.session.flush()

        admin = User(
            name="Admin AJ32", email="aj32-admin@example.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        admin.set_password("SenhaLocal!123")
        prof = User(
            name="Prof AJ32", email="aj32-prof@example.com", role="professor",
            first_login=False, unidade_id=un.id,
        )
        prof.set_password("SenhaLocal!123")
        admin_outra = User(
            name="Admin Outra", email="aj32-outra@example.com", role="admin",
            first_login=False, unidade_id=outra.id,
        )
        admin_outra.set_password("SenhaLocal!123")

        periodo = PeriodoLetivo(
            nome="Periodo AJ32", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        curso = Curso(nome="Curso AJ32", unidade_id=un.id, ativo=True)
        curso2 = Curso(nome="Curso AJ32 B", unidade_id=un.id, ativo=True)
        db.session.add_all([admin, prof, admin_outra, periodo, curso, curso2])
        db.session.flush()

        turma = Turma(
            nome="Turma AJ32", data_inicio=DATA_INI, data_fim=DATA_FIM,
            periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta = nova_oferta(turma.id, curso.id, un.id, principal=True)
        oferta2 = nova_oferta(turma.id, curso2.id, un.id, principal=False)

        n1 = Nivel(nome="Basico", curso_id=curso.id, unidade_id=un.id, ativo=True)
        n2 = Nivel(nome="Avancado", curso_id=curso.id, unidade_id=un.id, ativo=True)
        n_outro = Nivel(nome="Outro Curso", curso_id=curso2.id, unidade_id=un.id, ativo=True)
        aluno = Aluno(nome="Aluno AJ32", unidade_id=un.id, ativo=True)
        aluno_outra = Aluno(nome="Aluno Outra", unidade_id=outra.id, ativo=True)
        db.session.add_all([n1, n2, n_outro, aluno, aluno_outra])
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, oferta.id, nivel="Basico")
        aluno.nivel = "Basico"
        db.session.commit()
        return {
            "unidade": un.id,
            "outra_unidade": outra.id,
            "admin": admin.id,
            "prof": prof.id,
            "admin_outra": admin_outra.id,
            "turma": turma.id,
            "oferta": oferta.id,
            "oferta2": oferta2.id,
            "aluno": aluno.id,
            "aluno_outra": aluno_outra.id,
            "nivel_basico": n1.id,
            "nivel_avancado": n2.id,
        }


def _post_ajax(client, aluno_id, payload, headers=None):
    base_headers = {"Accept": "application/json"}
    if headers:
        base_headers.update(headers)
    return client.post(
        f"/aluno/{aluno_id}/atualizar-nivel",
        json=payload,
        headers=base_headers,
    )


def test_ajax_sucesso_retorna_json_e_persiste(client, app):
    ids = _seed(app)
    login_as(client, str(ids["admin"]), ids["unidade"])
    r = _post_ajax(client, ids["aluno"], {
        "turma_id": ids["turma"],
        "turma_curso_id": ids["oferta"],
        "nivel": "Avancado",
    })
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["nivel_valor"] == "Avancado"
    assert data["nivel_nome"] == "Avancado"
    assert data["aluno_id"] == ids["aluno"]
    assert data["turma_curso_id"] == ids["oferta"]
    assert "message" in data

    with app.app_context():
        aluno = db.session.get(Aluno, ids["aluno"])
        insc = Inscricao.query.filter_by(turma_curso_id=ids["oferta"], aluno_id=ids["aluno"], ativo=True).first()
        assert aluno.nivel == "Avancado"
        assert insc.nivel == "Avancado"


def test_ajax_idempotente_nao_gera_erro_e_retorna_ok(client, app):
    ids = _seed(app)
    login_as(client, str(ids["admin"]), ids["unidade"])
    payload = {
        "turma_id": ids["turma"],
        "turma_curso_id": ids["oferta"],
        "nivel": "Basico",
    }
    r1 = _post_ajax(client, ids["aluno"], payload)
    r2 = _post_ajax(client, ids["aluno"], payload)
    assert r1.status_code == 200 and r1.get_json()["ok"] is True
    assert r2.status_code == 200 and r2.get_json()["ok"] is True
    with app.app_context():
        aluno = db.session.get(Aluno, ids["aluno"])
        insc = Inscricao.query.filter_by(turma_curso_id=ids["oferta"], aluno_id=ids["aluno"], ativo=True).first()
        assert aluno.nivel == "Basico"
        assert insc.nivel == "Basico"


def test_ajax_400_oferta_invalida(client, app):
    ids = _seed(app)
    login_as(client, str(ids["admin"]), ids["unidade"])
    r = _post_ajax(client, ids["aluno"], {
        "turma_id": ids["turma"],
        "turma_curso_id": "",
        "nivel": "Avancado",
    })
    assert r.status_code == 400
    assert r.get_json()["ok"] is False
    assert "message" in r.get_json()


def test_ajax_404_inscricao_inexistente(client, app):
    ids = _seed(app)
    login_as(client, str(ids["admin"]), ids["unidade"])
    r = _post_ajax(client, ids["aluno"], {
        "turma_id": ids["turma"],
        "turma_curso_id": ids["oferta2"],  # aluno não inscrito nessa oferta
        "nivel": "Avancado",
    })
    assert r.status_code == 404
    assert r.get_json()["ok"] is False


def test_ajax_403_sem_permissao(client, app):
    ids = _seed(app)
    login_as(client, str(ids["prof"]), ids["unidade"])
    r = _post_ajax(client, ids["aluno"], {
        "turma_id": ids["turma"],
        "turma_curso_id": ids["oferta"],
        "nivel": "Avancado",
    })
    assert r.status_code == 403
    assert r.get_json()["ok"] is False


def test_ajax_404_isolamento_unidade(client, app):
    ids = _seed(app)
    # admin de outra unidade não deve alterar aluno da unidade AJ32
    login_as(client, str(ids["admin_outra"]), ids["outra_unidade"])
    r = _post_ajax(client, ids["aluno"], {
        "turma_id": ids["turma"],
        "turma_curso_id": ids["oferta"],
        "nivel": "Avancado",
    })
    assert r.status_code in (403, 404)
    assert r.get_json()["ok"] is False
    with app.app_context():
        aluno = db.session.get(Aluno, ids["aluno"])
        assert aluno.nivel == "Basico"


def test_fallback_form_sem_js_redirect_e_flash(client, app):
    ids = _seed(app)
    login_as(client, str(ids["admin"]), ids["unidade"])
    r = client.post(
        f"/aluno/{ids['aluno']}/atualizar-nivel",
        data={
            "turma_id": ids["turma"],
            "turma_curso_id": ids["oferta"],
            "nivel": "Avancado",
        },
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)
    assert f"/turma/{ids['turma']}" in (r.headers.get("Location") or "")
    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert any("atualizado com sucesso" in msg.lower() for _, msg in flashes)
    with app.app_context():
        insc = Inscricao.query.filter_by(turma_curso_id=ids["oferta"], aluno_id=ids["aluno"], ativo=True).first()
        assert insc.nivel == "Avancado"


def test_csrf_ausente_bloqueia_quando_csrf_habilitado(client_csrf, app_csrf):
    ids = _seed(app_csrf)
    login_as(client_csrf, str(ids["admin"]), ids["unidade"])
    r = client_csrf.post(
        f"/aluno/{ids['aluno']}/atualizar-nivel",
        json={
            "turma_id": ids["turma"],
            "turma_curso_id": ids["oferta"],
            "nivel": "Avancado",
        },
        headers={"Accept": "application/json"},
    )
    # Flask-WTF normalmente retorna 400 para CSRF ausente/inválido.
    assert r.status_code in (400, 403)
    with app_csrf.app_context():
        aluno = db.session.get(Aluno, ids["aluno"])
        assert aluno.nivel == "Basico"


def test_ajax_nao_altera_outros_campos(client, app):
    ids = _seed(app)
    login_as(client, str(ids["admin"]), ids["unidade"])
    with app.app_context():
        before = db.session.get(Aluno, ids["aluno"])
        snapshot = (before.nome, before.ativo, before.unidade_id)
        insc_before = Inscricao.query.filter_by(turma_curso_id=ids["oferta"], aluno_id=ids["aluno"], ativo=True).first()
        insc_snapshot = (insc_before.ativo, insc_before.turma_id, insc_before.turma_curso_id)

    r = _post_ajax(client, ids["aluno"], {
        "turma_id": ids["turma"],
        "turma_curso_id": ids["oferta"],
        "nivel": "Avancado",
    })
    assert r.status_code == 200
    with app.app_context():
        after = db.session.get(Aluno, ids["aluno"])
        insc_after = Inscricao.query.filter_by(turma_curso_id=ids["oferta"], aluno_id=ids["aluno"], ativo=True).first()
        assert (after.nome, after.ativo, after.unidade_id) == snapshot
        assert (insc_after.ativo, insc_after.turma_id, insc_after.turma_curso_id) == insc_snapshot
        assert insc_after.nivel == "Avancado"
