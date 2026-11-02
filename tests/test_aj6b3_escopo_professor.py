# ruff: noqa: F811
"""AJ6-B3 — escopo de OFERTA na ficha da turma e no dashboard do professor.

Decisões do responsável (2026-11-02):

  (1) `ver_turma`: a **régua de entrada** continua sendo a adesão — o professor
      entra na turma onde leciona alguma oferta ativa. O que muda é o
      **payload/HTML**: ficam restritos às ofertas dele. A regra reaproveitada é
      a única que existe (`professor_pode_acessar_oferta` / `ofertas_do_professor`
      em `services/aluno_info_professor.py`), sem duplicá-la na rota.
  (2) "Professor da turma" não existe: cai o fallback `Turma.professor_id` do
      dashboard (`app/main/dashboard_professor.py`).

Semente emprestada da AJ6-B2 (mesma malha, nomes sintéticos):

    - T1: A(pA, principal), B(pB), C(pC)   — pA só leciona A.
    - T2: D(pA, principal), E(pA), F(pB)   — pA leciona D e E; pB só F.
    - pC não leciona nada em T2 (0 ofertas naquela turma).

O teste de snapshot dos perfis não-professor vive em
`test_aj6b3_snapshot_nao_professor.py` (compara a estrutura sem classes
ANTES/DEPOIS para admin/pedagógico/secretaria/gerência/serviço social).
"""

from datetime import timedelta

import pytest
from _helpers import dia_de_aula_ate, hoje_ref, login_as
from test_aj6b2_auditoria_ofertas import _setup

from app import db
from app.main.dashboard_professor import _entradas_professor
from app.models import Turma

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())


def _abrir(client, turma_key, ids):
    r = client.get(f"/turma/{ids[turma_key]}")
    return r, r.get_data(as_text=True)


# ===========================================================================
# ITEM 1 — ver_turma: payload/HTML do professor só com as ofertas dele
# ===========================================================================

def test_b3_pA_em_T1_ve_so_a_oferta_dele(app, client):
    """pA (só oferta A em T1): entra (régua de entrada inalterada) e o corpo
    mostra A; os alunos, os cards e os links de B (pB) e C (pC) não saem."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r, html = _abrir(client, "t1", ids)
    assert r.status_code == 200, "a adesão por oferta continua liberando a entrada"
    assert "Aluno A" in html
    for chave, aluno in (("b", "Aluno B"), ("c", "Aluno C")):
        assert aluno not in html, f"vaza {aluno} (oferta alheia {chave})"
        assert f"detalhes-oferta-{ids[chave]}" not in html, f"vaza o card da oferta {chave}"
        assert f"turma_curso={ids[chave]}" not in html, f"vaza link de pauta/Diário da oferta {chave}"


def test_b3_pB_em_T2_ve_so_a_oferta_dele(app, client):
    """Inversão: pB leciona só F em T2 (e é o professor VESTIGIAL da T2)."""
    ids = _setup(app)
    login_as(client, ids["pb"], ids["un"])
    r, html = _abrir(client, "t2", ids)
    assert r.status_code == 200
    assert "Aluno F" in html
    for chave in ("d", "e"):
        assert f"detalhes-oferta-{ids[chave]}" not in html
        assert f"turma_curso={ids[chave]}" not in html


def test_b3_pA_em_T2_ve_as_suas_duas_ofertas_e_nao_F(app, client):
    """pA tem D e E em T2: as duas aparecem, F (de pB) não — inclusive quando
    ele seleciona uma das suas com ?oferta_sel=."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r, html = _abrir(client, "t2", ids)
    assert r.status_code == 200
    assert f"detalhes-oferta-{ids['d']}" in html
    assert f"detalhes-oferta-{ids['e']}" in html
    assert "Aluno D" in html and "Aluno E" in html
    assert "Aluno F" not in html
    assert f"detalhes-oferta-{ids['f']}" not in html

    r2 = client.get(f"/turma/{ids['t2']}?oferta_sel={ids['d']}")
    html2 = r2.get_data(as_text=True)
    assert r2.status_code == 200
    assert "Aluno F" not in html2
    assert f"detalhes-oferta-{ids['f']}" not in html2


def test_b3_pB_em_T1_ve_so_B(app, client):
    """pB em T1: vê B (a dele) e não A (pA) nem C (pC)."""
    ids = _setup(app)
    login_as(client, ids["pb"], ids["un"])
    r, html = _abrir(client, "t1", ids)
    assert r.status_code == 200
    assert "Aluno B" in html
    for aluno in ("Aluno A", "Aluno C"):
        assert aluno not in html


