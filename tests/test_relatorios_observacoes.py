# ruff: noqa: F811
"""Diário de Observações em modo global (Painel Pedagógico).

A rota `/relatorios/observacoes` lista o diário de todas as turmas do período
com filtros encadeados por período letivo, turma, curso (oferta) e professor.
É restrita a `ROLES_RELATORIOS`; o fluxo por turma (`/turma/<id>/observacoes`)
continua sem filtros e com a sua própria permissão.
"""

from datetime import date, time, timedelta

from _helpers import login_as, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401

from app import db
from app.models import (
    Curso,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    Unidade,
    User,
)

OBS_T1 = "OBS_T1_primeira turma"
ATIV_T2 = "ATIV_T2_segunda turma"
OBS_P2 = "OBS_P2_periodo anterior"


def _cenario(app):
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

        admin_a = _user("Admin A", "admin.obs.a@x.com", "admin", un_a.id)
        admin_b = _user("Admin B", "admin.obs.b@x.com", "admin", un_b.id)
        prof1 = _user("Prof Um", "prof.um@x.com", "professor", un_a.id)
        prof2 = _user("Prof Dois", "prof.dois@x.com", "professor", un_a.id)
        prof3 = _user("Prof Tres", "prof.tres@x.com", "professor", un_a.id)

        p1 = PeriodoLetivo(
            nome="P1 Atual", data_inicio=hoje - timedelta(days=15),
            data_fim=hoje + timedelta(days=30), unidade_id=un_a.id, ativo=True,
        )
        p2 = PeriodoLetivo(
            nome="P2 Anterior", data_inicio=hoje - timedelta(days=200),
            data_fim=hoje - timedelta(days=120), unidade_id=un_a.id, ativo=False,
        )
        db.session.add_all([p1, p2])
        db.session.flush()

        def _turma(nome, periodo, professor, unidade):
            turma = Turma(
                nome=nome, turno="Manhã", data_inicio=periodo.data_inicio,
                data_fim=periodo.data_fim, periodo_letivo_id=periodo.id,
                unidade_id=unidade.id, professor_id=professor.id, ativo=True,
            )
            db.session.add(turma)
            db.session.flush()
            return turma

        def _oferta(turma, nome_curso, professor):
            curso = Curso(nome=nome_curso, unidade_id=turma.unidade_id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            return nova_oferta(
                turma.id, curso.id, turma.unidade_id, principal=True,
                professor_id=professor.id,
                dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
                hora_inicio=time(8), hora_fim=time(10),
            )

        t1 = _turma("Turma Um", p1, prof1, un_a)
        o1 = _oferta(t1, "Curso Um", prof1)
        t2 = _turma("Turma Dois", p1, prof2, un_a)
        o2 = _oferta(t2, "Curso Dois", prof2)
        t3 = _turma("Turma Antiga", p2, prof3, un_a)

        def _diario(turma, oferta_id, dia, observacoes=None, atividades=None):
            db.session.add(RegistroAula(
                turma_id=turma.id, turma_curso_id=oferta_id, data=dia,
                observacoes=observacoes, atividades=atividades,
                unidade_id=un_a.id,
            ))

        _diario(t1, o1.id, hoje - timedelta(days=2), observacoes=OBS_T1)
        _diario(t2, o2.id, hoje - timedelta(days=1), atividades=ATIV_T2)
        # Registro sem nenhum dos dois textos não deve aparecer.
        _diario(t2, o2.id, hoje, observacoes=None, atividades="")
        _diario(t3, None, hoje - timedelta(days=150), observacoes=OBS_P2)
        db.session.commit()

        return {
            "un_a": un_a.id, "un_b": un_b.id,
            "admin_a": admin_a.id, "admin_b": admin_b.id,
            "prof1": prof1.id, "prof2": prof2.id,
            "p1": p1.id, "p2": p2.id,
            "t1": t1.id, "t2": t2.id, "t3": t3.id,
            "o1": o1.id, "o2": o2.id,
        }


def _url(ids, **params):
    from urllib.parse import urlencode

    params = {"periodo_letivo_id": ids["p1"], **params}
    return "/relatorios/observacoes?" + urlencode(params)


def test_admin_ve_todos_os_textos_do_periodo(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    resposta = client.get(_url(ids))
    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert OBS_T1 in corpo
    assert ATIV_T2 in corpo
    assert OBS_P2 not in corpo


def test_registro_sem_texto_nao_aparece(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(_url(ids)).get_data(as_text=True)
    # Dois registros com texto (OBS_T1 e ATIV_T2); o vazio fica de fora.
    marcador = 'class="list-group-item border-0 shadow-sm rounded mb-4 p-4"'
    assert corpo.count(marcador) == 2


def test_filtro_por_turma(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(_url(ids, turma_id=ids["t1"])).get_data(as_text=True)
    assert OBS_T1 in corpo
    assert ATIV_T2 not in corpo


def test_filtro_por_curso_da_turma(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(
        _url(ids, turma_id=ids["t2"], turma_curso_id=ids["o2"])
    ).get_data(as_text=True)
    assert ATIV_T2 in corpo
    assert OBS_T1 not in corpo


def test_filtro_por_professor(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(_url(ids, professor_id=ids["prof2"])).get_data(as_text=True)
    assert ATIV_T2 in corpo
    assert OBS_T1 not in corpo


def test_periodo_anterior_mostra_o_historico(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(_url(ids, periodo_letivo_id=ids["p2"])).get_data(as_text=True)
    assert OBS_P2 in corpo
    assert OBS_T1 not in corpo


def test_professor_nao_acessa_o_modo_global(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof1"], ids["un_a"])
    assert client.get(_url(ids)).status_code == 403


def test_unidade_b_nao_ve_registros_da_unidade_a(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_b"], ids["un_b"])
    resposta = client.get(_url(ids))
    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert OBS_T1 not in corpo
    assert ATIV_T2 not in corpo


def test_painel_pedagogico_tem_o_botao(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(
        f"/relatorios/painel?periodo_letivo_id={ids['p1']}"
    ).get_data(as_text=True)
    assert "/relatorios/observacoes" in corpo
    assert "Diário de observações" in corpo


def test_fluxo_por_turma_continua_sem_filtros(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(f"/turma/{ids['t1']}/observacoes").get_data(as_text=True)
    assert OBS_T1 in corpo
    assert 'action="/relatorios/observacoes"' not in corpo


def test_turma_de_outro_periodo_e_ignorada(app, client):
    """`turma_id` de outro período não vaza registros: cai para 'todas'."""
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(_url(ids, turma_id=ids["t3"])).get_data(as_text=True)
    assert OBS_P2 not in corpo
    assert OBS_T1 in corpo


def test_limite_de_linhas_anunciado_quando_truncar(app, client, monkeypatch):
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    from app.relatorios import observacoes as rota

    monkeypatch.setattr(rota, "LIMITE", 1)
    corpo = client.get(_url(ids)).get_data(as_text=True)
    assert "registros mais recentes" in corpo


def test_oferta_de_outra_turma_nao_vaza(app, client):
    """Oferta que não pertence à turma filtrada é ignorada."""
    ids = _cenario(app)
    login_as(client, ids["admin_a"], ids["un_a"])
    corpo = client.get(
        _url(ids, turma_id=ids["t2"], turma_curso_id=ids["o1"])
    ).get_data(as_text=True)
    assert ATIV_T2 in corpo
    assert OBS_T1 not in corpo
