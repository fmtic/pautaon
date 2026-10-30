# ruff: noqa: F811
"""PARTE B — pauta impressa e I1 por OFERTA, sem herança do professor da turma.

Decisão (fechada): "professor da oferta" = SOMENTE `turma_curso.professor_id`.
A turma é um agregador de ofertas — `turma.professor_id` não dá acesso à pauta
impressa nem aos dados do aluno (I1).

Cenário base: a turma tem `professor_id = prof_c` (que NÃO leciona nenhuma
oferta) e as ofertas têm `prof_a` (O1, principal) e `prof_b` (O2). Assim o
mesmo teste prova as duas direções: `prof_a` imprime a própria oferta mesmo sem
ser o professor da turma, e `prof_c` (o professor da turma) recebe 403.

A herança continua existindo na listagem de turmas e no painel do conselho —
fora do escopo desta parte (registrado no backlog).
"""

from datetime import time, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from _helpers import login_as, nova_inscricao, nova_oferta
from _i1_helpers import conteudo, info
from test_conselho_oferta import app, client  # noqa: F401

from app import db
from app.models import (
    Aluno,
    Curso,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.utils.timezone import get_local_now

GRADE = dict(
    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
    hora_inicio=time(8),
    hora_fim=time(10),
)


def _usuario(nome, email, role, unidade_id):
    user = User(name=nome, email=email, role=role, first_login=False,
                unidade_id=unidade_id)
    user.set_password("SenhaLocal!123")
    return user


def _seed(app, *, ofertas=2):
    """Turma com `prof_c` (não leciona), O1 de `prof_a`, O2 de `prof_b`."""
    hoje = get_local_now().date()
    with app.app_context():
        un = Unidade(nome="Unidade PB", ativo=True)
        db.session.add(un)
        db.session.flush()

        prof_a = _usuario("Professor A", "pa.pb@x.com", "professor", un.id)
        prof_b = _usuario("Professor B", "pb.pb@x.com", "professor", un.id)
        prof_c = _usuario("Professor da Turma", "pc.pb@x.com", "professor", un.id)
        admin = _usuario("Admin PB", "admin.pb@x.com", "admin", un.id)
        secretaria = _usuario("Secretaria PB", "sec.pb@x.com", "secretaria", un.id)
        pedagogico = _usuario("Pedagogico PB", "ped.pb@x.com", "pedagogico", un.id)
        db.session.add_all(
            [prof_a, prof_b, prof_c, admin, secretaria, pedagogico]
        )
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P PB", data_inicio=hoje - timedelta(days=30),
            data_fim=hoje + timedelta(days=30), unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma PB", unidade_id=un.id, periodo_letivo_id=periodo.id,
            professor_id=prof_c.id, ativo=True,
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
        )
        db.session.add(turma)
        db.session.flush()

        cursos = [
            Curso(nome=f"Curso PB {i}", unidade_id=un.id, ativo=True)
            for i in range(2)
        ]
        db.session.add_all(cursos)
        db.session.flush()

        o1 = nova_oferta(
            turma.id, cursos[0].id, un.id, principal=True,
            professor_id=prof_a.id, **GRADE,
        )
        o2 = None
        if ofertas >= 2:
            o2 = nova_oferta(
                turma.id, cursos[1].id, un.id, principal=False,
                professor_id=prof_b.id, **GRADE,
            )

        aluno_a = Aluno(nome="Aluno A", unidade_id=un.id, ativo=True)
        aluno_b = Aluno(nome="Aluno B", unidade_id=un.id, ativo=True)
        aluno_c = Aluno(nome="Aluno C", unidade_id=un.id, ativo=True)
        db.session.add_all([aluno_a, aluno_b, aluno_c])
        db.session.flush()

        nova_inscricao(aluno_a.id, turma.id, o1.id)
        nova_inscricao(aluno_c.id, turma.id, o1.id)
        if o2 is not None:
            nova_inscricao(aluno_b.id, turma.id, o2.id)
            nova_inscricao(aluno_c.id, turma.id, o2.id)

        db.session.commit()
        return {
            "un": un.id,
            "prof_a": prof_a.id,
            "prof_b": prof_b.id,
            "prof_c": prof_c.id,
            "admin": admin.id,
            "secretaria": secretaria.id,
            "pedagogico": pedagogico.id,
            "turma": turma.id,
            "o1": o1.id,
            "o2": o2.id if o2 is not None else None,
            "aluno_a": aluno_a.id,
            "aluno_b": aluno_b.id,
            "aluno_c": aluno_c.id,
        }


def _impressao(client, ids, oferta_id=None):
    url = f"/turma/{ids['turma']}/imprimir-pauta"
    if oferta_id is not None:
        url += f"?turma_curso={oferta_id}"
    return client.get(url)


# ---------------------------------------------------------------------------
# 1. Professor imprime a oferta que leciona — mesmo sem ser o da turma
# ---------------------------------------------------------------------------

