"""AJ7-A — auditoria da edição do conselho individual por gestor.

Regra: quando admin, pedagógico (ou qualquer papel que NÃO seja o professor da
oferta) altera respostas do conselho individual de uma oferta, a edição fica
registrada em `log_acao` com autor, aluno, oferta, professor da oferta e
campos alterados — nunca com o professor da oferta como autor.

Cobertura:
    A0 descoberta: `ConselhoResposta` não herda `AuditoriaMixin`; o listener
       genérico "Criar/Alterar <Modelo>" não registra a edição da resposta.
    A1 admin altera resposta de escolha + observação -> 1 log por aluno, com
       ids, papel, tipo=alteracao, valor anterior -> novo no campo enumerado
       e "texto alterado" nos campos livres (sem conteúdo).
    A2 pedagógico altera -> log com papel=pedagogico.
    A3 salvamento sem mudança -> nenhum log novo.
    A4 professor da oferta salva -> nenhum log do helper.
    A5 primeiro preenchimento por admin -> tipo=preenchimento.
    A6 texto livre (resposta e observação) nunca aparece nos detalhes.
    A7 outro professor -> 403 e nada gravado.
    A8 filtro de `/admin/logs` exibe o rótulo na categoria `edicao`.
    A9 golden: salvar sem mudança mantém a tela idêntica.

Nomes sintéticos, SQLite do fixture `app`; nenhuma escrita em banco real.
"""

import re
from datetime import date

from _helpers import login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    ConselhoClasse,
    ConselhoResposta,
    Curso,
    LogAcao,
    PerguntaConselho,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)

OPCOES = "Nunca | As vezes | Sempre"
#: Rótulo do log (constante local para que a reversão no código antigo colete
#: os testes e falhe no comportamento, não no import).
ACAO_EDICAO_CONSELHO_GESTOR = "Alteração de conselho (gestor)"
RESP_ESCOLHA = "Nunca"
OBS_INICIAL = "Observacao inicial do conselho"
RESP_LIVRE = "Resposta livre inicial"
SEGREDO_OBS = "SEGREDO-OBSERVACAO-QUE-NAO-PODE-VAZAR"
SEGREDO_TEXTO = "SEGREDO-TEXTO-LIVRE-QUE-NAO-PODE-VAZAR"

_URL_LANCAMENTO = "/conselho/lancamento?turma={turma}&etapa=INICIAL&oferta_sel={oferta}"


def _usuario(nome, role, unidade_id):
    user = User(
        name=nome,
        email=f"{nome.lower().replace(' ', '.')}@example.com",
        role=role,
        first_login=False,
        unidade_id=unidade_id,
    )
    user.set_password("SenhaLocal!123")
    db.session.add(user)
    return user


def _seed(app):
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ7A", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        prof = _usuario("Professor AJ7A", "professor", unidade.id)
        db.session.flush()
        outro_prof = _usuario("Outro Professor AJ7A", "professor", unidade.id)
        db.session.flush()
        admin = _usuario("Admin AJ7A", "admin", unidade.id)
        db.session.flush()
        pedagogico = _usuario("Pedagogico AJ7A", "pedagogico", unidade.id)
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="Periodo AJ7A", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma AJ7A", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True, professor_id=prof.id,
        )
        db.session.add(turma)
        db.session.flush()

        curso = Curso(nome="Curso AJ7A", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        oferta = nova_oferta(
            turma.id, curso.id, unidade.id, programa="Programa AJ7A",
            principal=True, professor_id=prof.id,
        )

        aluno = Aluno(nome="Aluno AJ7A", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, oferta.id)

        # Segundo aluno SEM ConselhoClasse: serve à descoberta A0b (primeiro
        # salvamento cria a linha e dispara o listener genérico).
        aluno2 = Aluno(nome="Aluno 2 AJ7A", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno2)
        db.session.flush()
        nova_inscricao(aluno2.id, turma.id, oferta.id)

        p_escolha = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="Como participa das aulas?", opcoes=OPCOES, ativo=True,
        )
        p_livre = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="O que a familia precisa saber?", opcoes="", ativo=True,
        )
        db.session.add_all([p_escolha, p_livre])
        db.session.flush()

        conselho = ConselhoClasse(
            turma_id=turma.id, turma_curso_id=oferta.id, aluno_id=aluno.id,
            etapa=EtapaConselho.INICIAL, unidade_id=unidade.id,
        )
        db.session.add(conselho)
        db.session.flush()

        r_escolha = ConselhoResposta(
            conselho_id=conselho.id, aluno_id=aluno.id,
            pergunta_id=p_escolha.id, resposta=RESP_ESCOLHA,
            observacao=OBS_INICIAL, unidade_id=unidade.id,
        )
        r_livre = ConselhoResposta(
            conselho_id=conselho.id, aluno_id=aluno.id,
            pergunta_id=p_livre.id, resposta=RESP_LIVRE,
            observacao="", unidade_id=unidade.id,
        )
        db.session.add_all([r_escolha, r_livre])
        db.session.commit()

        return {
            "un": unidade.id,
            "prof": prof.id,
            "outro_prof": outro_prof.id,
            "admin": admin.id,
            "pedagogico": pedagogico.id,
            "turma": turma.id,
            "oferta": oferta.id,
            "aluno": aluno.id,
            "aluno2": aluno2.id,
            "conselho": conselho.id,
            "p_escolha": p_escolha.id,
            "p_livre": p_livre.id,
        }


