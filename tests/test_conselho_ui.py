"""ETAPA D5.2b — telas de conselho operáveis no navegador.

Os testes da D5.2 rodam com CSRF desligado e postam direto nas rotas; os
quatro defeitos de tela (grade de lançamento ausente, modal inerte, POST do
fechamento sem token e select de situação fora do enum) só aparecem no
navegador. Este arquivo cobre exatamente essas quatro frentes.

Um usuário por teste: cada teste semeia o próprio cenário via `_setup` e
realiza um único login.
"""

import re

from test_conselho_oferta import (  # noqa: F401  (fixtures reaproveitadas)
    _enturma,
    _loga,
    _perguntas,
    _setup,
    app,
    client,
)

from app.models import ConselhoResposta
from app.models.enums import SituacaoFinal


def _token_csrf(html: str) -> str:
    """Extrai o token do <meta name="csrf-token"> exposto pelo base.html."""
    encontrado = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert encontrado, "base.html deveria expor o meta csrf-token"
    return encontrado.group(1)


# ---------------------------------------------------------------------------
# (a) CSRF no POST do fechamento
# ---------------------------------------------------------------------------

def test_fechamento_exige_csrf_e_aceita_com_token(app, client):  # noqa: F811
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    _loga(client, ids, unidade_id=ids["un_a"])

    payload = {
        "oferta_id": ids["ofertas"][0],
        "dados": [
            {"aluno_id": ids["aluno_a"], "situacao": "Aprovado",
             "proxima_turma_id": None},
        ],
    }
    url = f"/conselho/fechamento/{ids['turma']}/salvar"

    app.config["WTF_CSRF_ENABLED"] = True
    try:
        # Sem o cabeçalho X-CSRFToken o CSRFProtect barra antes da rota.
        r = client.post(url, json=payload)
        assert r.status_code == 400

        # A página do fechamento entrega o token pelo meta do base.html.
        pagina = client.get(f"/conselho/fechamento/{ids['turma']}")
        assert pagina.status_code == 200
        token = _token_csrf(pagina.data.decode("utf-8"))

        r = client.post(url, json=payload, headers={"X-CSRFToken": token})
        assert r.status_code == 200
        assert r.get_json()["success"] is True
    finally:
        app.config["WTF_CSRF_ENABLED"] = False


# ---------------------------------------------------------------------------
# (b) Grade do lançamento: aluno × pergunta tipo ALUNO, ida e volta
# ---------------------------------------------------------------------------

def test_grade_lancamento_so_aluno_e_ida_volta(app, client):  # noqa: F811
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    _enturma(app, ids, "aluno_b")
    p_aluno, p_turma = _perguntas(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    assert r.status_code == 200
    body = r.data.decode("utf-8")

    # Um input por aluno × pergunta tipo ALUNO, com o nome que a rota lê.
    for chave in ("aluno_a", "aluno_b"):
        assert f'name="resp_{ids[chave]}_{p_aluno}"' in body
    assert body.count('name="resp_') == 2

    # Pergunta tipo TURMA não aparece na grade (é a avaliação da oferta).
    assert f'name="resp_{ids["aluno_a"]}_{p_turma}"' not in body
    assert 'name="resp_turma_' not in body

    # POST com exatamente os campos que o GET gerou.
    form = {
        "turma_id": ids["turma"],
        "etapa": "INICIAL",
        "turma_curso_id": ids["ofertas"][0],
        f"resp_{ids['aluno_a']}_{p_aluno}": "Participa bem",
        f"resp_{ids['aluno_b']}_{p_aluno}": "Precisa de apoio",
    }
    r = client.post("/conselho/salvar", data=form)
    assert r.status_code == 302

    with app.app_context():
        gravadas = {resp.resposta for resp in ConselhoResposta.query.all()}
        assert gravadas == {"Participa bem", "Precisa de apoio"}

    # Reabre a grade: as respostas voltam pré-preenchidas.
    r = client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    body = r.data.decode("utf-8")
    assert "Participa bem" in body
    assert "Precisa de apoio" in body


# ---------------------------------------------------------------------------
# (c) Select de situação final = exatamente os valores do enum
# ---------------------------------------------------------------------------

def test_select_situacao_final_igual_ao_enum(app, client):  # noqa: F811
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(f"/conselho/fechamento/{ids['turma']}")
    assert r.status_code == 200
    body = r.data.decode("utf-8")

    inicio = body.index("situacao-select")
    trecho = body[inicio:body.index("</select>", inicio)]
    valores = re.findall(r'value="([^"]*)"', trecho)

    assert valores == [situacao.value for situacao in SituacaoFinal]
    assert "EMPREGADO" not in body


# ---------------------------------------------------------------------------
# (d) detalhe.html: modal morto removido e link para a avaliação da oferta
# ---------------------------------------------------------------------------

def test_detalhe_sem_modal_morto_e_com_link_da_oferta(app, client):  # noqa: F811
    ids = _setup(app, ofertas=2)
    _loga(client, ids, unidade_id=ids["un_a"])
    oferta_id = ids["ofertas"][1]

    r = client.get(f"/turma/{ids['turma']}?oferta_sel={oferta_id}")
    assert r.status_code == 200
    body = r.data.decode("utf-8")

    # O formulário do modal (que postava campos ignotos) não existe mais.
    assert 'id="modalConselho"' not in body
    assert 'id="inputOfertaConselho"' not in body
    assert 'action="/conselho/salvar"' not in body

    # A avaliação coletiva é alcançável pelo link da OFERTA em uso.
    assert f"/turma/{ids['turma']}/avaliacao?oferta_sel={oferta_id}" in body