def test_b3_pC_em_T1_ve_so_C(app, client):
    """pC em T1: vê C (a dele) e não A nem B."""
    ids = _setup(app)
    login_as(client, ids["pc"], ids["un"])
    r, html = _abrir(client, "t1", ids)
    assert r.status_code == 200
    assert "Aluno C" in html
    for aluno in ("Aluno A", "Aluno B"):
        assert aluno not in html


def test_b3_professor_sem_oferta_na_turma_403(app, client):
    """Régua de entrada (inalterada): pC leciona C em T1, mas nada em T2 → 403,
    sem qualquer nome de aluno no corpo."""
    ids = _setup(app)
    login_as(client, ids["pc"], ids["un"])
    r, html = _abrir(client, "t2", ids)
    assert r.status_code == 403
    for aluno in ("Aluno D", "Aluno E", "Aluno F"):
        assert aluno not in html


def test_b3_admin_ve_todas_as_ofertas_e_alunos(app, client):
    """Perfil admin: nada é escopado — todas as ofertas e alunos aparecem."""
    ids = _setup(app)
    login_as(client, ids["admin"], ids["un"])
    r, html = _abrir(client, "t1", ids)
    assert r.status_code == 200
    for chave in ("a", "b", "c"):
        assert f"detalhes-oferta-{ids[chave]}" in html
    for aluno in ("Aluno A", "Aluno B", "Aluno C"):
        assert aluno in html


def test_b3_detalhe_do_professor_sem_oferta_alheia(app, client):
    """Nada de nome de curso, DIÁRIO ou tema de oferta alheia no corpo."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r, html = _abrir(client, "t1", ids)
    assert r.status_code == 200
    assert "CURSO-ALFA" in html
    for curso_alheio in ("CURSO-BRAVO", "CURSO-CHARLIE"):
        assert curso_alheio not in html, f"vaza o curso {curso_alheio}"
    for diario_alheio in ("DIY-B", "DIY-C"):
        assert diario_alheio not in html


def test_b3_links_de_conselho_do_professor_nao_apontam_para_oferta_alheia(app, client):
    """O dropdown CONSELHO DE CLASSE monta `oferta_sel=<id>` a partir da oferta
    resolvida na página: para o professor só pode sair uma oferta dele."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r, html = _abrir(client, "t1", ids)
    assert r.status_code == 200
    for chave in ("b", "c"):
        assert f"oferta_sel={ids[chave]}" not in html, f"link de conselho para a oferta {chave}"
    assert f"oferta_sel={ids['a']}" in html


# ===========================================================================
# ITEM 3 — dashboard: sem fallback Turma.professor_id
# ===========================================================================

def _turma_sem_oferta(app, ids, nome, professor_id):
    """Cria turma ATIVA sem oferta alguma, com Turma.professor_id preenchido."""
    with app.app_context():
        periodo = db.session.get(Turma, ids["t1"]).periodo_letivo
        legada = Turma(
            nome=nome, unidade_id=ids["un"], periodo_letivo_id=periodo.id,
            professor_id=professor_id, ativo=True,
            data_inicio=HOJE - timedelta(days=30), data_fim=HOJE + timedelta(days=30),
        )
        db.session.add(legada)
        db.session.commit()
        return legada.id


def test_b3_dashboard_nao_mostra_turma_sem_oferta_mesmo_sendo_professor_dela(app):
    """Decisão (2): turma sem oferta ativa com `Turma.professor_id = pA` NÃO
    entra no dashboard de pA. O ramo legado (fallback) foi removido."""
    ids = _setup(app)
    legada = _turma_sem_oferta(app, ids, "Turma Legada Sem Oferta", ids["pa"])
    with app.app_context():
        entradas = _entradas_professor(ids["pa"])
    turmas_no_dashboard = {e["turma"].id for e in entradas}
    assert legada not in turmas_no_dashboard
    assert all(e["oferta"] is not None for e in entradas), "entrada sem oferta = legado"
    # as ofertas reais dele continuam entrando
    assert {e["turma_curso_id"] for e in entradas} == {ids["a"], ids["d"], ids["e"]}


def test_b3_dashboard_entrada_do_professor_bate_com_suas_ofertas(app):
    """Sem o fallback, o dashboard é exatamente o conjunto de ofertas ativas do
    professor (pB: só B e F — nem a turma vestigial T2 entra por ser `Turma`)."""
    ids = _setup(app)
    with app.app_context():
        pb = _entradas_professor(ids["pb"])
    assert {e["turma_curso_id"] for e in pb} == {ids["b"], ids["f"]}
    assert {e["turma"].id for e in pb} == {ids["t1"], ids["t2"]}