def _url_lancamento(ids):
    return _URL_LANCAMENTO.format(turma=ids["turma"], oferta=ids["oferta"])


def _form(ids, resp_escolha, obs_escolha, resp_livre, obs_livre):
    aluno, p_escolha, p_livre = ids["aluno"], ids["p_escolha"], ids["p_livre"]
    return {
        "turma_id": str(ids["turma"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["oferta"]),
        f"resp_{aluno}_{p_escolha}": resp_escolha,
        f"obs_{aluno}_{p_escolha}": obs_escolha,
        f"resp_{aluno}_{p_livre}": resp_livre,
        f"obs_{aluno}_{p_livre}": obs_livre,
    }


def _salvar(client, ids, *, resp_escolha, obs_escolha, resp_livre, obs_livre):
    return client.post(
        "/conselho/salvar",
        data=_form(ids, resp_escolha, obs_escolha, resp_livre, obs_livre),
    )


def _ids_logs(app):
    with app.app_context():
        return {row.id for row in LogAcao.query.all()}


def _logs_novos(app, antes):
    with app.app_context():
        return [
            row for row in LogAcao.query.order_by(LogAcao.id).all()
            if row.id not in antes
        ]


def _resposta(app, aluno_id, pergunta_id):
    with app.app_context():
        return ConselhoResposta.query.filter_by(
            aluno_id=aluno_id, pergunta_id=pergunta_id,
        ).one()


# ---------------------------------------------------------------------------
# A0 — descoberta: o listener genérico não cobre ConselhoResposta
# ---------------------------------------------------------------------------

def test_a0_listener_generico_nao_audita_conselho_resposta(client, app):
    ids = _seed(app)
    # ConselhoResposta NÃO herda AuditoriaMixin (só autor_id/autor_nome):
    # por isso o listener `before_flush` não cria "Criar/Alterar
    # ConselhoResposta" — a edição da resposta passa despercebida hoje.
    assert not hasattr(ConselhoResposta, "updated_by_id")

    login_as(client, ids["admin"], ids["un"])
    antes = _ids_logs(app)
    r = _salvar(
        client, ids, resp_escolha="Sempre", obs_escolha=OBS_INICIAL,
        resp_livre=RESP_LIVRE, obs_livre="",
    )
    assert r.status_code == 302

    novos = _logs_novos(app, antes)
    assert not [log for log in novos if "ConselhoResposta" in (log.acao or "")], (
        "o listener genérico passou a cobrir ConselhoResposta — a descoberta "
        "do AJ7-A envelheceu; revisar o helper"
    )
    # O helper do AJ7-A é o ÚNICO registro dessa edição.
    assert [log.acao for log in novos] == [ACAO_EDICAO_CONSELHO_GESTOR]


# ---------------------------------------------------------------------------
# A0b — descoberta: o listener cobre ConselhoClasse, mas sem ids nem campos
# ---------------------------------------------------------------------------

def test_a0b_listener_generico_loga_conselho_classe_sem_detalhes_uteis(client, app):
    ids = _seed(app)
    # `aluno2` não tem ConselhoClasse: o primeiro salvamento cria a linha, que
    # É auditada pelo listener (ConselhoClasse herda AuditoriaMixin).
    with app.app_context():
        assert ConselhoClasse.query.filter_by(aluno_id=ids["aluno2"]).count() == 0

    login_as(client, ids["admin"], ids["un"])
    antes = _ids_logs(app)
    aluno2, p_escolha, p_livre = ids["aluno2"], ids["p_escolha"], ids["p_livre"]
    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["turma"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["oferta"]),
        f"resp_{aluno2}_{p_escolha}": "Sempre",
        f"obs_{aluno2}_{p_escolha}": "Primeiro parecer",
        f"resp_{aluno2}_{p_livre}": "",
        f"obs_{aluno2}_{p_livre}": "",
    })
    assert r.status_code == 302

    novos = _logs_novos(app, antes)
    genericos = [log for log in novos if log.acao == "Criar ConselhoClasse"]
    assert len(genericos) == 1, [log.acao for log in novos]
    log = genericos[0]
    # O listener grava autor e unidade...
    assert log.usuario_id == ids["admin"]
    assert log.unidade_id == ids["un"]
    # ...mas `detalhes` é só o `repr` padrão do objeto: sem aluno, oferta,
    # professor, campos ou valores. É exatamente o que falta para a regra.
    assert "ConselhoClasse" in log.detalhes
    for ausente in (
        f"aluno_id={aluno2}", f"turma_curso_id={ids['oferta']}",
        f"professor_id={ids['prof']}", "campos=", "resposta[",
    ):
        assert ausente not in log.detalhes

    # O valor em si continua invisível: só o helper do AJ7-A descreve a edição.
    helper = [log for log in novos if log.acao == ACAO_EDICAO_CONSELHO_GESTOR]
    assert len(helper) == 1
    assert f"aluno_id={aluno2}" in helper[0].detalhes


