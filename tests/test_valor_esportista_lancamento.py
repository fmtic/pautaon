# ruff: noqa: F811
"""AJ16-B — lançamento do "Valor / Postura do Esportista" na AULA.

Desde o AJ16-B o valor/postura do esportista pertence à AULA (oferta + data),
em N:N com `RegistroAula`, como os temas. Ele é um dado ADICIONAL: não entra
em nenhuma conta de presença/falta, total de aulas, percentual, pauta impressa,
relatório ou exportação.

Contratos cobertos aqui:
    - 0..N valores por aula, sem valor padrão e sem valor por aluno;
    - conceito A–D não cria/limpa valor por si só (o conjunto é da aula);
    - F/J e aula sem presença preservam o conjunto selecionado;
    - o conjunto é substituído por inteiro e deduplicado no servidor;
    - valor inativo já vinculado é preservado; novo inativo, inexistente ou de
      outra unidade recusa a gravação inteira;
    - o autor F1 não muda quando só os valores da aula mudam.
"""

import re

import pytest
from sqlalchemy import event

from _helpers import login_as
from _valor_aula import (
    cenario,
    contagens,
    corpo_pauta,
    linha,
    post,
    url_pauta,
    valores_da_aula,
)

from app import db
from app.models import Inscricao, RegistroAula, User, ValorEsportista


def _estatisticas(corpo):
    """`[(P, F, J, aulas)]` dos cartões de aluno, na ordem da página."""
    padrao = re.compile(
        r"P:\s*([\d.]+)%\s*</span>.*?F:\s*([\d.]+)%\s*</span>"
        r".*?J:\s*(\d+)\s*</span>.*?\((\d+)\s*aulas\)",
        re.S,
    )
    return padrao.findall(corpo)


@pytest.mark.parametrize("conceito", ["A", "B", "C", "D"])
def test_conceito_presenca_persiste_conjunto_da_aula(app, client, conceito):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(
        client, ids, {ids["aluno"]: conceito},
        [ids["valores"]["ativo"]],
    )

    assert resposta.status_code == 302
    assert linha(app, ids["aluno"]).conceito == conceito
    assert valores_da_aula(app, ids) == [ids["valores"]["ativo"]]


@pytest.mark.parametrize("conceito", ["F", "J"])
def test_falta_e_justificada_preservam_os_valores_da_aula(app, client, conceito):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    assert valores_da_aula(app, ids) == [ids["valores"]["ativo"]]

    resposta = post(
        client, ids, {ids["aluno"]: conceito}, [ids["valores"]["ativo"]],
    )

    assert resposta.status_code == 302
    assert linha(app, ids["aluno"]).conceito == conceito
    assert valores_da_aula(app, ids) == [ids["valores"]["ativo"]]


def test_aula_sem_presenca_pode_ter_valores_e_nao_cria_frequencia(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = post(client, ids, {}, [ids["valores"]["ativo"], ids["valores"]["outro"]])

    assert resposta.status_code == 302
    assert linha(app, ids["aluno"]) is None
    assert contagens(app)[0] == 0
    assert valores_da_aula(app, ids) == sorted(
        [ids["valores"]["ativo"], ids["valores"]["outro"]]
    )


def test_substitui_o_conjunto_por_inteiro(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"},
         [ids["valores"]["ativo"], ids["valores"]["outro"]])
    assert valores_da_aula(app, ids) == sorted(
        [ids["valores"]["ativo"], ids["valores"]["outro"]]
    )

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["outro"]])

    assert valores_da_aula(app, ids) == [ids["valores"]["outro"]]


def test_duplicatas_enviadas_sao_deduplicadas(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(
        client, ids, {ids["aluno"]: "A"},
        [ids["valores"]["ativo"], ids["valores"]["ativo"]],
    )

    assert valores_da_aula(app, ids) == [ids["valores"]["ativo"]]
    assert contagens(app)[2] == 1


def test_valor_inativo_ja_vinculado_continua_visivel_e_valido(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])
    from _valor_aula import definir_valores

    definir_valores(app, ids, [ids["valores"]["inativo"]])

    corpo = corpo_pauta(client, ids)
    assert "Disciplina (inativo)" in corpo
    assert f'value="{ids["valores"]["inativo"]}" checked' in corpo

    # Reenviar o inativo que já estava vinculado preserva o histórico.
    resposta = post(
        client, ids, {ids["aluno"]: "A"}, [ids["valores"]["inativo"]],
    )

    assert resposta.status_code == 302
    assert valores_da_aula(app, ids) == [ids["valores"]["inativo"]]


