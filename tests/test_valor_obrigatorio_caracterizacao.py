# ruff: noqa: F811
"""V2 — caracterização do comportamento ANTES da regra de obrigatoriedade.

Esta é a "linha de base" pedida na P2: fixa o que a pauta faz **hoje** (branch
`nova_feature`, HEAD `26c52e4`) para que a inversão da regra seja uma mudança
explícita e verificável, não um efeito colateral.

Estado atual (a ser invertido na implementação):

    - conceito A/B/C/D sem valor: o conceito é salvo e o valor fica NULL;
    - valor inativo novo, inexistente ou de outra unidade: descartado em
      silêncio, mas o conceito é salvo normalmente.

Depois da regra, os dois casos passam a ser PENDÊNCIA: nada é gravado e a
pauta mostra a mensagem com os alunos pendentes.
"""

import pytest

from _helpers import login_as
from test_conselho_oferta import app, client  # noqa: F401
from test_valor_esportista_lancamento import (  # noqa: F401
    _cenario,
    _post,
    _valor_gravado,
)


#: chave do cenário -> id enviado no campo `postura_aluno_<id>`.
VALORES_INVALIDOS = {
    "inativo": lambda ids: ids["inativo"],
    "de outra unidade": lambda ids: ids["externo"],
    "inexistente": lambda ids: 999999,
}


def test_caracterizacao_a_d_sem_valor_salva_hoje(app, client):
    """A–D sem valor: o conceito entra e o valor fica NULL (comportamento antigo)."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])

    resposta = _post(client, ids, conceito="A", valor_id=None)

    assert resposta.status_code == 302
    assert _valor_gravado(app, ids) == ("A", None)


@pytest.mark.parametrize("caso", list(VALORES_INVALIDOS))
def test_caracterizacao_valor_invalido_descarta_e_salva_conceito(app, client, caso):
    """Valor inativo/inexistente/de outra unidade: descartado, conceito salvo."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])

    resposta = _post(client, ids, conceito="A", valor_id=VALORES_INVALIDOS[caso](ids))

    assert resposta.status_code == 302, caso
    assert _valor_gravado(app, ids) == ("A", None), caso