# ---------------------------------------------------------------------------
# A1 — admin altera: um log por aluno, ids + valores só dos enumerados
# ---------------------------------------------------------------------------

def test_a1_admin_altera_gera_um_log_com_ids_e_campos(client, app):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])
    antes = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha="Sempre", obs_escolha=SEGREDO_OBS,
        resp_livre=SEGREDO_TEXTO, obs_livre="",
    )
    assert r.status_code == 302

    novos = _logs_novos(app, antes)
    assert len(novos) == 1, f"esperado 1 log por aluno; veio {len(novos)}"
    log = novos[0]
    assert log.acao == ACAO_EDICAO_CONSELHO_GESTOR
    assert log.usuario_id == ids["admin"]
    assert log.unidade_id == ids["un"]

    detalhes = log.detalhes
    assert f"aluno_id={ids['aluno']}" in detalhes
    assert f"turma_curso_id={ids['oferta']}" in detalhes
    assert f"professor_id={ids['prof']}" in detalhes
    assert f"usuario_id={ids['admin']}" in detalhes
    assert "papel=admin" in detalhes
    assert "tipo=alteracao" in detalhes
    assert "campos=observacao,resposta" in detalhes

    # Campo de escolha: valor anterior -> novo.
    assert (
        f"resposta[p{ids['p_escolha']}]: 'Nunca' -> 'Sempre'" in detalhes
    )
    # Texto livre: só o marcador, nunca o conteúdo.
    assert f"observacao[p{ids['p_escolha']}]: texto alterado" in detalhes
    assert f"resposta[p{ids['p_livre']}]: texto alterado" in detalhes
    for proibido in (SEGREDO_OBS, SEGREDO_TEXTO, RESP_LIVRE):
        assert proibido not in detalhes


# ---------------------------------------------------------------------------
# A2 — pedagógico altera: mesmo log, com o papel correto
# ---------------------------------------------------------------------------

def test_a2_pedagogico_altera_gera_log(client, app):
    ids = _seed(app)
    login_as(client, ids["pedagogico"], ids["un"])
    antes = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha=RESP_ESCOLHA, obs_escolha="Nova observacao",
        resp_livre=RESP_LIVRE, obs_livre="",
    )
    assert r.status_code == 302

    novos = _logs_novos(app, antes)
    assert len(novos) == 1
    log = novos[0]
    assert log.acao == ACAO_EDICAO_CONSELHO_GESTOR
    assert log.usuario_id == ids["pedagogico"]
    assert log.unidade_id == ids["un"]
    assert "papel=pedagogico" in log.detalhes
    assert f"observacao[p{ids['p_escolha']}]: texto alterado" in log.detalhes


# ---------------------------------------------------------------------------
# A3 — salvamento sem mudança: nenhum log novo
# ---------------------------------------------------------------------------

def test_a3_sem_mudanca_nao_gera_log(client, app):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])
    antes = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha=RESP_ESCOLHA, obs_escolha=OBS_INICIAL,
        resp_livre=RESP_LIVRE, obs_livre="",
    )
    assert r.status_code == 302
    assert _logs_novos(app, antes) == []


# ---------------------------------------------------------------------------
# A4 — professor da oferta salva: nenhum log do helper
# ---------------------------------------------------------------------------

