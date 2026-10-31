import pytest
from _helpers import login_as

from app.database import db
from app.models import User, LoginControle, LogAcao
from app.models.enums import UserRole
from app.auth import chave_conta, chave_ip
from config import Config


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app(app_com_servidor):
    return app_com_servidor


@pytest.fixture
def admin_user(app):
    with app.app_context():
        u = User(name="Admin", email="admin@test.com", role=UserRole.ADMIN.value, first_login=False)
        u.set_password("SenhaAdmin!1")
        db.session.add(u)
        db.session.commit()
        return u.id


def _criar_bloqueio_conta(app, email, nivel=1):
    with app.app_context():
        from datetime import timedelta
        from app.models.base import get_local_now
        chave = chave_conta(email)
        reg = LoginControle(escopo="conta", chave_hash=chave, falhas=5,
                            janela_inicio=get_local_now().replace(tzinfo=None),
                            bloqueado_ate=get_local_now().replace(tzinfo=None) + timedelta(minutes=15),
                            nivel=nivel, atualizado_em=get_local_now().replace(tzinfo=None))
        db.session.add(reg)
        db.session.commit()
        return reg.id



def test_t1_admin_ve_card_e_bloqueio(client, app, admin_user):
    uid = _criar_bloqueio_conta(app, "bloq@test.com")
    login_as(client, str(admin_user))
    resp = client.get("/admin/painel")
    assert resp.status_code == 200
    assert b"Bloqueios de login" in resp.data
    with app.app_context():
        reg = db.session.get(LoginControle, uid)
        assert reg.chave_hash[:8].encode() in resp.data
    assert b"bloq@test.com" not in resp.data


def test_t2_papeis_recebem_403(client, app):
    for role in ["pedagogico", "secretaria", "gerencia", "professor", "servico_social"]:
        with app.app_context():
            u = User(name=role, email=f"{role}@test.com", role=role, first_login=False)
            u.set_password("Senha!123")
            db.session.add(u)
            db.session.commit()
            uid = u.id
        login_as(client, str(uid))
        r1 = client.post("/admin/login-controle/desbloquear-conta", data={"email": "x@y.com"})
        r2 = client.post("/admin/login-controle/desbloquear-ip", data={"ip": "1.2.3.4"})
        assert r1.status_code == 403
        assert r2.status_code == 403