@pytest.mark.parametrize("origem", ["inativo_novo", "inexistente", "outra_unidade"])
def test_valor_sem_validade_recusa_tudo(app, client, origem):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    if origem == "inativo_novo":
        valor_id = ids["valores"]["inativo"]
    elif origem == "inexistente":
        valor_id = 999999
    else:
        valor_id = ids["valores"]["externo"]

    resposta = post(
        client, ids, {ids["aluno"]: "A"}, [valor_id],
        extras={"observacoes": "não deve gravar"},
    )

    assert resposta.status_code == 302
    assert contagens(app) == (0, 0, 0)
    corpo = corpo_pauta(client, ids)
    assert "Nada foi salvo." in corpo
    assert "obrigatório" not in corpo


def test_valor_de_outra_unidade_nao_vaza_para_a_aula(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["externo"]])

    assert valores_da_aula(app, ids) is None
    assert contagens(app) == (0, 0, 0)


def test_nao_existe_valor_padrao_ao_salvar_sem_selecao(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    # Sem A–D a aula pode ficar sem valor: nada é inventado.
    resposta = post(client, ids, {ids["aluno"]: "F"}, [])

    assert resposta.status_code == 302
    assert valores_da_aula(app, ids) == []
    assert contagens(app)[2] == 0


def test_secretaria_nao_lanca(app, client):
    ids = cenario(app)
    with app.app_context():
        sec = User(
            name="Sec AJ16B", email="sec.aj16b@x.com", role="secretaria",
            first_login=False, unidade_id=ids["un"],
        )
        sec.set_password("SenhaLocal!123")
        db.session.add(sec)
        db.session.commit()
        sec_id = sec.id

    login_as(client, sec_id, ids["un"])
    resposta = post(
        client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]],
    )

    assert resposta.status_code == 403
    assert contagens(app) == (0, 0, 0)


def test_aluno_transferido_nao_recebe_nada(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    assert linha(app, ids["aluno"]).conceito == "A"

    with app.app_context():
        insc = Inscricao.query.filter_by(aluno_id=ids["aluno"]).first()
        insc.ativo = False
        db.session.commit()

    post(client, ids, {ids["aluno"]: "F"}, [])

    assert linha(app, ids["aluno"]).conceito == "A"


def test_duas_ofertas_tem_conjuntos_independentes(app, client):
    ids = cenario(app, ofertas=2)
    login_as(client, ids["admin"], ids["un"])

    post(
        client, ids, {ids["aluno"]: "A"}, [ids["valores"]["outro"]],
        extras={"turma_curso": str(ids["ofertas"][1])},
    )

    assert valores_da_aula(app, ids, oferta_idx=1) == [ids["valores"]["outro"]]
    assert valores_da_aula(app, ids, oferta_idx=0) is None
    assert linha(app, ids["aluno"]).turma_curso_id == ids["ofertas"][1]


def test_estatisticas_nao_mudam_quando_so_o_valor_muda(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    antes = _estatisticas(corpo_pauta(client, ids))

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["outro"]])
    depois = _estatisticas(corpo_pauta(client, ids))

    assert antes == depois
    assert antes  # a pauta trouxe as estatísticas do aluno
    assert valores_da_aula(app, ids) == [ids["valores"]["outro"]]


def test_autor_f1_nao_muda_quando_so_os_valores_mudam(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])
    with app.app_context():
        autor_original = linha(app, ids["aluno"]).autor_id
        assert autor_original == ids["admin"]
        outro = User(
            name="Outro Prof AJ16B", email="outro.aj16b@x.com",
            role="admin", first_login=False, unidade_id=ids["un"],
        )
        outro.set_password("SenhaLocal!123")
        db.session.add(outro)
        db.session.commit()
        outro_id = outro.id

    login_as(client, outro_id, ids["un"])
    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["outro"]])

    with app.app_context():
        atual = linha(app, ids["aluno"])
        assert atual.autor_id == autor_original
        assert atual.conceito == "A"


def test_pauta_faz_numero_constante_de_consultas(app, client):
    """`RegistroAula.valores` é `selectin`: N valores não geram N+1."""
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"}, [ids["valores"]["ativo"]])

    def _conta():
        consultas = []

        def _registra(_conn, _cursor, statement, _params, _context, _many):
            consultas.append(statement)

        event.listen(db.engine, "before_cursor_execute", _registra)
        try:
            with app.app_context():
                client.get(url_pauta(ids))
        finally:
            event.remove(db.engine, "before_cursor_execute", _registra)
        return len(consultas)

    # Aquece o cache do app/sessão antes de medir.
    client.get(url_pauta(ids))
    com_1 = _conta()

    with app.app_context():
        extras = []
        for indice in range(6):
            valor = ValorEsportista(
                nome=f"Extra AJ16B {indice}", unidade_id=ids["un"], ativo=True,
            )
            db.session.add(valor)
            db.session.flush()
            extras.append(valor.id)
        diario = RegistroAula.query.filter_by(
            turma_curso_id=ids["ofertas"][0]
        ).one()
        diario.valores = list(diario.valores) + list(
            ValorEsportista.query.filter(ValorEsportista.id.in_(extras)).all()
        )
        db.session.commit()

    com_7 = _conta()

    assert com_1 == com_7
    assert contagens(app)[2] == 7
