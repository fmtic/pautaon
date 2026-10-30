# ruff: noqa: F811
"""V2 — Valor/Postura do Esportista obrigatório para presença (A–D).

Regra (decidida com o responsável):

    1. Ao salvar a pauta, todo aluno com conceito A/B/C/D exige
       `valor_esportista_id` preenchido. F, J e sem conceito não exigem (F/J
       continuam limpando o valor).
    2. Exceção: unidade da turma SEM nenhum valor ativo no catálogo — a regra
       não se aplica (a pauta não pode travar).
    3. Valor inativo JÁ salvo continua válido; inativo novo, inexistente ou de
       outra unidade conta como AUSENTE.
    4. Servidor valida tudo antes de gravar: havendo pendência, NADA é gravado
       (nem conceitos, nem diário), e a mensagem lista os alunos (até 10 + "e
       mais N").

A tela (select `required`, bloqueio no submit, aviso de cadastro) é coberta em
`test_valor_obrigatorio_ui.py`.
"""

import re
from datetime import time, timedelta

import pytest
from _helpers import login_as, nova_inscricao, nova_oferta
from test_valor_esportista_lancamento import _estatisticas  # noqa: F401

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    Unidade,
    User,
    ValorEsportista,
)
from app.utils.logica import carregar_contexto_turma, get_local_now

PRESENCA = ["A", "B", "C", "D"]


