# ruff: noqa: F811
"""AJ6-B4 — fechamento da série de autorização por oferta (itens 1, 2 e 3).

Mesma REGRA ÚNICA do ciclo (`ofertas_do_professor` /
`professor_pode_acessar_oferta`, em `app/services/aluno_info_professor.py`):
nenhuma predicação nova de acesso. Cobre os três vazamentos remanescentes,
sempre com a semente do AJ6-B2 (`_setup`) mais o extra do item 3:

    - Item 1 (`historico_aluno`): o professor só vê inscrições em OFERTAS dele;
      não expõe outras turmas/ofertas do aluno nem o nome de outro professor.
    - Item 2 (GET `/frequencia`, `exigir_escolha`): com 2+ ofertas próprias e
      nenhuma escolhida, o calendário (datas/meses) é zerado — nenhum link de
      pauta sai sem `turma_curso` (cairia em 403).
    - Item 3 (`ver_turma` / `detalhe.html`): com a oferta PRINCIPAL de outro
      professor, o "centro de custo compartilhado" é ocultado (nem "Não
      definido", que revelaria a oferta alheia).

Nomes sintéticos; SQLite em memória (fixture `app`); nenhuma escrita em banco
real. Matriz: pA vê só a oferta dele; aluno em A e B → pA não vê B nem pB;
admin vê tudo. Reversão em git worktree (caminhos absolutos).
"""

import re
from datetime import time

from _helpers import login_as, nova_inscricao, nova_oferta
from test_aj6b2_auditoria_ofertas import DIAS_TODOS, _setup

from app import db
from app.models import Aluno, Curso, PeriodoLetivo, Turma


def _aluno_em_duas_ofertas(app, ids, *, chave="X"):
    """Cria um aluno sintético inscrito em A (pA) e B (pB), ambas na T1."""
    with app.app_context():
        aluno = Aluno(nome=f"Aluno {chave}", unidade_id=ids["un"], ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, ids["t1"], ids["a"])
        nova_inscricao(aluno.id, ids["t1"], ids["b"])
        db.session.commit()
        return aluno.id


def _turma_principal_alheia(app, ids):
    """T3: oferta PRINCIPAL de pB (centro_custo 'CC-SECRETO') + oferta de pA
    (não principal). pA entra por adesão, mas a principal NÃO é dele."""
    with app.app_context():
        base = db.session.get(Turma, ids["t1"])
        periodo = db.session.get(PeriodoLetivo, base.periodo_letivo_id)
        t3 = Turma(
            nome="Turma Tres", unidade_id=ids["un"],
            periodo_letivo_id=periodo.id, professor_id=ids["pb"], ativo=True,
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
        )
        db.session.add(t3)
        db.session.flush()
        c_b = Curso(nome="CURSO-BRAVO-T3", unidade_id=ids["un"], ativo=True)
        c_a = Curso(nome="CURSO-ALFA-T3", unidade_id=ids["un"], ativo=True)
        db.session.add_all([c_b, c_a])
        db.session.flush()
        nova_oferta(
            t3.id, c_b.id, ids["un"], programa="Prog Bravo T3", principal=True,
            professor_id=ids["pb"], centro_custo="CC-SECRETO",
            dias_semana=DIAS_TODOS, hora_inicio=time(8), hora_fim=time(10),
        )
        de_pa = nova_oferta(
            t3.id, c_a.id, ids["un"], programa="Prog Alfa T3", principal=False,
            professor_id=ids["pa"], dias_semana=DIAS_TODOS,
            hora_inicio=time(8), hora_fim=time(10),
        )
        db.session.commit()
        return {"t3": t3.id, "de_pa": de_pa.id}


# ===========================================================================
# ITEM 1 — historico_aluno escopado por oferta
# ===========================================================================

def test_item1_professor_ve_soa_inscricao_na_oferta_dele(app, client):
    """pA leciona A (T1). O histórico do aluno mostra A; nunca B nem pB."""
    ids = _setup(app)
    xid = _aluno_em_duas_ofertas(app, ids)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/aluno/{xid}/historico")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "CURSO-ALFA" in html, "a oferta dele continua no histórico"
    assert "CURSO-BRAVO" not in html, "vaza oferta de outra turma/professor"
    assert "Professor Bravo" not in html, "vaza o nome de outro professor"


def test_item1_aluno_em_a_e_b_pa_nao_ve_b_nem_pb(app, client):
    """Aluno inscrito em A (pA) e B (pB): pA não vê a oferta B nem o professor
    Bravo (a lista de inscrições é filtrada por `ofertas_do_professor`)."""
    ids = _setup(app)
    xid = _aluno_em_duas_ofertas(app, ids)
    login_as(client, ids["pa"], ids["un"])
    html = client.get(f"/aluno/{xid}/historico").get_data(as_text=True)
    # Só uma oferta aparece (a dele); a de pB sai por completo.
    assert "Professor Alfa" in html
    assert "Professor Bravo" not in html
    assert html.count("CURSO-BRAVO") == 0


