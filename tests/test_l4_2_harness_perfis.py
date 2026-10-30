"""ETAPA L4.2 — auditoria do harness (P5–P7): troca de perfil no mesmo teste.

O fixture `app` usado pela maioria dos testes mantém um `app_context` aberto
durante toda a função e o Flask **reutiliza** esse AppContext em cada request
do `test_client`. Como `flask.g` vive no AppContext, o `_login_user` cacheado
pelo Flask-Login sobrevive entre requisições: trocar o `_user_id` da sessão não
troca o usuário. Em produção cada request empurra seu próprio AppContext,
então não é defeito de aplicação — é armadilha de harness (convenção T1 §5.6:
"um usuário por teste").

Estes testes fixam o padrão de prova da auditoria:
    1. aplicação SEM contexto aberto durante os requests (o padrão do módulo
       `test_h4_leitores_grade_variavel_smoke`) → a troca de perfil vale e o
       403 do perfil sem permissão acontece (classe "a" da auditoria);
    2. mesmo teste com o fixture que mantém o contexto → a troca é IGNORADA
       (classe "b"; o assert de 403 passaria por engano / nunca seria
       exercitado);
    3. `login_as` (harness) limpa o cache de `g` e faz o 403 acontecer no
       fixture com contexto aberto — correção padrão proposta na P7.
"""
# ruff: noqa: F811 — fixtures `app`/`client` reaproveitadas do harness D5.

from _helpers import login_as
from test_conselho_oferta import app, client  # noqa: F401 (fixtures)

from app import create_app
from app.database import db
from app.models import Unidade, User
from config import Config

#: Rota acessível a admin/pedagogico/secretaria — professor recebe 403.
ROTA_SO_GESTAO = "/turmas/lixeira"


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _seed_identidades():
    """Unidade + admin + professor (mesmo tenant). Devolve os ids."""
    un = Unidade(nome="Unidade Harness", ativo=True)
    db.session.add(un)
    db.session.flush()
    admin = User(
        name="Admin Harness", email="admin.harness@example.com", role="admin",
        first_login=False,
    )
    admin.set_password("SenhaLocal!123")
    prof = User(
        name="Prof Harness", email="prof.harness@example.com", role="professor",
        first_login=False, unidade_id=un.id,
    )
    prof.set_password("SenhaLocal!123")
    db.session.add_all([admin, prof])
    db.session.commit()
    return {"un": un.id, "admin": admin.id, "prof": prof.id}


def _login_inline(client, uid, unidade_id=None):
    """Login "cru" (sem limpar `g`) — o padrão antigo dos testes."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
        if unidade_id is not None:
            sess["unidade_id"] = unidade_id


def test_p6_classe_a_app_sem_contexto_aberto_a_troca_de_perfil_vale():
    """Classe (a): app criado sem contexto preso — cada request tem seu `g`.

    É o padrão de `test_h4_leitores_grade_variavel_smoke.py` (o único teste da
    suíte que usa três perfis na mesma função). Aqui o 403 do professor
    acontece de verdade, depois de um request do admin.
    """
    test_app = create_app(SQLiteTestConfig)
    with test_app.app_context():
        db.create_all()
        ids = _seed_identidades()

    cli_admin = test_app.test_client()
    _login_inline(cli_admin, ids["admin"], ids["un"])
    assert cli_admin.get(ROTA_SO_GESTAO).status_code == 200

    cli_prof = test_app.test_client()
    _login_inline(cli_prof, ids["prof"])
    assert cli_prof.get(ROTA_SO_GESTAO).status_code == 403


def test_p6_classe_b_fixture_com_contexto_aberto_ignora_a_troca(app, client):
    """Classe (b): o fixture mantém o AppContext — o 2º perfil NÃO assume.

    Caracterização do harness (não da aplicação): depois de um request como
    admin, gravar o professor na sessão continua executando como admin. Um
    assert `status_code == 403` aqui falharia; um assert de permissão "ok"
    passaria sem nunca exercitar o perfil restrito.
    """
    with app.app_context():
        ids = _seed_identidades()

    _login_inline(client, ids["admin"], ids["un"])
    assert client.get(ROTA_SO_GESTAO).status_code == 200

    _login_inline(client, ids["prof"])  # troca só a sessão: cache de g permanece
    resp = client.get(ROTA_SO_GESTAO)
    assert resp.status_code == 200, (
        "com o AppContext preso ao fixture o request reusa o admin de `g` — "
        "se aqui der 403, o harness mudou e a auditoria L4.2 precisa ser revista"
    )


def test_p7_login_as_limpa_o_cache_e_o_403_acontece(app, client):
    """P7: `login_as` (harness) torna a troca de perfil real e reversível."""
    with app.app_context():
        ids = _seed_identidades()

    login_as(client, ids["admin"], ids["un"])
    assert client.get(ROTA_SO_GESTAO).status_code == 200

    login_as(client, ids["prof"])
    assert client.get(ROTA_SO_GESTAO).status_code == 403

    login_as(client, ids["admin"], ids["un"])
    assert client.get(ROTA_SO_GESTAO).status_code == 200