def _cenario(app, *, alunos=1, ofertas=1, com_valores=True):
    """Unidade + período + turma + N alunos (inscritos em todas as ofertas)."""
    hoje = get_local_now().date()
    with app.app_context():
        un = Unidade(nome="Unidade V2", ativo=True)
        db.session.add(un)
        db.session.flush()

        admin = User(
            name="Admin V2", email="admin.v2@x.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        admin.set_password("SenhaLocal!123")
        professor = User(
            name="Professor V2", email="prof.v2@x.com", role="professor",
            first_login=False, unidade_id=un.id,
        )
        professor.set_password("SenhaLocal!123")
        db.session.add_all([admin, professor])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P V2",
            data_inicio=hoje - timedelta(days=30),
            data_fim=hoje + timedelta(days=30),
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma V2", turno="Manhã",
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
            periodo_letivo_id=periodo.id, unidade_id=un.id,
            professor_id=professor.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        ids_ofertas = []
        for indice in range(ofertas):
            curso = Curso(
                nome=f"Curso V2 {indice}", unidade_id=un.id, ativo=True,
            )
            db.session.add(curso)
            db.session.flush()
            ids_ofertas.append(
                nova_oferta(
                    turma.id, curso.id, un.id, principal=(indice == 0),
                    professor_id=professor.id,
                    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
                    hora_inicio=time(8), hora_fim=time(10),
                ).id
            )

        ids_alunos = []
        ids_inscricoes = []
        for indice in range(alunos):
            aluno = Aluno(
                nome=f"Aluno V2 {indice}", unidade_id=un.id, ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            ids_inscricoes.append(
                nova_inscricao(aluno.id, turma.id, ids_ofertas[0]).id
            )
            if ofertas >= 2:
                nova_inscricao(aluno.id, turma.id, ids_ofertas[1])
            ids_alunos.append(aluno.id)

        valores = {}
        if com_valores:
            ativo = ValorEsportista(nome="Alegria", unidade_id=un.id, ativo=True)
            outro = ValorEsportista(nome="Foco", unidade_id=un.id, ativo=True)
            db.session.add_all([ativo, outro])
            db.session.flush()
            valores = {"ativo": ativo.id, "outro": outro.id}

        db.session.commit()
        return {
            "un": un.id,
            "admin": admin.id,
            "professor": professor.id,
            "turma": turma.id,
            "ofertas": ids_ofertas,
            "alunos": ids_alunos,
            "inscricoes": ids_inscricoes,
            "valores": valores,
            "data": carregar_contexto_turma(turma.id)["datas"][0],
        }


def _url_pauta(ids, oferta_id=None):
    url = f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"
    if oferta_id:
        url += f"&turma_curso={oferta_id}"
    return url


def _post(client, ids, conceitos, valores=None, extras=None):
    """POST /frequencia com `{aluno_id: conceito}` e `{aluno_id: valor_id}`."""
    dados = {"turma": str(ids["turma"]), "data": ids["data"]}
    for aluno_id, conceito in conceitos.items():
        dados[f"aluno_{aluno_id}"] = conceito
    for aluno_id, valor_id in (valores or {}).items():
        dados[f"postura_aluno_{aluno_id}"] = str(valor_id)
    if extras:
        dados.update(extras)
    return client.post("/frequencia", data=dados, follow_redirects=False)


def _contagens(app):
    """(linhas de frequência, linhas de diário) — prova de gravação atômica."""
    with app.app_context():
        return Frequencia.query.count(), RegistroAula.query.count()


def _linhas_frequencia(app):
    with app.app_context():
        return Frequencia.query.count()


def _linha(app, aluno_id):
    with app.app_context():
        return Frequencia.query.filter_by(aluno_id=aluno_id).first()


def _flash(client, ids, oferta_id=None):
    """Corpo da pauta após o POST (aqui o flash da pendência é exibido)."""
    return client.get(_url_pauta(ids, oferta_id)).get_data(as_text=True)


def _pauta_impressa(client, ids):
    resposta = client.get(f"/turma/{ids['turma']}/imprimir-pauta")
    assert resposta.status_code == 200
    return resposta.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Regra 1 + 4: A–D sem valor recusa e não grava nada
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("conceito", PRESENCA)
def test_presenca_sem_valor_recusa_e_nao_grava_nada(app, client, conceito):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    resposta = _post(
        client, ids, {aluno: conceito},
        extras={"observacoes": "não deve gravar", "atividades": "nem isto"},
    )

    assert resposta.status_code == 302
    assert _contagens(app) == (0, 0)

    corpo = _flash(client, ids)
    assert "obrigatório para presença" in corpo
    assert "Aluno V2 0" in corpo


@pytest.mark.parametrize("conceito", PRESENCA)
def test_presenca_com_valor_grava_conceito_valor_e_diario(app, client, conceito):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    resposta = _post(
        client, ids, {aluno: conceito}, {aluno: ids["valores"]["ativo"]},
        extras={"observacoes": "gravou", "atividades": "gravou também"},
    )

    assert resposta.status_code == 302
    linha = _linha(app, aluno)
    assert (linha.conceito, linha.valor_esportista_id) == (
        conceito, ids["valores"]["ativo"],
    )
    assert _contagens(app) == (1, 1)
    with app.app_context():
        diario = RegistroAula.query.one()
        assert diario.observacoes == "gravou"
        assert diario.atividades == "gravou também"


# ---------------------------------------------------------------------------
# Regra 1: F/J não exigem e continuam limpando o valor
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("conceito", ["F", "J"])
def test_falta_e_justificada_sem_valor_salvam_e_limpam(app, client, conceito):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    _post(client, ids, {aluno: "A"}, {aluno: ids["valores"]["ativo"]})
    assert _linha(app, aluno).valor_esportista_id == ids["valores"]["ativo"]

    resposta = _post(client, ids, {aluno: conceito})

    assert resposta.status_code == 302
    linha = _linha(app, aluno)
    assert (linha.conceito, linha.valor_esportista_id) == (conceito, None)


def test_aluno_sem_conceito_nao_cria_linha(app, client):
    """Sem conceito não há linha de frequência (o diário vazio pode existir)."""
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = _post(client, ids, {})

    assert resposta.status_code == 302
    assert _linhas_frequencia(app) == 0


def test_sem_conceito_preserva_linha_e_valor_existentes(app, client):
    """Reabrir a pauta e salvar sem tocar no aluno não apaga o histórico."""
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    _post(client, ids, {aluno: "A"}, {aluno: ids["valores"]["ativo"]})
    _post(client, ids, {})

    linha = _linha(app, aluno)
    assert (linha.conceito, linha.valor_esportista_id) == (
        "A", ids["valores"]["ativo"],
    )


# ---------------------------------------------------------------------------
# Regra 2: unidade sem catálogo ativo fica isenta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("conceito", PRESENCA)
def test_unidade_sem_valores_ativos_isenta_a_regra(app, client, conceito):
    ids = _cenario(app, com_valores=False)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    resposta = _post(client, ids, {aluno: conceito})

    assert resposta.status_code == 302
    linha = _linha(app, aluno)
    assert (linha.conceito, linha.valor_esportista_id) == (conceito, None)
    assert "obrigatório para presença" not in _flash(client, ids)


# ---------------------------------------------------------------------------
# Regra 3: valor inativo já salvo continua valendo
# ---------------------------------------------------------------------------

def test_valor_inativo_ja_salvo_continua_valendo(app, client):
    from datetime import date

    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    with app.app_context():
        legado = ValorEsportista(
            nome="Antigo", unidade_id=ids["un"], ativo=False,
        )
        db.session.add(legado)
        db.session.flush()
        db.session.add(Frequencia(
            aluno_id=aluno, turma_id=ids["turma"],
            turma_curso_id=ids["ofertas"][0],
            data=date.fromisoformat(ids["data"]), conceito="A",
            valor_esportista_id=legado.id,
        ))
        db.session.commit()
        legado_id = legado.id

    resposta = _post(client, ids, {aluno: "A"}, {aluno: legado_id})

    assert resposta.status_code == 302
    linha = _linha(app, aluno)
    assert (linha.conceito, linha.valor_esportista_id) == ("A", legado_id)


@pytest.mark.parametrize("origem", ["inativo_novo", "inexistente", "outra_unidade"])
def test_valor_sem_validade_e_pendencia(app, client, origem):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    with app.app_context():
        outra = Unidade(nome="Unidade V2 B", ativo=True)
        db.session.add(outra)
        db.session.flush()
        escolhas = {
            "inativo_novo": ValorEsportista(
                nome="Inativo Y", unidade_id=ids["un"], ativo=False,
            ).id,
            "inexistente": 999999,
        }
        if origem == "outra_unidade":
            db.session.flush()
            escolhas["outra_unidade"] = ValorEsportista(
                nome="Externo Y", unidade_id=outra.id, ativo=True,
            ).id
        db.session.flush()
        valor_id = escolhas[origem]
        db.session.commit()

    resposta = _post(client, ids, {aluno: "A"}, {aluno: valor_id})

    assert resposta.status_code == 302
    assert _contagens(app) == (0, 0)
    assert "obrigatório para presença" in _flash(client, ids)


# ---------------------------------------------------------------------------
# Regra 4: mensagem com nomes e truncamento
# ---------------------------------------------------------------------------

def test_mensagem_lista_os_alunos_pendentes(app, client):
    ids = _cenario(app, alunos=2)
    login_as(client, ids["admin"], ids["un"])

    _post(client, ids, {a: "A" for a in ids["alunos"]})

    corpo = _flash(client, ids)
    assert "Aluno V2 0" in corpo
    assert "Aluno V2 1" in corpo
    assert _contagens(app) == (0, 0)


def test_mensagem_trunca_acima_de_dez_alunos(app, client):
    ids = _cenario(app, alunos=12)
    login_as(client, ids["admin"], ids["un"])

    _post(client, ids, {a: "A" for a in ids["alunos"]})

    corpo = _flash(client, ids)
    pendentes = re.search(
        r"Alunos pendentes: (.*?)\. Nada foi salvo", corpo, re.S,
    )
    assert pendentes, "mensagem de pendência não renderizou"
    lista = pendentes.group(1)

    assert lista.endswith("e mais 2")
    assert "Aluno V2 9" in lista
    assert "Aluno V2 10" not in lista  # o 11º nome não é listado
    assert _contagens(app) == (0, 0)


# ---------------------------------------------------------------------------
# Duas ofertas: valida só a pauta da oferta do formulário
# ---------------------------------------------------------------------------

def test_duas_ofertas_valida_so_alunos_da_oferta_do_formulario(app, client):
    ids = _cenario(app, alunos=2, ofertas=2)
    login_as(client, ids["admin"], ids["un"])
    # Aluno 1 sai da pauta da oferta 1 (inscrição naquela oferta desativada).
    with app.app_context():
        inscricao = Inscricao.query.filter_by(
            aluno_id=ids["alunos"][1], turma_curso_id=ids["ofertas"][1],
        ).first()
        inscricao.ativo = False
        db.session.commit()

    resposta = _post(
        client, ids, {ids["alunos"][1]: "A"},
        extras={"turma_curso": str(ids["ofertas"][1])},
    )

    assert resposta.status_code == 302
    assert _linhas_frequencia(app) == 0
    assert "obrigatório para presença" not in _flash(client, ids, ids["ofertas"][1])


def test_duas_ofertas_pendencia_na_oferta_do_formulario(app, client):
    ids = _cenario(app, alunos=1, ofertas=2)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    resposta = _post(
        client, ids, {aluno: "A"},
        extras={"turma_curso": str(ids["ofertas"][1])},
    )

    assert resposta.status_code == 302
    assert _contagens(app) == (0, 0)
    assert "obrigatório para presença" in _flash(client, ids, ids["ofertas"][1])


# ---------------------------------------------------------------------------
# Não regressão: valor não entra em estatística nem em pauta impressa
# ---------------------------------------------------------------------------

def test_estatisticas_e_pauta_impressa_nao_dependem_do_valor(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    _post(client, ids, {aluno: "A"}, {aluno: ids["valores"]["ativo"]})
    impressa_antes = _pauta_impressa(client, ids)
    stats_antes = _estatisticas(_flash(client, ids))

    # Anula o valor direto no banco (fora da rota) e compara as saídas.
    with app.app_context():
        linha = Frequencia.query.filter_by(aluno_id=aluno).first()
        linha.valor_esportista_id = None
        db.session.commit()

    assert _pauta_impressa(client, ids) == impressa_antes
    assert _estatisticas(_flash(client, ids)) == stats_antes


# ---------------------------------------------------------------------------
# Permissões: secretaria continua sem lançar
# ---------------------------------------------------------------------------

def test_secretaria_continua_recebendo_403(app, client):
    ids = _cenario(app)
    with app.app_context():
        secretaria = User(
            name="Secretaria V2", email="sec.v2@x.com", role="secretaria",
            first_login=False, unidade_id=ids["un"],
        )
        secretaria.set_password("SenhaLocal!123")
        db.session.add(secretaria)
        db.session.commit()
        secretaria_id = secretaria.id

    login_as(client, secretaria_id, ids["un"])
    resposta = _post(
        client, ids, {ids["alunos"][0]: "A"},
        {ids["alunos"][0]: ids["valores"]["ativo"]},
    )

    assert resposta.status_code == 403
    assert _contagens(app) == (0, 0)
