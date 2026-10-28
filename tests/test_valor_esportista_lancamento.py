# ruff: noqa: F811
"""A1 — lançamento do "Valor / Postura do Esportista" na pauta.

Regra crítica: o valor é um dado ADICIONAL. Ele só é gravado com conceito
A/B/C/D; F, J, campo vazio ou aluno sem conceito gravam NULL (ou preservam a
linha, quando o aluno não foi enviado). Nada aqui pode alterar conceito,
presença/falta, total de aulas ou percentual.
"""

import re
from datetime import date, time, timedelta

import pytest
from _helpers import login_as, nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
    ValorEsportista,
)
from app.utils.logica import carregar_contexto_turma, get_local_now


def _cenario(app, *, ofertas=1):
    """Unidade + período vigente + turma com N ofertas + 1 aluno + valores."""
    hoje = get_local_now().date()
    with app.app_context():
        un = Unidade(nome="Unidade A1V", ativo=True)
        un_b = Unidade(nome="Unidade B1V", ativo=True)
        user = User(
            name="Admin A1V", email="admin.a1v@x.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        user.set_password("SenhaLocal!123")
        db.session.add_all([un, un_b, user])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P A1V",
            data_inicio=hoje - timedelta(days=30),
            data_fim=hoje + timedelta(days=30),
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma A1V", turno="Manhã",
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
            periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        ids_ofertas = []
        for i in range(ofertas):
            curso = Curso(nome=f"Curso A1V {i}", unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            ids_ofertas.append(
                nova_oferta(
                    turma.id, curso.id, un.id, principal=(i == 0),
                    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
                    hora_inicio=time(8), hora_fim=time(10),
                ).id
            )

        aluno = Aluno(nome="Aluno A1V", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, ids_ofertas[0])
        if ofertas >= 2:
            nova_inscricao(aluno.id, turma.id, ids_ofertas[1])

        ativo = ValorEsportista(nome="Alegria", unidade_id=un.id, ativo=True)
        inativo = ValorEsportista(nome="Foco", unidade_id=un.id, ativo=False)
        externo = ValorEsportista(nome="Outro", unidade_id=un_b.id, ativo=True)
        db.session.add_all([ativo, inativo, externo])
        db.session.commit()

        data = carregar_contexto_turma(turma.id)["datas"][0]
        return {
            "un": un.id, "un_b": un_b.id, "user": user.id,
            "turma": turma.id, "ofertas": ids_ofertas, "aluno": aluno.id,
            "ativo": ativo.id, "inativo": inativo.id, "externo": externo.id,
            "data": data,
        }


def _post(client, ids, conceito="A", valor_id=None, extras=None):
    dados = {"turma": str(ids["turma"]), "data": ids["data"]}
    if conceito is not None:
        dados[f"aluno_{ids['aluno']}"] = conceito
    if valor_id is not None:
        dados[f"postura_aluno_{ids['aluno']}"] = str(valor_id)
    if extras:
        dados.update(extras)
    return client.post("/frequencia", data=dados, follow_redirects=False)


def _linha(app, ids, oferta_idx=0):
    with app.app_context():
        query = Frequencia.query.filter(Frequencia.aluno_id == ids["aluno"])
        if oferta_idx is not None:
            query = query.filter(
                Frequencia.turma_curso_id == ids["ofertas"][oferta_idx]
            )
        return query.first()


def _valor_gravado(app, ids, oferta_idx=0):
    linha = _linha(app, ids, oferta_idx)
    return (linha.conceito, linha.valor_esportista_id) if linha else (None, None)


def test_conceito_presenca_persiste_valor(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    resposta = _post(client, ids, conceito="A", valor_id=ids["ativo"])
    assert resposta.status_code == 302
    assert _valor_gravado(app, ids) == ("A", ids["ativo"])


@pytest.mark.parametrize("conceito", ["B", "C", "D"])
def test_conceitos_b_c_d_tambem_persistem(app, client, conceito):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito=conceito, valor_id=ids["ativo"])
    assert _valor_gravado(app, ids) == (conceito, ids["ativo"])


def test_conceito_f_limpa_valor_anterior(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=ids["ativo"])
    assert _valor_gravado(app, ids)[1] == ids["ativo"]

    _post(client, ids, conceito="F", valor_id=ids["ativo"])
    assert _valor_gravado(app, ids) == ("F", None)


def test_conceito_j_limpa_valor_anterior(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=ids["ativo"])
    _post(client, ids, conceito="J", valor_id=ids["ativo"])
    assert _valor_gravado(app, ids) == ("J", None)


def test_valor_sem_conceito_e_ignorado(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito=None, valor_id=ids["ativo"])
    assert _linha(app, ids) is None


def _corpo_pauta(client, ids):
    """Corpo da pauta (é aqui que o flash da pendência aparece)."""
    return client.get(
        f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"
    ).get_data(as_text=True)


def test_valor_de_outra_unidade_vira_pendencia(app, client):
    """V2: valor de outra unidade conta como AUSENTE (nada é gravado)."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    resposta = _post(client, ids, conceito="A", valor_id=ids["externo"])
    assert resposta.status_code == 302
    assert _linha(app, ids) is None
    assert "obrigatório para presença" in _corpo_pauta(client, ids)


def test_valor_inativo_novo_vira_pendencia(app, client):
    """V2: valor inativo que nunca foi salvo conta como AUSENTE."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=ids["inativo"])
    assert _linha(app, ids) is None
    assert "obrigatório para presença" in _corpo_pauta(client, ids)


def test_valor_inexistente_vira_pendencia_sem_derrubar(app, client):
    """V2: id inexistente é pendência (302), nunca erro 500."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    resposta = _post(client, ids, conceito="A", valor_id=999999)
    assert resposta.status_code == 302
    assert _linha(app, ids) is None
    assert "obrigatório para presença" in _corpo_pauta(client, ids)


def test_valor_inativo_ja_salvo_preserva_no_get_e_no_post(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    # Grava direto um valor que depois é inativado no cadastro.
    with app.app_context():
        linha = Frequencia(
            aluno_id=ids["aluno"], turma_id=ids["turma"],
            turma_curso_id=ids["ofertas"][0],
            data=date.fromisoformat(ids["data"]), conceito="A",
            valor_esportista_id=ids["inativo"], unidade_id=ids["un"],
        )
        db.session.add(linha)
        db.session.commit()

    corpo = client.get(
        f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"
    ).get_data(as_text=True)
    assert "Foco (inativo)" in corpo
    assert f'value="{ids["inativo"]}" selected' in corpo

    # Reabrir e salvar (o browser envia o valor inativo já selecionado)
    # preserva a escolha — não perde histórico.
    _post(client, ids, conceito="A", valor_id=ids["inativo"])
    assert _valor_gravado(app, ids) == ("A", ids["inativo"])


def test_a_d_sem_valor_vira_pendencia(app, client):
    """V2: A–D sem valor recusa o lançamento inteiro (antes salvava NULL)."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=None)
    assert _linha(app, ids) is None
    assert "obrigatório para presença" in _corpo_pauta(client, ids)


def test_secretaria_nao_lanca(app, client):
    ids = _cenario(app)
    with app.app_context():
        sec = User(
            name="Sec A1V", email="sec.a1v@x.com", role="secretaria",
            first_login=False, unidade_id=ids["un"],
        )
        sec.set_password("SenhaLocal!123")
        db.session.add(sec)
        db.session.commit()
        sec_id = sec.id
    login_as(client, sec_id, ids["un"])
    resposta = _post(client, ids, conceito="A", valor_id=ids["ativo"])
    assert resposta.status_code == 403
    assert _linha(app, ids) is None


def test_aluno_transferido_nao_recebe_nada(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=ids["ativo"])
    assert _valor_gravado(app, ids) == ("A", ids["ativo"])

    # Inscrição desativada (transferido): some da pauta e o POST não altera a
    # linha existente.
    with app.app_context():
        insc = Inscricao.query.filter_by(aluno_id=ids["aluno"]).first()
        insc.ativo = False
        db.session.commit()

    _post(client, ids, conceito="F", valor_id=ids["ativo"])
    assert _valor_gravado(app, ids) == ("A", ids["ativo"])


def test_duas_ofertas_gravam_no_registro_da_oferta(app, client):
    ids = _cenario(app, ofertas=2)
    login_as(client, ids["user"], ids["un"])
    _post(
        client, ids, conceito="A", valor_id=ids["ativo"],
        extras={"turma_curso": str(ids["ofertas"][1])},
    )
    assert _valor_gravado(app, ids, oferta_idx=1) == ("A", ids["ativo"])
    assert _linha(app, ids, oferta_idx=0) is None


def test_estatisticas_nao_mudam_com_valor(app, client):
    """Não regressão: P/F/J/aulas são idênticos qualquer que seja o valor."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    url = f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"

    with app.app_context():
        outro = ValorEsportista(
            nome="Disciplina", unidade_id=ids["un"], ativo=True,
        )
        db.session.add(outro)
        db.session.commit()
        outro_id = outro.id

    _post(client, ids, conceito="A", valor_id=ids["ativo"])
    antes = _estatisticas(client.get(url).get_data(as_text=True))

    _post(client, ids, conceito="A", valor_id=outro_id)
    depois = _estatisticas(client.get(url).get_data(as_text=True))

    assert antes == depois
    assert antes  # a pauta trouxe as estatísticas do aluno
    assert _valor_gravado(app, ids) == ("A", outro_id)


def _estatisticas(corpo):
    """`[(P, F, J, aulas)]` dos cartões de aluno, na ordem da página."""
    padrao = re.compile(
        r"P:\s*([\d.]+)%\s*</span>.*?F:\s*([\d.]+)%\s*</span>"
        r".*?J:\s*(\d+)\s*</span>.*?\((\d+)\s*aulas\)",
        re.S,
    )
    return padrao.findall(corpo)


def _url_pauta(ids):
    return f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"


def _select_postura(corpo, aluno_id):
    """A tag `<select>` do Valor do Esportista daquele aluno."""
    achado = re.search(
        r'<select[^>]*name="postura_aluno_%d"[^>]*>' % aluno_id, corpo,
    )
    assert achado, "select do Valor do Esportista não renderizou"
    return achado.group(0)


def test_select_habilitado_apenas_com_conceito_de_presenca(app, client):
    """Estado inicial do select: A–D habilita; sem conceito ou F/J desabilita."""
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])

    sem_conceito = _select_postura(
        client.get(_url_pauta(ids)).get_data(as_text=True), ids["aluno"],
    )
    assert "disabled" in sem_conceito

    _post(client, ids, conceito="A", valor_id=ids["ativo"])
    com_conceito = _select_postura(
        client.get(_url_pauta(ids)).get_data(as_text=True), ids["aluno"],
    )
    assert "disabled" not in com_conceito
    assert f'value="{ids["ativo"]}" selected' in client.get(
        _url_pauta(ids)
    ).get_data(as_text=True)

    _post(client, ids, conceito="J", valor_id=None)
    assert "disabled" in _select_postura(
        client.get(_url_pauta(ids)).get_data(as_text=True), ids["aluno"],
    )


def test_valor_inativo_nao_aparece_no_select_sem_uso(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    corpo = client.get(_url_pauta(ids)).get_data(as_text=True)
    # "Foco" existe na unidade, mas está inativo e nunca foi lançado.
    assert "Alegria" in corpo
    assert "Foco" not in corpo


def test_is_readonly_desabilita_o_select_e_o_post_e_recusado(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A", valor_id=ids["ativo"])

    with app.app_context():
        sec = User(
            name="Sec A1V 2", email="sec.a1v2@x.com", role="secretaria",
            first_login=False, unidade_id=ids["un"],
        )
        sec.set_password("SenhaLocal!123")
        db.session.add(sec)
        db.session.commit()
        sec_id = sec.id

    login_as(client, sec_id, ids["un"])
    corpo = client.get(_url_pauta(ids)).get_data(as_text=True)
    assert "disabled" in _select_postura(corpo, ids["aluno"])
    assert _post(client, ids, conceito="F", valor_id=None).status_code == 403
    assert _valor_gravado(app, ids) == ("A", ids["ativo"])

