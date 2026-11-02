# ruff: noqa: F811
"""AJ6-B — o professor só acessa (lê e escreve) as SUAS ofertas.

Regra (MER §7.14, §12.27; decisão fechada do I1/PARTE B): não existe mais
"professor da turma" — só o professor da OFERTA (``TurmaCurso.professor_id``),
que por sua vez pertence a uma turma (agregador de ofertas). Um professor
vinculado a UMA oferta não pode ver nem lançar a pauta/CRUD/diário das outras
ofertas da mesma turma. Demais perfis: inalterados.

Cenário:
    - T1: oferta A (pA), B (pB), C (pC) — pA só leciona A.
    - T2: oferta D (pA), E (pA), F (pB) — pA leciona D e E (duas ofertas).
    - Alunos e diário distintos por oferta.

Matriz (pA): rota própria = permitida; rota de oferta alheia (B/C/F) = 403,
sem vazar a existência; e o seletor/pauta nunca expõe as ofertas alheias.
"""

from datetime import time, timedelta

import pytest
from _helpers import (
    dia_de_aula_ate,
    hoje_ref,
    login_as,
    nova_inscricao,
    nova_oferta,
)

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())
DIAS_TODOS = "Segunda, Terça, Quarta, Quinta, Sexta"


def _iso(data_alvo):
    return data_alvo.strftime("%Y-%m-%d")


def _usuario(nome, role, unidade_id):
    user = User(
        name=nome, email=f"{nome.lower().replace(' ', '.')}@aj6b.test",
        role=role, first_login=False, unidade_id=unidade_id,
    )
    user.set_password("SenhaLocal!123")
    return user


def _oferta(turma, curso, unidade, prof, *, principal=False):
    return nova_oferta(
        turma.id, curso.id, unidade.id,
        programa=f"Prog {curso.nome}", principal=principal,
        professor_id=prof.id, dias_semana=DIAS_TODOS,
        hora_inicio=time(8), hora_fim=time(10),
    )


def _setup(app):
    with app.app_context():
        un = Unidade(nome="Unidade AJ6B", ativo=True)
        un2 = Unidade(nome="Unidade AJ6B 2", ativo=True)
        db.session.add_all([un, un2])
        db.session.flush()

        pa = _usuario("Professor Alfa", "professor", un.id)
        pb = _usuario("Professor Bravo", "professor", un.id)
        pc = _usuario("Professor Charlie", "professor", un.id)
        px = _usuario("Professor Outra Un", "professor", un2.id)
        admin = _usuario("Admin AJ6B", "admin", un.id)
        secre = _usuario("Sec AJ6B", "secretaria", un.id)
        ped = _usuario("Ped AJ6B", "pedagogico", un.id)
        gerencia = _usuario("Ger AJ6B", "gerencia", un.id)
        social = _usuario("Soc AJ6B", "servico_social", un.id)
        db.session.add_all([pa, pb, pc, px, admin, secre, ped, gerencia, social])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P AJ6B", data_inicio=HOJE - timedelta(days=40),
            data_fim=HOJE + timedelta(days=40), unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        def _turma(nome, professor_de):
            t = Turma(
                nome=nome, unidade_id=un.id, periodo_letivo_id=periodo.id,
                professor_id=professor_de.id, ativo=True,
                data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
            )
            db.session.add(t)
            db.session.flush()
            return t

        t1 = _turma("Turma Um", pa)   # professor da TURMA é pA (vestigial)
        t2 = _turma("Turma Dois", pb)

        def _curso(nome):
            c = Curso(nome=nome, unidade_id=un.id, ativo=True)
            db.session.add(c)
            db.session.flush()
            return c

        o_a = _oferta(t1, _curso("CURSO-ALFA"), un, pa, principal=True)
        o_b = _oferta(t1, _curso("CURSO-BRAVO"), un, pb)
        o_c = _oferta(t1, _curso("CURSO-CHARLIE"), un, pc)
        o_d = _oferta(t2, _curso("CURSO-DELTA"), un, pa, principal=True)
        o_e = _oferta(t2, _curso("CURSO-ECHO"), un, pa)
        o_f = _oferta(t2, _curso("CURSO-FOXTROT"), un, pb)

        alunos = {}
        for chave, oferta in (
            ("A", o_a), ("B", o_b), ("C", o_c), ("D", o_d),
            ("E", o_e), ("F", o_f),
        ):
            aluno = Aluno(
                nome=f"Aluno {chave}", unidade_id=un.id, ativo=True,
                data_nascimento=HOJE - timedelta(days=6000),
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, oferta.turma_id, oferta.id)
            alunos[chave] = aluno.id

        # Diário de Bordo distinto por oferta (mesma data-alvo).
        for chave, oferta in (
            ("A", o_a), ("B", o_b), ("C", o_c),
            ("D", o_d), ("E", o_e), ("F", o_f),
        ):
            db.session.add(RegistroAula(
                turma_id=oferta.turma_id, turma_curso_id=oferta.id,
                data=HOJE, atividades=f"DIARIO-{chave}",
                observacoes=f"OBS-{chave}", instrutor_id=pb.id,
                unidade_id=un.id,
            ))

        db.session.commit()
        return {
            "un": un.id, "t1": t1.id, "t2": t2.id,
            "pa": pa.id, "pb": pb.id, "pc": pc.id, "px": px.id,
            "admin": admin.id, "secre": secre.id, "ped": ped.id,
            "gerencia": gerencia.id, "social": social.id,
            "a": o_a.id, "b": o_b.id, "c": o_c.id,
            "d": o_d.id, "e": o_e.id, "f": o_f.id,
            "alunos": alunos,
        }


