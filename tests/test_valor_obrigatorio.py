# ruff: noqa: F811
"""AJ16-B — obrigatoriedade do Valor do Esportista é da AULA (não do aluno).

Regra:
    1. Ao salvar a pauta, se ao menos um aluno tem conceito A/B/C/D e a
       unidade tem catálogo ativo, a aula exige ao menos um valor trabalhado.
    2. F, J e aula sem presença não exigem valor — e não limpam o conjunto já
       selecionado.
    3. Unidade sem nenhum valor ativo fica isenta (a pauta não pode travar).
    4. Valor inativo já vinculado continua válido; inativo novo, inexistente ou
       de outra unidade recusa a gravação inteira.
    5. Servidor valida tudo antes de gravar: havendo pendência, NADA é gravado
       (nem conceitos, nem diário, nem valores) e a mensagem é sempre a mesma.

A tela (checkbox da aula, bloqueio no submit, aviso de cadastro) é coberta em
`test_valor_obrigatorio_ui.py`.
"""

import pytest

from _helpers import login_as
from _valor_aula import (
    cenario,
    contagens,
    corpo_pauta,
    definir_valores,
    linha,
    post,
    valores_da_aula,
)

from app import db
from app.models import Inscricao, User

PRESENCA = ["A", "B", "C", "D"]
MENSAGEM = "Selecione ao menos um valor trabalhado na aula. Nada foi salvo."


def _pauta_impressa(client, ids):
    resposta = client.get(f"/turma/{ids['turma']}/imprimir-pauta")
    assert resposta.status_code == 200
    return resposta.get_data(as_text=True)


@pytest.mark.parametrize("conceito", PRESENCA)
def test_presenca_sem_valor_recusa_e_nao_grava_nada(app, client, conceito):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(
        client, ids, {ids["aluno"]: conceito}, [],
        extras={"observacoes": "não deve gravar", "atividades": "nem isto"},
    )

    assert resposta.status_code == 302
    assert contagens(app) == (0, 0, 0)
    assert MENSAGEM in corpo_pauta(client, ids)


@pytest.mark.parametrize("conceito", PRESENCA)
def test_presenca_com_valor_grava_conceito_valor_e_diario(app, client, conceito):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(
        client, ids, {ids["aluno"]: conceito}, [ids["valores"]["ativo"]],
        extras={"observacoes": "gravou", "atividades": "gravou também"},
    )

    assert resposta.status_code == 302
    assert linha(app, ids["aluno"]).conceito == conceito
    assert valores_da_aula(app, ids) == [ids["valores"]["ativo"]]
    assert contagens(app) == (1, 1, 1)
    with app.app_context():
        from app.models import RegistroAula

        diario = RegistroAula.query.one()
        assert diario.observacoes == "gravou"
        assert diario.atividades == "gravou também"


@pytest.mark.parametrize("conceito", ["F", "J"])
def test_falta_e_justificada_nao_exigem_valor(app, client, conceito):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(client, ids, {ids["aluno"]: conceito}, [])

    assert resposta.status_code == 302
    assert linha(app, ids["aluno"]).conceito == conceito
    assert valores_da_aula(app, ids) == []
    assert MENSAGEM not in corpo_pauta(client, ids)


@pytest.mark.parametrize("conceito", ["F", "J"])
def test_falta_e_justificada_preservam_valor_ja_selecionado(app, client, conceito):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    post(client, ids, {ids["aluno"]: conceito}, [ids["valores"]["ativo"]])

    assert valores_da_aula(app, ids) == [ids["valores"]["ativo"]]


@pytest.mark.parametrize("conceito", PRESENCA)
def test_unidade_sem_valores_ativos_isenta_a_regra(app, client, conceito):
    ids = cenario(app, com_valores=False)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(client, ids, {ids["aluno"]: conceito}, [])

    assert resposta.status_code == 302
    assert linha(app, ids["aluno"]).conceito == conceito
    assert valores_da_aula(app, ids) == []
    assert MENSAGEM not in corpo_pauta(client, ids)