def test_professor_imprime_a_propria_oferta(app, client):
    ids = _seed(app)
    login_as(client, ids["prof_a"], ids["un"])

    resposta = _impressao(client, ids, ids["o1"])
    corpo = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "Aluno A" in corpo
    assert "Aluno C" in corpo
    assert "Aluno B" not in corpo
    assert "Curso PB 0" in corpo


def test_professor_b_imprime_a_oferta_dele(app, client):
    ids = _seed(app)
    login_as(client, ids["prof_b"], ids["un"])

    resposta = _impressao(client, ids, ids["o2"])
    corpo = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "Aluno B" in corpo
    assert "Aluno A" not in corpo
    assert "Curso PB 1" in corpo


# ---------------------------------------------------------------------------
# 2. Sem herança: o professor da turma não imprime oferta de outro
# ---------------------------------------------------------------------------

def test_professor_da_turma_sem_oferta_recebe_403(app, client):
    """`prof_c` é o professor da TURMA, mas não leciona O1/O2."""
    ids = _seed(app)
    login_as(client, ids["prof_c"], ids["un"])

    assert _impressao(client, ids, ids["o1"]).status_code == 403
    assert _impressao(client, ids, ids["o2"]).status_code == 403
    assert _impressao(client, ids).status_code == 403


def test_professor_de_outra_oferta_recebe_403(app, client):
    ids = _seed(app)
    login_as(client, ids["prof_a"], ids["un"])

    assert _impressao(client, ids, ids["o2"]).status_code == 403


def test_oferta_nao_pode_ficar_sem_professor_no_banco(app, client):
    """G1/P2 (d6e7f8a9b0c1): a premissa do teste antigo — oferta com
    `professor_id` NULL — não existe mais; o banco recusa a atribuição.
    antigo × novo × motivo: testava o 403 defensivo com oferta sem professor;
    agora prova o NOT NULL na camada do banco, que elimina o estado."""
    ids = _seed(app)
    with app.app_context():
        turma_curso = db.session.get(TurmaCurso, ids["o1"])
        turma_curso.professor_id = None
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    # Intacta, a oferta continua imprimível pelo dono e pelo admin.
    login_as(client, ids["prof_a"], ids["un"])
    assert _impressao(client, ids, ids["o1"]).status_code == 200

    login_as(client, ids["admin"], ids["un"])
    assert _impressao(client, ids, ids["o1"]).status_code == 200


def test_oferta_inativa_do_professor_recebe_403(app, client):
    ids = _seed(app)
    with app.app_context():
        db.session.get(TurmaCurso, ids["o2"]).ativo = False
        db.session.commit()

    login_as(client, ids["prof_b"], ids["un"])
    assert _impressao(client, ids, ids["o2"]).status_code == 403


# ---------------------------------------------------------------------------
# 3. Sem parâmetro: 1 oferta ativa → ela; 2+ → a de menor id (P3 do G1)
# ---------------------------------------------------------------------------

def test_sem_parametro_usa_a_oferta_de_menor_id_quando_e_dele(app, client):
    """`prof_a` é dono da O1, a de menor id: sem parâmetro imprime a O1."""
    ids = _seed(app)
    login_as(client, ids["prof_a"], ids["un"])

    resposta = _impressao(client, ids)
    corpo = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "Curso PB 0" in corpo
    assert "Aluno A" in corpo
    assert "Aluno B" not in corpo


def test_sem_parametro_da_oferta_de_menor_id_de_outro_recebe_403(app, client):
    """G1 (P3): sem parâmetro vale a oferta de **menor id**, não a dele."""
    ids = _seed(app)
    login_as(client, ids["prof_b"], ids["un"])

    assert _impressao(client, ids).status_code == 403


def test_oferta_principal_nao_altera_acesso(app, client):
    """R2: trocar a `principal` não muda nenhum acesso (só a listagem/a ordem)."""
    ids = _seed(app)
    with app.app_context():
        db.session.get(TurmaCurso, ids["o1"]).principal = False
        db.session.get(TurmaCurso, ids["o2"]).principal = True
        db.session.commit()

    login_as(client, ids["prof_a"], ids["un"])
    assert _impressao(client, ids, ids["o1"]).status_code == 200
    assert _impressao(client, ids, ids["o2"]).status_code == 403
    # Sem parâmetro continua valendo a de menor id (O1), agora não principal.
    assert _impressao(client, ids).status_code == 200

    login_as(client, ids["prof_b"], ids["un"])
    assert _impressao(client, ids, ids["o2"]).status_code == 200
    assert _impressao(client, ids, ids["o1"]).status_code == 403
    assert _impressao(client, ids).status_code == 403


# ---------------------------------------------------------------------------
# 4. "Outras ofertas" e lista de alunos: nada de ofertas que ele não leciona
# ---------------------------------------------------------------------------

