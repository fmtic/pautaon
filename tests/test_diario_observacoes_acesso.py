# ruff: noqa: F811
"""Acesso e navegação para o Diário de Bordo da turma.

Antes a rota `/turma/<id>/observacoes` não era alcançável por nenhum link e
aceitava qualquer professor para qualquer turma (só checava o perfil). Agora:

- a página é restrita à unidade da turma (`assert_unidade_context`) e, para
  professor, às turmas em que ele é o responsável;
- há botão no painel do professor (`/professor/painel`) e no detalhe da turma
  (`/turma/<id>`).
"""

from datetime import date, time, timedelta

from _helpers import login_as, nova_oferta

from app import db
from app.models import Curso, PeriodoLetivo, RegistroAula, Turma, Unidade, User

TEXTO = "OBS_ACESSO_Diario da turma"


def _cenario(app):
    """Duas unidades, dois professores, admin/secretaria e um diário."""
    hoje = date.today()
    with app.app_context():
        un_a = Unidade(nome="Unidade A", ativo=True)
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add_all([un_a, un_b])
        db.session.flush()

        def _user(nome, email, role, unidade_id):
            user = User(
                name=nome, email=email, role=role,
                first_login=False, unidade_id=unidade_id,
            )
            user.set_password("SenhaLocal!123")
            db.session.add(user)
            db.session.flush()
            return user

        prof_a = _user("Prof A", "prof.a@x.com", "professor", un_a.id)
        prof_b = _user("Prof B", "prof.b@x.com", "professor", un_a.id)
        admin_a = _user("Admin A", "admin.a@x.com", "admin", un_a.id)
        sec_a = _user("Sec A", "sec.a@x.com", "secretaria", un_a.id)
        admin_b = _user("Admin B", "admin.b@x.com", "admin", un_b.id)

        periodo = PeriodoLetivo(
            nome="P Acesso", data_inicio=hoje - timedelta(days=30),
            data_fim=hoje + timedelta(days=30), unidade_id=un_a.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma_a = Turma(
            nome="Turma A", turno="Manhã", data_inicio=periodo.data_inicio,
            data_fim=periodo.data_fim, periodo_letivo_id=periodo.id,
            unidade_id=un_a.id, professor_id=prof_a.id, ativo=True,
        )
        turma_b = Turma(
            nome="Turma B", turno="Manhã", data_inicio=periodo.data_inicio,
            data_fim=periodo.data_fim, periodo_letivo_id=periodo.id,
            unidade_id=un_b.id, ativo=True,
        )
        db.session.add_all([turma_a, turma_b])
        db.session.flush()

        curso = Curso(nome="Curso A", unidade_id=un_a.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        oferta = nova_oferta(
            turma_a.id, curso.id, un_a.id, principal=True,
            professor_id=prof_a.id,
            dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
            hora_inicio=time(8), hora_fim=time(10),
        )
        _ = oferta  # oferta ativa: o painel do professor lista a turma

        db.session.add(RegistroAula(
            turma_id=turma_a.id, turma_curso_id=oferta.id, data=hoje,
            observacoes=TEXTO, unidade_id=un_a.id,
        ))
        db.session.commit()

        return {
            "un_a": un_a.id, "un_b": un_b.id,
            "prof_a": prof_a.id, "prof_b": prof_b.id,
            "admin_a": admin_a.id, "sec_a": sec_a.id, "admin_b": admin_b.id,
            "turma_a": turma_a.id, "turma_b": turma_b.id,
        }


def _url(ids):
    return f"/turma/{ids['turma_a']}/observacoes"


def test_professor_dono_abre_o_diario(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof_a"], ids["un_a"])
    resposta = client.get(_url(ids))
    assert resposta.status_code == 200
    assert TEXTO in resposta.get_data(as_text=True)


def test_professor_de_outra_turma_recebe_403(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof_b"], ids["un_a"])
    assert client.get(_url(ids)).status_code == 403


def test_professor_de_outra_unidade_recebe_403(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof_b"], ids["un_b"])
    assert client.get(f"/turma/{ids['turma_a']}/observacoes").status_code == 403


def test_admin_de_outra_unidade_recebe_403(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_b"], ids["un_b"])
    assert client.get(f"/turma/{ids['turma_a']}/observacoes").status_code == 403


def test_admin_e_secretaria_da_unidade_abrem(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    assert client.get(_url(ids)).status_code == 200
    login_as(client, ids["sec_a"], ids["un_a"])
    assert client.get(_url(ids)).status_code == 200


def test_turma_inexistente_retorna_404(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    assert client.get("/turma/999999/observacoes").status_code == 404


def test_painel_do_professor_tem_o_botao(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof_a"], ids["un_a"])
    resposta = client.get("/painel")
    assert resposta.status_code == 200
    assert _url(ids) in resposta.get_data(as_text=True)


def test_detalhe_da_turma_tem_o_botao(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    resposta = client.get(f"/turma/{ids['turma_a']}")
    assert resposta.status_code == 200
    assert _url(ids) in resposta.get_data(as_text=True)
