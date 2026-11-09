# ruff: noqa: F811
"""AJ16-B — caracterização ANTIGO (A1/V2) × NOVO (valor na aula).

O valor deixou de ser um FK opcional por aluno em `frequencia` e passou a ser
um conjunto da AULA (oferta + data), validado antes de qualquer escrita. O que
muda, caso a caso:

    | cenário                                        | antes (A1/V2)     | agora |
    |------------------------------------------------|-------------------|-------|
    | A/B/C/D sem valor, unidade com catálogo        | recusa (V2)       | recusa|
    | valor inativo novo, inexistente, externo       | recusa (V2)       | recusa|
    | valor válido + conceito A–D                    | 1 valor por aluno | conjunto da aula |
    | F/J sem valor, aula com valor já selecionado   | limpa por aluno   | preserva |

A diferença estrutural central: não existe mais `frequencia.valor_esportista_id`
nem `postura_aluno_<id>`; o único caminho é `valor_ids` (repetido) → N:N em
`RegistroAula.valores`. "Recusa" = nada gravado (frequência, diário e vínculos)
e mensagem única na pauta.
"""

import pytest

from _helpers import login_as
from _valor_aula import cenario, contagens, linha, post, valores_da_aula

from app.models import Frequencia


def _conceitos(app):
    with app.app_context():
        return [
            linha.conceito for linha in Frequencia.query.order_by(Frequencia.id)
        ]


def test_antes_salvava_presenca_sem_valor_agora_recusa(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(client, ids, {ids["aluno"]: "A"}, [])

    assert resposta.status_code == 302
    assert contagens(app) == (0, 0, 0)
    assert _conceitos(app) == []


@pytest.mark.parametrize("origem", ["inativo_novo", "inexistente", "outra_unidade"])
def test_antes_descartava_valor_invalido_agora_recusa(app, client, origem):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    valor_id = {
        "inativo_novo": ids["valores"]["inativo"],
        "inexistente": 999999,
        "outra_unidade": ids["valores"]["externo"],
    }[origem]

    resposta = post(client, ids, {ids["aluno"]: "A"}, [valor_id])

    assert resposta.status_code == 302, origem
    assert contagens(app) == (0, 0, 0), origem
    assert _conceitos(app) == [], origem


def test_agora_o_valor_e_da_aula_e_nao_do_aluno(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(
        client, ids, {ids["aluno"]: "A"},
        [ids["valores"]["ativo"], ids["valores"]["outro"]],
    )

    assert valores_da_aula(app, ids) == sorted(
        [ids["valores"]["ativo"], ids["valores"]["outro"]]
    )
    # A linha de frequência não guarda mais o valor.
    assert not hasattr(linha(app, ids["aluno"]), "valor_esportista_id")


def test_agora_f_j_nao_limpam_o_conjunto_da_aula(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    post(client, ids, {ids["aluno"]: "F"}, [ids["valores"]["ativo"]])

    assert _conceitos(app) == ["F"]
    assert valores_da_aula(app, ids) == [ids["valores"]["ativo"]]