def test_valor_inativo_ja_vinculado_continua_valendo(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])
    definir_valores(app, ids, [ids["valores"]["inativo"]])

    resposta = post(
        client, ids, {ids["aluno"]: "A"}, [ids["valores"]["inativo"]],
    )

    assert resposta.status_code == 302
    assert linha(app, ids["aluno"]).conceito == "A"
    assert valores_da_aula(app, ids) == [ids["valores"]["inativo"]]


@pytest.mark.parametrize("origem", ["inativo_novo", "inexistente", "outra_unidade"])
def test_valor_sem_validade_recusa_tudo(app, client, origem):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    valor_id = {
        "inativo_novo": ids["valores"]["inativo"],
        "inexistente": 999999,
        "outra_unidade": ids["valores"]["externo"],
    }[origem]

    resposta = post(client, ids, {ids["aluno"]: "A"}, [valor_id])

    assert resposta.status_code == 302
    assert contagens(app) == (0, 0, 0)
    corpo = corpo_pauta(client, ids)
    assert "Nada foi salvo." in corpo
    assert MENSAGEM not in corpo


def test_mensagem_e_unica_e_nao_lista_alunos(app, client):
    ids = cenario(app, alunos=12)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {aluno: "A" for aluno in ids["alunos"]}, [])

    corpo = corpo_pauta(client, ids)
    assert MENSAGEM in corpo
    # A mensagem é única: não existe mais a lista "Alunos pendentes: ...".
    assert "Alunos pendentes:" not in corpo
    assert contagens(app) == (0, 0, 0)


def test_duas_ofertas_pendencia_na_oferta_do_formulario(app, client):
    ids = cenario(app, ofertas=2)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(
        client, ids, {ids["aluno"]: "A"}, [],
        extras={"turma_curso": str(ids["ofertas"][1])},
    )

    assert resposta.status_code == 302
    assert contagens(app) == (0, 0, 0)
    assert MENSAGEM in corpo_pauta(client, ids, ids["ofertas"][1])


def test_duas_ofertas_valida_so_alunos_da_oferta_do_formulario(app, client):
    ids = cenario(app, alunos=2, ofertas=2)
    login_as(client, ids["admin"], ids["un"])

    # Aluno 1 sai da pauta da oferta 1 (inscrição daquela oferta desativada).
    with app.app_context():
        inscricao = Inscricao.query.filter_by(
            aluno_id=ids["alunos"][1], turma_curso_id=ids["ofertas"][1],
        ).first()
        inscricao.ativo = False
        db.session.commit()

    resposta = post(
        client, ids, {ids["alunos"][1]: "A"}, [ids["valores"]["ativo"]],
        extras={"turma_curso": str(ids["ofertas"][1])},
    )

    assert resposta.status_code == 302
    assert contagens(app)[0] == 0
    assert MENSAGEM not in corpo_pauta(client, ids, ids["ofertas"][1])


def test_estatisticas_e_pauta_impressa_nao_dependem_do_valor(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    impressa_com = _pauta_impressa(client, ids)

    # Troca só o conjunto da aula: conceito/estatística/pauta não mudam.
    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["outro"]])

    assert _pauta_impressa(client, ids) == impressa_com
    assert linha(app, ids["aluno"]).conceito == "A"


def test_secretaria_continua_recebendo_403(app, client):
    ids = cenario(app)
    with app.app_context():
        secretaria = User(
            name="Secretaria AJ16B", email="sec.aj16b.v2@x.com",
            role="secretaria", first_login=False, unidade_id=ids["un"],
        )
        secretaria.set_password("SenhaLocal!123")
        db.session.add(secretaria)
        db.session.commit()
        secretaria_id = secretaria.id

    login_as(client, secretaria_id, ids["un"])
    resposta = post(
        client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]],
    )

    assert resposta.status_code == 403
    assert contagens(app) == (0, 0, 0)