def test_item1_admin_ve_todas_as_inscricoes(app, client):
    """Perfil não-professor: saída inalterada — admin vê A e B (e os dois
    professores). É o contraponto que prova que o filtro só vale p/ professor."""
    ids = _setup(app)
    xid = _aluno_em_duas_ofertas(app, ids)
    login_as(client, ids["admin"], ids["un"])
    r = client.get(f"/aluno/{xid}/historico")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "CURSO-ALFA" in html and "CURSO-BRAVO" in html, "admin vê as duas"
    assert "Professor Alfa" in html and "Professor Bravo" in html


# ===========================================================================
# ITEM 2 — GET /frequencia com exigir_escolha: nenhum link sem turma_curso
# ===========================================================================

def test_item2_exigir_escolha_gera_zero_link_de_impressao(app, client):
    """pA tem D+E em T2 (2+ ofertas próprias, nenhuma escolhida). A página abre
    (200) pedindo a escolha do curso e NÃO gera nenhum link de pauta — todo
    link de impressão nasciria sem turma_curso e cairia em 403."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/frequencia?turma_id={ids['t2']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Selecione o curso" in html, "estado exigir_escolha"
    assert "Pauta de" not in html
    assert "imprimir-pauta" not in html, "nenhum link de pauta deve sair sem escolha"


def test_item2_exigir_escolha_zera_datas_e_meses(app, client):
    """Com exigir_escolha o calendário da turma (união de todas as ofertas,
    inclusive as que ele não leciona) é zerado: nenhum <option> de data sai."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    html = client.get(f"/frequencia?turma_id={ids['t2']}").get_data(as_text=True)
    # Nenhuma data ISO no seletor de "Data da Aula".
    assert "Nenhuma aula disponível" in html
    assert not re.search(r'<option value="\d{4}-\d{2}-\d{2}"', html), \
        "nenhuma data de oferta (própria ou alheia) pode aparecer sem escolha"


def test_item2_apos_escolher_oferta_calendario_voltou(app, client):
    """Escolhida uma oferta própria (D), a pauta reabre: o calendário da oferta
    aparece e todo link de pauta/impressão leva turma_curso (sem 403)."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/frequencia?turma_id={ids['t2']}&turma_curso={ids['d']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # Calendário da oferta D de volta: pelo menos uma data no seletor.
    assert re.search(r'<option value="\d{4}-\d{2}-\d{2}"', html), \
        "escolhida a oferta, o calendário da oferta reaparece"
    # Todo link de impressão leva o curso escolhido (nunca cai em 403).
    links = _links_imprimir(html)
    assert links, "com oferta escolhida a ficha oferece link de pauta"
    for link in links:
        assert "turma_curso" in link, link


def _links_imprimir(html):
    return re.findall(r'href="[^"]*imprimir-pauta[^"]*"', html)


# ===========================================================================
# ITEM 3 — ver_turma: centro de custo da oferta principal alheia
# ===========================================================================

def test_item3_professor_nao_ve_cc_de_oferta_principal_alheia(app, client):
    """T3: a oferta principal (centro de custo) é de pB; pA só leciona a outra.
    A ficha não pode mostrar 'CC-SECRETO' nem o rótulo 'Centro de custo
    compartilhado' (que revelaria a oferta principal de outro)."""
    ids = _setup(app)
    extra = _turma_principal_alheia(app, ids)
    login_as(client, ids["pa"], ids["un"])
    r = client.get(f"/turma/{extra['t3']}")
    assert r.status_code == 200, "pA tem oferta ativa na T3 → entra por adesão"
    html = r.get_data(as_text=True)
    assert "CC-SECRETO" not in html, "vaza centro de custo da oferta principal alheia"
    assert "Centro de custo compartilhado" not in html, \
        "oculta o campo inteiro (não apenas o valor)"


def test_item3_admin_ve_centro_de_custo_normal(app, client):
    """Perfil não-professor inalterado: admin vê o 'Centro de custo
    compartilhado' com o valor da oferta principal."""
    ids = _setup(app)
    extra = _turma_principal_alheia(app, ids)
    login_as(client, ids["admin"], ids["un"])
    r = client.get(f"/turma/{extra['t3']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Centro de custo compartilhado" in html
    assert "CC-SECRETO" in html, "admin vê o centro de custo da principal"
