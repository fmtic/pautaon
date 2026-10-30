# ruff: noqa: F811
"""Solução B — `/professor/painel` unificada na rota canônica `main.painel`.

A rota legada (`registros.painel_professor`) renderizava
`dashboard/professor.html` com um contexto próprio (`turmas`, `total_alunos`,
`lista_programas`, `programa_ativo`, `is_readonly`) que o template não consome
todo: faltavam `entradas`, `aulas_pendentes` e `dias_bloqueados`, e o painel
abria com "Minhas Turmas" vazia. A montagem duplicada foi removida e a view
agora é só o redirect.

Coberto aqui:
    - A URL legada responde 302 para `/painel` em qualquer perfil autenticado
      (professor, admin) e continua protegida por login.
    - O professor que chega por ela vem pelo painel COMPLETO — a linha da sua
      oferta aparece, sem o estado vazio "Nenhuma turma vinculada".
    - O painel gerencial (Painel Geral) não aponta mais para a rota legada: o
      card "Abrir pauta" leva direto à pauta (`/frequencia`).
"""

from _helpers import login_as
from test_conselho_professor import _setup


def _corpo(response):
    return response.get_data(as_text=True)


def test_rota_legada_leva_o_professor_ao_painel_completo(client, app):
    """O link antigo do professor cai no painel com `entradas` montadas."""
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    resposta = client.get("/professor/painel")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/painel")

    corpo = _corpo(client.get("/professor/painel", follow_redirects=True))
    # A oferta do professor aparece (o "Turma — Curso" da linha); o estado
    # vazio da época da rota legada não.
    assert "Turma X — Curso X" in corpo
    assert "Nenhuma turma vinculada" not in corpo
    assert "Meus Alunos" in corpo


def test_rota_legada_devolve_o_painel_do_perfil_ao_gestor(client, app):
    """Admin/pedagógico/secretaria não veem mais o template do professor.

    A rota legada os atendia com uma montagem própria (todas as turmas ativas
    da unidade); o destino canônico roteia por perfil e o gerencial deles é o
    Painel Geral — sem o card "Meus Alunos" do painel do professor.
    """
    ids = _setup(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = client.get("/professor/painel")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/painel")

    corpo = _corpo(client.get("/professor/painel", follow_redirects=True))
    assert "Meus Alunos" not in corpo
    assert "Períodos Ativos" in corpo


def test_rota_legada_continua_exigindo_login(client):
    """Sem sessão a rota não renderiza nada: `login_required` desvia para /login."""
    resposta = client.get("/professor/painel")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_painel_geral_aponta_a_pauta_para_a_rota_de_frequencia(client, app):
    """Último link interno para a rota legada: o card "Abrir pauta"."""
    ids = _setup(app)
    login_as(client, ids["admin"], ids["un"])

    corpo = _corpo(client.get("/painel"))
    assert "Abrir pauta" in corpo
    assert "/professor/painel" not in corpo
    assert 'href="/frequencia"' in corpo