def test_a4_professor_da_oferta_nao_gera_log(client, app):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])
    antes = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha="Sempre", obs_escolha="Ajuste do professor",
        resp_livre=RESP_LIVRE, obs_livre="",
    )
    assert r.status_code == 302

    novos = _logs_novos(app, antes)
    assert [log for log in novos if log.acao == ACAO_EDICAO_CONSELHO_GESTOR] == []
    # ConselhoResposta não é auditada pelo listener: nada é gravado.
    assert novos == []
    assert _resposta(app, ids["aluno"], ids["p_escolha"]).observacao == (
        "Ajuste do professor"
    )


# ---------------------------------------------------------------------------
# A5 — primeiro preenchimento por admin: tipo=preenchimento
# ---------------------------------------------------------------------------

def test_a5_primeiro_preenchimento_tem_tipo_preenchimento(client, app):
    ids = _seed(app)
    with app.app_context():
        for pergunta_id in (ids["p_escolha"], ids["p_livre"]):
            linha = ConselhoResposta.query.filter_by(
                aluno_id=ids["aluno"], pergunta_id=pergunta_id,
            ).one()
            linha.resposta = None
            linha.observacao = None
        db.session.commit()

    login_as(client, ids["admin"], ids["un"])
    antes = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha="Sempre", obs_escolha="",
        resp_livre="", obs_livre="",
    )
    assert r.status_code == 302

    novos = _logs_novos(app, antes)
    assert len(novos) == 1
    detalhes = novos[0].detalhes
    assert "tipo=preenchimento" in detalhes
    assert (
        f"resposta[p{ids['p_escolha']}]: (vazio) -> 'Sempre'" in detalhes
    )


# ---------------------------------------------------------------------------
# A6 — texto livre nunca aparece no log (resposta e observação)
# ---------------------------------------------------------------------------

def test_a6_texto_livre_nao_aparece_no_log(client, app):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])
    antes = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha=RESP_ESCOLHA,
        obs_escolha=SEGREDO_OBS,
        resp_livre=SEGREDO_TEXTO, obs_livre=SEGREDO_OBS,
    )
    assert r.status_code == 302

    novos = _logs_novos(app, antes)
    assert len(novos) == 1
    detalhes = novos[0].detalhes
    assert SEGREDO_OBS not in detalhes
    assert SEGREDO_TEXTO not in detalhes
    assert detalhes.count("texto alterado") == 3
    # Nenhum valor livre nem entre aspas/repr.
    assert re.search(r"SEGREDO", detalhes) is None


# ---------------------------------------------------------------------------
# A7 — outro professor continua barrado (403) e nada é gravado
# ---------------------------------------------------------------------------

def test_a7_outro_professor_recebe_403_e_nao_grava(client, app):
    ids = _seed(app)
    login_as(client, ids["outro_prof"], ids["un"])
    antes = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha="Sempre", obs_escolha="invasao",
        resp_livre="invasao", obs_livre="",
    )
    assert r.status_code == 403
    assert _logs_novos(app, antes) == []
    linha = _resposta(app, ids["aluno"], ids["p_escolha"])
    assert linha.resposta == RESP_ESCOLHA
    assert linha.observacao == OBS_INICIAL


# ---------------------------------------------------------------------------
# A8 — filtro de /admin/logs mostra o rótulo em `edicao`
# ---------------------------------------------------------------------------

def test_a8_filtro_admin_logs_exibe_rotulo_em_edicao(client, app):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])
    _salvar(
        client, ids, resp_escolha="Sempre", obs_escolha="Ajuste",
        resp_livre=RESP_LIVRE, obs_livre="",
    )

    edicao = client.get("/admin/logs?acao=edicao")
    assert edicao.status_code == 200
    corpo = edicao.get_data(as_text=True)
    assert ACAO_EDICAO_CONSELHO_GESTOR in corpo

    criacao = client.get("/admin/logs?acao=criacao")
    assert criacao.status_code == 200
    assert ACAO_EDICAO_CONSELHO_GESTOR not in criacao.get_data(as_text=True)


# ---------------------------------------------------------------------------
# A9 — golden: salvar sem mudança não altera a tela do lançamento
# ---------------------------------------------------------------------------

def test_a9_golden_lancamento_identico_em_salvamento_sem_mudanca(client, app):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])
    url = _url_lancamento(ids)

    antes_tela = client.get(url).get_data(as_text=True)
    antes_logs = _ids_logs(app)

    r = _salvar(
        client, ids, resp_escolha=RESP_ESCOLHA, obs_escolha=OBS_INICIAL,
        resp_livre=RESP_LIVRE, obs_livre="",
    )
    assert r.status_code == 302
    # Consome o flash do POST antes de comparar o HTML.
    client.get(url)
    depois_tela = client.get(url).get_data(as_text=True)

    assert antes_tela == depois_tela
    assert _logs_novos(app, antes_logs) == []
