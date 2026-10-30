# ruff: noqa: F811
"""V2 — caracterização ANTIGO × NOVO da regra de obrigatoriedade.

Com a implementação da regra (`_planejar_frequencia` em `logica.py`), os
mesmos cenários passam a ser pendência. O que muda, caso a caso:

    | cenário                                   | antes (A1)        | agora (V2)   |
    |-------------------------------------------|-------------------|--------------|
    | A/B/C/D sem valor, unidade com catálogo   | salva, valor NULL | recusa tudo  |
    | valor inativo novo, inexistente, externo  | salva, valor NULL | recusa tudo  |

"Recusa tudo" = nenhuma linha de `frequencia` e nenhuma linha de diário; a
mensagem da pauta lista os alunos pendentes. A exceção por unidade sem catálogo
ativo é coberta em `test_valor_obrigatorio.py`.
"""

import pytest

from _helpers import login_as
from test_valor_esportista_lancamento import (  # noqa: F401
    _cenario,
    _post,
    _valor_gravado,
)

from app.models import Frequencia


#: chave do cenário -> id enviado no campo `postura_aluno_<id>`.
VALORES_INVALIDOS = {
    "inativo": lambda ids: ids["inativo"],
    "de outra unidade": lambda ids: ids["externo"],
    "inexistente": lambda ids: 999999,
}


def _linhas(app):
    with app.app_context():
        return Frequencia.query.count()


def test_a_d_sem_valor_agora_e_pendencia(app, client):
    """ANTES: salvava ("A", None). AGORA: recusa e não grava."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])

    resposta = _post(client, ids, conceito="A", valor_id=None)

    assert resposta.status_code == 302
    assert _linhas(app) == 0
    assert _valor_gravado(app, ids) == (None, None)


@pytest.mark.parametrize("caso", list(VALORES_INVALIDOS))
def test_valor_invalido_agora_e_pendencia(app, client, caso):
    """ANTES: descartava o valor e salvava o conceito. AGORA: recusa."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])

    resposta = _post(client, ids, conceito="A", valor_id=VALORES_INVALIDOS[caso](ids))

    assert resposta.status_code == 302, caso
    assert _linhas(app) == 0, caso
    assert _valor_gravado(app, ids) == (None, None), caso