def test_professor_nao_ve_outras_ofertas(app, client):
    """Aluno C está em O1 e O2; o professor de O1 não vê a indicação de O2."""
    ids = _seed(app)
    login_as(client, ids["prof_a"], ids["un"])

    corpo = _impressao(client, ids, ids["o1"]).get_data(as_text=True)

    assert "Outras ofertas" not in corpo
    assert "Curso PB 1" not in corpo


def test_admin_continua_vendo_outras_ofertas(app, client):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])

    corpo = _impressao(client, ids, ids["o1"]).get_data(as_text=True)

    assert "Outras ofertas" in corpo
    assert "Curso PB 1" in corpo


def test_admin_sem_parametro_mantem_redirecionamento(app, client):
    """Comportamento atual preservado para os demais perfis (2+ ofertas)."""
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = _impressao(client, ids)

    assert resposta.status_code == 302
    assert "/frequencia" in resposta.headers["Location"]


def test_secretaria_e_pedagogico_inalterados(app, client):
    ids = _seed(app)

    login_as(client, ids["secretaria"], ids["un"])
    assert _impressao(client, ids, ids["o2"]).status_code == 200

    login_as(client, ids["pedagogico"], ids["un"])
    assert _impressao(client, ids, ids["o1"]).status_code == 200


def test_professor_de_outra_unidade_recebe_403(app, client):
    ids = _seed(app)
    with app.app_context():
        un2 = Unidade(nome="Unidade PB 2", ativo=True)
        db.session.add(un2)
        db.session.flush()
        outro = _usuario("Prof Outra Unidade", "pu.pb@x.com", "professor", un2.id)
        db.session.add(outro)
        db.session.commit()
        outro_id = outro.id

    login_as(client, outro_id, ids["un"])
    assert _impressao(client, ids, ids["o1"]).status_code == 403


# ---------------------------------------------------------------------------
# 5. Com 1 oferta ativa, o professor vê só os alunos inscritos nela
# ---------------------------------------------------------------------------

def test_professor_com_uma_oferta_ve_somente_inscritos_nela(app, client):
    ids = _seed(app)
    with app.app_context():
        # O2 sai de cena: o aluno B fica com inscrição ativa numa oferta inativa.
        db.session.get(TurmaCurso, ids["o2"]).ativo = False
        db.session.commit()

    login_as(client, ids["prof_a"], ids["un"])
    resposta = _impressao(client, ids, ids["o1"])
    corpo = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "Aluno A" in corpo
    assert "Aluno B" not in corpo

    login_as(client, ids["admin"], ids["un"])
    assert _impressao(client, ids, ids["o1"]).status_code == 200


# ---------------------------------------------------------------------------
# 6. I1 (modal + acompanhante/instruções) sem herança de turma.professor_id
# ---------------------------------------------------------------------------

def test_i1_professor_da_turma_sem_a_oferta_recebe_403(app, client):
    """Antes da PARTE B o professor da turma herdava o acesso ao aluno."""
    ids = _seed(app)
    conteudo(app, ids["aluno_a"], acompanhante="Mãe", vai=True,
             instrucoes="Precisa de apoio.")
    login_as(client, ids["prof_c"], ids["un"])

    assert info(client, ids["aluno_a"]).status_code == 403


def test_i1_professor_da_oferta_acessa_mesmo_sem_ser_o_da_turma(app, client):
    ids = _seed(app)
    conteudo(app, ids["aluno_a"], acompanhante="Mãe", vai=True,
             instrucoes="Precisa de apoio.")
    login_as(client, ids["prof_a"], ids["un"])

    resposta = info(client, ids["aluno_a"])

    assert resposta.status_code == 200
    assert resposta.get_json()["instrucoes"] == "Precisa de apoio."


def test_i1_impressao_dele_mostra_as_linhas_do_aluno(app, client):
    ids = _seed(app)
    conteudo(app, ids["aluno_a"], acompanhante="Mãe", vai=True,
             instrucoes="Precisa de apoio.")
    login_as(client, ids["prof_a"], ids["un"])

    corpo = _impressao(client, ids, ids["o1"]).get_data(as_text=True)

    assert "Quem acompanha:" in corpo
    assert "Precisa de apoio." in corpo


def test_i1_periodo_encerrado_continua_bloqueado(app, client):
    """O resto da regra do I1 não muda: período encerrado ⇒ 403 / linhas fora."""
    ids = _seed(app)
    conteudo(app, ids["aluno_a"], acompanhante="Mãe", vai=True,
             instrucoes="Precisa de apoio.")
    hoje = get_local_now().date()
    with app.app_context():
        periodo = PeriodoLetivo.query.filter_by(nome="P PB").one()
        periodo.data_inicio = hoje - timedelta(days=60)
        periodo.data_fim = hoje - timedelta(days=1)
        db.session.commit()

    login_as(client, ids["prof_a"], ids["un"])
    assert info(client, ids["aluno_a"]).status_code == 403

    corpo = _impressao(client, ids, ids["o1"]).get_data(as_text=True)
    assert "Quem acompanha:" not in corpo
    assert "Precisa de apoio." not in corpo
