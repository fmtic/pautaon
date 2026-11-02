# ruff: noqa: F811
"""AJ6-B2 — auditoria pós-AJ6-B da autorização do professor por OFERTA.

Cobre três frentes que a correção da AJ6-B deixou em aberto (itens 3, 4 e 5 do
pedido de auditoria), sempre com a mesma semente:

    - T1: ofertas A(pA), B(pB), C(pC)  — pA só leciona A.
    - T2: ofertas D(pA), E(pA), F(pB)  — pA leciona D e E (duas na MESMA turma).
    - pC não leciona nenhuma oferta de T2 (0 ofertas naquela turma).
    - Alunos sintéticos "Aluno A".."Aluno F", um por oferta; diário DIY-* por
      oferta. Nenhum dado real/nome de pessoa real: só rótulos sintéticos.

Item 3: a guarda FINAL do POST /frequencia é pulada quando `oferta_post` é
None (sem data). Prova de que, MESMO assim, nenhuma linha nasce com
`turma_curso_id` NULL numa turma com 2+ ofertas ativas — nem para quem tem 2
ofertas sem escolher, nem para quem tem 0 ofertas da turma.

Item 4: matriz pA/pB das rotas que faltavam confirmar — conselho (GET painel,
lançamento, salvar, fechamento), dashboard (`_entradas_professor` = "minhas
turmas"), export de conselho e a rota JSON `/api/alunos`.

Item 5: corpo HTML de `/turma/<id>` (ver_turma) verificado quanto a revelar ou
não alunos de oferta alheia ao professor (reportar; não corrigir).
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
from app.main.dashboard_professor import _entradas_professor
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    RegistroAula,
    Turma,
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
        name=nome, email=f"{nome.lower().replace(' ', '.')}@aj6b2.test",
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
        un = Unidade(nome="Unidade AJ6B2", ativo=True)
        db.session.add(un)
        db.session.flush()

        pa = _usuario("Professor Alfa", "professor", un.id)
        pb = _usuario("Professor Bravo", "professor", un.id)
        pc = _usuario("Professor Charlie", "professor", un.id)
        admin = _usuario("Admin AJ6B2", "admin", un.id)
        db.session.add_all([pa, pb, pc, admin])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P AJ6B2", data_inicio=HOJE - timedelta(days=40),
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

        t1 = _turma("Turma Um", pa)   # pA é o professor da TURMA (vestigial)
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
            ("A", o_a), ("B", o_b), ("C", o_c),
            ("D", o_d), ("E", o_e), ("F", o_f),
        ):
            aluno = Aluno(
                nome=f"Aluno {chave}", unidade_id=un.id, ativo=True,
                data_nascimento=HOJE - timedelta(days=6000),
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, oferta.turma_id, oferta.id)
            alunos[chave] = aluno.id

        for chave, oferta in (
            ("A", o_a), ("B", o_b), ("C", o_c),
            ("D", o_d), ("E", o_e), ("F", o_f),
        ):
            db.session.add(RegistroAula(
                turma_id=oferta.turma_id, turma_curso_id=oferta.id,
                data=HOJE, atividades=f"DIY-{chave}",
                observacoes=f"OBS-{chave}", instrutor_id=pb.id,
                unidade_id=un.id,
            ))

        db.session.commit()
        return {
            "un": un.id, "t1": t1.id, "t2": t2.id,
            "pa": pa.id, "pb": pb.id, "pc": pc.id, "admin": admin.id,
            "a": o_a.id, "b": o_b.id, "c": o_c.id,
            "d": o_d.id, "e": o_e.id, "f": o_f.id,
            "alunos": alunos,
        }


def _post_frequencia(client, turma_id, aluno_id, *, oferta_id=None, com_data=True):
    form = {
        "turma": str(turma_id),
        f"aluno_{aluno_id}": "A",
    }
    if oferta_id is not None:
        form["turma_curso"] = str(oferta_id)
    if com_data:
        form["data"] = _iso(HOJE)
    return client.post("/frequencia", data=form, follow_redirects=False)


def _freq_null_na_turma(app, turma_id):
    with app.app_context():
        return Frequencia.query.filter(
            Frequencia.turma_id == turma_id,
            Frequencia.turma_curso_id.is_(None),
        ).count()


# ===========================================================================
# ITEM 3 — a guarda FINAL pulada (sem oferta resolvida) nunca grava NULL
# ===========================================================================

def test_item3_post_duas_ofertas_sem_turma_curso_nao_grava_null(app, client):
    """pA tem 2 ofertas em T2; POST com data e SEM turma_curso → o resolver da
    rota levanta ValueError (2+ ativas sem escolha) e redireciona antes de
    qualquer escrita. Nada é gravado — muito menos com turma_curso_id NULL."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    antes = _freq_null_na_turma(app, ids["t2"])
    r = _post_frequencia(client, ids["t2"], ids["alunos"]["E"])  # sem oferta_id
    assert r.status_code == 302
    # Nenhuma linha de frequência em T2 (nem com oferta, nem NULL).
    with app.app_context():
        assert Frequencia.query.filter_by(turma_id=ids["t2"]).count() == 0
    assert _freq_null_na_turma(app, ids["t2"]) == 0
    assert antes == 0


def test_item3_post_zero_ofertas_da_turma_403_sem_gravar(app, client):
    """pC não leciona oferta alguma em T2 → a guarda de adesão nega 403 antes
    de qualquer escrita; nenhuma linha (NULL ou não) aparece em T2."""
    ids = _setup(app)
    login_as(client, ids["pc"], ids["un"])
    r = _post_frequencia(client, ids["t2"], ids["alunos"]["F"])
    assert r.status_code == 403
    with app.app_context():
        assert Frequencia.query.filter_by(turma_id=ids["t2"]).count() == 0
    assert _freq_null_na_turma(app, ids["t2"]) == 0