def _post_frequencia(client, turma_id, oferta_id, aluno_id):
    return client.post("/frequencia", data={
        "turma": str(turma_id),
        "turma_curso": str(oferta_id),
        "data": _iso(HOJE),
        f"aluno_{aluno_id}": "A",
    }, follow_redirects=False)


# ---------------------------------------------------------------------------
# GET /frequencia — leitura da pauta
# ---------------------------------------------------------------------------

def test_get_pauta_propria_ok(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/frequencia?turma_id={ids['t1']}&turma_curso={ids['a']}")
    assert r.status_code == 200
    assert "Aluno A" in r.get_data(as_text=True)


def test_get_pauta_alheia_403(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    for oferta in (ids["b"], ids["c"]):
        r = client.get(f"/frequencia?turma_id={ids['t1']}&turma_curso={oferta}")
        assert r.status_code == 403, oferta


def test_get_pauta_automatica_esconde_alheias(app, client):
    """pA tem 1 oferta em T1 → autoescopo; as ofertas alheias nem aparecem."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/frequencia?turma_id={ids['t1']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Aluno A" in html
    assert "Aluno B" not in html
    assert "Aluno C" not in html


def test_get_pauta_professor_com_duas_ofertas(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    # Escolha exigida entre D e E (as dele); F (alheia) não é ofertada.
    r = client.get(f"/frequencia?turma_id={ids['t2']}&turma_curso={ids['d']}")
    assert r.status_code == 200
    assert "Aluno D" in r.get_data(as_text=True)
    r2 = client.get(f"/frequencia?turma_id={ids['t2']}&turma_curso={ids['e']}")
    assert r2.status_code == 200
    r3 = client.get(f"/frequencia?turma_id={ids['t2']}&turma_curso={ids['f']}")
    assert r3.status_code == 403


# ---------------------------------------------------------------------------
# POST /frequencia — escrita (CRUD)
# ---------------------------------------------------------------------------

def test_post_escrita_propria_grava(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = _post_frequencia(client, ids["t1"], ids["a"], ids["alunos"]["A"])
    assert r.status_code == 302
    with app.app_context():
        assert Frequencia.query.filter_by(
            aluno_id=ids["alunos"]["A"], turma_curso_id=ids["a"], data=HOJE,
        ).count() == 1


def test_post_escrita_alheia_403_sem_gravar(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = _post_frequencia(client, ids["t1"], ids["b"], ids["alunos"]["B"])
    assert r.status_code == 403
    with app.app_context():
        assert Frequencia.query.filter_by(
            aluno_id=ids["alunos"]["B"], turma_curso_id=ids["b"], data=HOJE,
        ).count() == 0


def test_post_escrita_na_segunda_oferta_propria(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = _post_frequencia(client, ids["t2"], ids["e"], ids["alunos"]["E"])
    assert r.status_code == 302


# ---------------------------------------------------------------------------
# GET /turma/<id>/observacoes — Diário de Bordo
# ---------------------------------------------------------------------------

def test_diario_automatico_so_da_oferta_dele(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/turma/{ids['t1']}/observacoes")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "DIARIO-A" in html
    assert "DIARIO-B" not in html
    assert "DIARIO-C" not in html


def test_diario_oferta_alheia_403(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/turma/{ids['t1']}/observacoes?turma_curso={ids['b']}")
    assert r.status_code == 403


def test_diario_oferta_propria_ok(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/turma/{ids['t1']}/observacoes?turma_curso={ids['a']}")
    assert r.status_code == 200
    assert "DIARIO-A" in r.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Impressão e info-professor (já oferta-level — sem regressão)
# ---------------------------------------------------------------------------

def test_impressao_propria_ok_alheia_403(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r_ok = client.get(f"/turma/{ids['t1']}/imprimir-pauta?turma_curso={ids['a']}")
    assert r_ok.status_code == 200
    r_no = client.get(f"/turma/{ids['t1']}/imprimir-pauta?turma_curso={ids['b']}")
    assert r_no.status_code == 403


def test_info_professor_alheio_403(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/aluno/{ids['alunos']['B']}/info-professor")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Demais perfis: inalterados
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role_key", ["admin", "ped", "secre"])
def test_nao_professor_le_qualquer_oferta(app, client, role_key):
    ids = _setup(app)
    login_as(client, ids[role_key], ids["un"])
    r = client.get(f"/frequencia?turma_id={ids['t1']}&turma_curso={ids['b']}")
    assert r.status_code == 200
    r2 = client.get(f"/turma/{ids['t1']}/observacoes?turma_curso={ids['c']}")
    assert r2.status_code == 200


@pytest.mark.parametrize("role_key", ["gerencia", "social"])
def test_perfis_fora_da_pauta_403_papel(app, client, role_key):
    # Guardas de papel (role) permanecem: gerência e serviço social não entram
    # na rota de frequência (independentemente desta correção por oferta).
    ids = _setup(app)
    login_as(client, ids[role_key], ids["un"])
    r = client.get(f"/frequencia?turma_id={ids['t1']}&turma_curso={ids['a']}")
    assert r.status_code == 403


def test_secretaria_nao_escreve(app, client):
    ids = _setup(app)
    login_as(client, ids["secre"], ids["un"])
    r = _post_frequencia(client, ids["t1"], ids["b"], ids["alunos"]["B"])
    # Guardas anteriores: POST bloqueado para secretaria; nunca 200/gravado.
    assert r.status_code in (302, 403)


# ---------------------------------------------------------------------------
# Unidade e oferta inativa
# ---------------------------------------------------------------------------

def test_professor_de_outra_unidade_nao_alcancia(app, client):
    ids = _setup(app)
    login_as(client, ids["px"], ids["un"])  # unidade do pX é un2, mas sessão un
    # Mesmo forçando a unidade da sessão, pX não tem oferta na T1.
    r = client.get(f"/turma/{ids['t1']}/observacoes")
    assert r.status_code in (302, 403)


def test_oferta_inativa_nao_libera(app, client):
    ids = _setup(app)
    with app.app_context():
        inativa = db.session.get(TurmaCurso, ids["c"])
        inativa.ativo = False
        db.session.commit()
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/frequencia?turma_id={ids['t1']}&turma_curso={ids['c']}")
    assert r.status_code == 403
