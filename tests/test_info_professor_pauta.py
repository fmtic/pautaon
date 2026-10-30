# ruff: noqa: F811
"""I1 — ícone "Informações do aluno" na pauta de frequência.

Só para PROFESSOR e só para aluno com inscrição qualificada **e** ao menos um
bloco preenchido. A pauta NÃO carrega os textos: apenas `data-aluno-id` no
ícone (o modal busca `/aluno/<id>/info-professor`).

O JavaScript é verificado aqui também: renderiza por `textContent` (nunca
`.innerHTML`) e preserva quebras de linha com `white-space: pre-wrap`.
"""

from pathlib import Path

from _helpers import login_as
from _i1_helpers import dois_blocos, mais_alunos, pauta, seed

from app import db

RAIZ = Path(__file__).resolve().parents[1]


def test_pauta_traz_icone_sem_os_textos(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["prof"], ids["un"])

    resposta = pauta(client, ids)
    corpo = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
    assert "btn-info-professor" in corpo
    assert "bi bi-chat-left-dots-fill" in corpo
    assert f'data-aluno-id="{ids["aluno"]}"' in corpo
    # Textos do aluno nunca vão no HTML da pauta.
    assert "Mãe" not in corpo
    assert "Usa óculos e precisa de lugar na frente." not in corpo
    assert "Quem acompanha" not in corpo


def test_pauta_sem_icone_para_outros_perfis(app, client):
    ids = seed(app)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["admin"], ids["un"])

    corpo = pauta(client, ids).get_data(as_text=True)

    assert "btn-info-professor" not in corpo
    assert "data-aluno-id" not in corpo
    assert "modal-info-professor" not in corpo


def test_pauta_sem_icone_quando_nao_ha_blocos(app, client):
    ids = seed(app)
    login_as(client, ids["prof"], ids["un"])

    corpo = pauta(client, ids).get_data(as_text=True)

    assert "btn-info-professor" not in corpo


def test_pauta_sem_icone_para_professor_sem_acesso(app, client):
    """Período encerrado: o professor vê a turma, mas não a informação."""
    ids = seed(app, dias_inicio=-60, dias_fim=-1)
    dois_blocos(app, ids["aluno"])
    login_as(client, ids["prof"], ids["un"])

    corpo = pauta(client, ids).get_data(as_text=True)

    assert "btn-info-professor" not in corpo


def test_js_renderiza_texto_sem_innerhtml():
    js = (RAIZ / "app" / "static" / "js" / "aluno_info_professor.js").read_text(
        encoding="utf-8",
    )

    assert "textContent" in js
    assert ".innerHTML" not in js
    assert "white-space" in js
    assert "/aluno/${alunoId}/info-professor" in js
    assert "Informações para o professor — " in js


# ---------------------------------------------------------------------------
# N+1: o número de SELECTs da pauta não cresce com o número de alunos
# ---------------------------------------------------------------------------

def _contar_selects(client, ids):
    from sqlalchemy import event

    consultas = []

    def _conta(_conn, _cursor, statement, _params, _context, _executemany):
        consultas.append(statement)

    event.listen(db.engine, "before_cursor_execute", _conta)
    try:
        resposta = pauta(client, ids)
    finally:
        event.remove(db.engine, "before_cursor_execute", _conta)
    assert resposta.status_code == 200
    return len(consultas)


def test_selects_constantes_com_3_e_15_alunos(app, client):
    ids = seed(app, alunos=3)
    for aluno_id in ids["alunos"]:
        dois_blocos(app, aluno_id)
    login_as(client, ids["prof"], ids["un"])
    pauta(client, ids)  # aquece caches de sessão/template
    com_3 = _contar_selects(client, ids)

    for aluno_id in mais_alunos(app, ids, 12):
        dois_blocos(app, aluno_id)
    com_15 = _contar_selects(client, ids)

    assert com_3 == com_15