def test_item3_post_oferta_alheia_explicita_403_sem_gravar(app, client):
    """Âncora de reversão: POST explícito numa oferta que NÃO é do professor
    (B, de pB, em T1) → 403 da guarda final, sem gravar. Na base pré-AJ6-B
    isto ESCREVEIA na oferta alheia (o leak), então o teste falha lá."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = _post_frequencia(client, ids["t1"], ids["alunos"]["B"], oferta_id=ids["b"])
    assert r.status_code == 403
    with app.app_context():
        assert Frequencia.query.filter_by(
            aluno_id=ids["alunos"]["B"], turma_curso_id=ids["b"], data=HOJE,
        ).count() == 0


# ===========================================================================
# ITEM 4 — matriz pA/pB: conselho, dashboard, export e JSON
# ===========================================================================

def test_item4_conselho_painel_professor_ok(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get("/conselho")
    assert r.status_code == 200


@pytest.mark.parametrize(
    ("prof_key", "turma_key", "oferta_alheia_key"),
    [("pa", "t1", "b"), ("pa", "t1", "c"), ("pb", "t2", "d"), ("pb", "t2", "e")],
)
def test_item4_conselho_lancamento_oferta_alheia_403(app, client, prof_key, turma_key, oferta_alheia_key):
    ids = _setup(app)
    login_as(client, ids[prof_key], ids["un"])
    r = client.get(
        f"/conselho/lancamento?turma={ids[turma_key]}&oferta_sel={ids[oferta_alheia_key]}"
    )
    assert r.status_code == 403


@pytest.mark.parametrize(
    ("prof_key", "turma_key", "oferta_propria_key"),
    [("pa", "t1", "a"), ("pb", "t2", "f")],
)
def test_item4_conselho_lancamento_oferta_propria_nao_negada(app, client, prof_key, turma_key, oferta_propria_key):
    ids = _setup(app)
    login_as(client, ids[prof_key], ids["un"])
    r = client.get(
        f"/conselho/lancamento?turma={ids[turma_key]}&oferta_sel={ids[oferta_propria_key]}"
    )
    assert r.status_code != 403, "oferta própria do professor não pode ser negada"


def test_item4_conselho_salvar_oferta_alheia_403(app, client):
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["t1"]),
        "turma_curso_id": str(ids["b"]),   # oferta de pB
        "etapa": "inicial",
    }, follow_redirects=False)
    assert r.status_code == 403


def test_item4_conselho_fechamento_professor_403(app, client):
    """Fechamento é da secretaria/pedagogia: todo professor (pA e pB) toma 403
    independentemente da oferta (guarda de papel, não desta correção)."""
    ids = _setup(app)
    for prof_key in ("pa", "pb"):
        login_as(client, ids[prof_key], ids["un"])
        r = client.get(f"/conselho/fechamento/{ids['t1']}")
        assert r.status_code == 403, prof_key


def test_item4_dashboard_entradas_so_ofertas_do_professor(app):
    """`_entradas_professor` (minhas turmas) devolve apenas as OFERTAS ativas
    do professor — sem herdar `Turma.professor_id` em turma que tem ofertas."""
    ids = _setup(app)
    with app.app_context():
        pa_ids = {e["turma_curso_id"] for e in _entradas_professor(ids["pa"])}
        pb_ids = {e["turma_curso_id"] for e in _entradas_professor(ids["pb"])}
    assert pa_ids == {ids["a"], ids["d"], ids["e"]}
    # pB é o professor VESTIGIAL da T2 (Turma.professor_id), mas só leciona B e F.
    assert pb_ids == {ids["b"], ids["f"]}


def test_item4_api_alunos_json_professor_403(app, client):
    """Rota JSON: lista de papel exclui professor → 403 (não vaza a pauta)."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/api/alunos/{ids['t1']}")
    assert r.status_code == 403


def test_item4_conselho_imprimir_export_professor_403(app, client):
    """Export do conselho: papel restrito a pedagógico/admin/gerência → 403."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get("/conselho/imprimir?etapa=final&quantidade=5")
    assert r.status_code == 403


# ===========================================================================
# ITEM 5 — ver_turma: corpo revela alunos de oferta alheia? (reportar)
# ===========================================================================

def test_item5_ver_turma_corpo_markes_oferta_alheia(app, client):
    """pA passa na adesão (tem A em T1) e abre /turma/T1. O corpo é checado
    quanto aos alunos das ofertas ALHEIAS (B de pB, C de pC). Ajustado ao
    comportamento real observado; NÃO corrige nada — só documenta."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/turma/{ids['t1']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    proprio = "Aluno A" in html
    estrangeiro_b = "Aluno B" in html
    estrangeiro_c = "Aluno C" in html
    print(f"[AJ6B2 ver_turma] proprio(A)={proprio} alheio_B={estrangeiro_b} alheio_C={estrangeiro_c}")
    # O professor da oferta A abre a ficha da TURMA (adesao por turma, nao por
    # oferta) e o corpo elenca os alunos das OUTRAS ofertas (B, C). Este teste
    # CARACTERIZA o estado atual (SIM, vaza) para o operador decidir; nao
    # corrige. Se a fuga for sanada, a assercao abaixo passa a falhar e deve
    # ser invertida junto com a decisao.
    assert proprio is True
    assert estrangeiro_b is True
    assert estrangeiro_c is True