def test_t3_desbloquear_conta_libera_login(client, app, admin_user):
    email = "user@test.com"
    with app.app_context():
        u = User(name="User", email=email, role="professor", first_login=False)
        u.set_password("SenhaUser!1")
        db.session.add(u)
        db.session.commit()
    _criar_bloqueio_conta(app, email)
    login_as(client, str(admin_user))
    r = client.post("/admin/login-controle/desbloquear-conta", data={"email": email}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Conta desbloqueada" in r.data
    client.post("/logout")
    r2 = client.post("/login", data={"email": email, "password": "SenhaUser!1"}, follow_redirects=True)
    assert r2.status_code == 200


def test_t4_desbloquear_ip(client, app, admin_user):
    import datetime as dt
    with app.app_context():
        chave = chave_ip("10.0.0.1")
        reg = LoginControle(escopo="ip", chave_hash=chave, falhas=30,
                            janela_inicio=dt.datetime.now(),
                            bloqueado_ate=dt.datetime.now() + dt.timedelta(minutes=15),
                            nivel=0, atualizado_em=dt.datetime.now())
        db.session.add(reg)
        db.session.commit()
    login_as(client, str(admin_user))
    r = client.post("/admin/login-controle/desbloquear-ip", data={"ip": "10.0.0.1"}, follow_redirects=True)
    assert r.status_code == 200
    assert b"IP desbloqueado" in r.data


def test_t5_sem_bloqueio_nao_cria_linha(client, app, admin_user):
    with app.app_context():
        before = LoginControle.query.count()
    login_as(client, str(admin_user))
    r = client.post("/admin/login-controle/desbloquear-conta", data={"email": "ninguem@test.com"}, follow_redirects=True)
    assert b"Nenhum bloqueio encontrado" in r.data
    with app.app_context():
        after = LoginControle.query.count()
    assert before == after


def test_t6_entrada_invalida(client, app, admin_user):
    login_as(client, str(admin_user))
    r1 = client.post("/admin/login-controle/desbloquear-conta", data={"email": ""}, follow_redirects=True)
    assert b"Informe um e-mail" in r1.data
    r2 = client.post("/admin/login-controle/desbloquear-ip", data={"ip": "abc"}, follow_redirects=True)
    assert b"Informe um IP" in r2.data
    r3 = client.post("/admin/login-controle/desbloquear-ip", data={"ip": "999.1.1.1"}, follow_redirects=True)
    assert b"Informe um IP" in r3.data



def test_t7_csrf_sem_token_retorna_400():
    import os
    os.environ.setdefault("APP_ENV", "development")
    from app import create_app, db
    from config import Config
    class Cfg(Config):
        SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        TESTING = True
        WTF_CSRF_ENABLED = True
    a = create_app(Cfg)
    with a.app_context():
        db.create_all()
        u = User(name="Admin", email="admin@test.com", role=UserRole.ADMIN.value, first_login=False)
        u.set_password("SenhaAdmin!1")
        db.session.add(u)
        from app.auth import chave_conta
        from datetime import timedelta
        from app.models.base import get_local_now
        reg = LoginControle(escopo="conta", chave_hash=chave_conta("x@test.com"), falhas=5,
                            janela_inicio=get_local_now().replace(tzinfo=None),
                            bloqueado_ate=get_local_now().replace(tzinfo=None) + timedelta(minutes=15),
                            nivel=1, atualizado_em=get_local_now().replace(tzinfo=None))
        db.session.add(reg)
        db.session.commit()
        admin_id = u.id
    c = a.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["_fresh"] = True
    r = c.post("/admin/login-controle/desbloquear-conta", data={"email": "x@test.com"})
    assert r.status_code == 400
    with a.app_context():
        db.session.remove()
        db.drop_all()


def test_t8_log_formato_exato(client, app, admin_user):
    email = "fmt@test.com"
    _criar_bloqueio_conta(app, email)
    login_as(client, str(admin_user))
    client.post("/admin/login-controle/desbloquear-conta", data={"email": email}, follow_redirects=True)
    with app.app_context():
        log = LogAcao.query.filter_by(acao="Desbloqueio de login").order_by(LogAcao.id.desc()).first()
        assert log is not None
        assert log.detalhes.startswith("escopo=conta chave=")
        assert "por_usuario_id=" in log.detalhes
        assert "encontrado=sim" in log.detalhes
        assert email not in (log.detalhes or "")


def test_t9_nivel_volta_a_zero(client, app, admin_user):
    email = "nivel@test.com"
    _criar_bloqueio_conta(app, email, nivel=2)
    login_as(client, str(admin_user))
    client.post("/admin/login-controle/desbloquear-conta", data={"email": email}, follow_redirects=True)
    with app.app_context():
        reg = LoginControle.query.filter_by(escopo="conta", chave_hash=chave_conta(email)).first()
        assert reg is not None
        assert reg.nivel == 0


def test_t10_bloqueio_expirado_nao_aparece(client, app, admin_user):
    import datetime as dt
    with app.app_context():
        chave = chave_conta("exp@test.com")
        reg = LoginControle(escopo="conta", chave_hash=chave, falhas=5,
                            janela_inicio=dt.datetime.now(),
                            bloqueado_ate=dt.datetime.now() - dt.timedelta(minutes=5),
                            nivel=1, atualizado_em=dt.datetime.now())
        db.session.add(reg)
        db.session.commit()
    login_as(client, str(admin_user))
    resp = client.get("/admin/painel")
    assert resp.status_code == 200
    assert b"exp@test.com" not in resp.data
