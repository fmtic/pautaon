"""AJ21-B — página única do resumo do conselho (individual + coletivo).

Cobertura:
    R1  perfis: 200 admin/pedagogico/secretaria; 403 professor e demais;
        404 turma de outra unidade.
    R2  rota única: a antiga `/turma/<id>/avaliacao/resumo` não existe mais
        (404 no cliente e BuildError no url_for), sem resquícios nos templates.
    R3  página traz individual e coletivo juntos; somente perguntas com
        resposta salva; somente a alternativa ESCOLHIDA (com a letra).
    R4  observação do aluno e observação coletiva (`_obs`) aparecem escapadas
        e com quebras de linha preservadas.
    R5  nome social tem prioridade; autor da última gravação é discreto.
    R6  botão "Editar" por aluno e "Editar avaliação da turma" só para
        admin/pedagogico; secretaria vê a página sem ações de escrita.
    R7  seletor de etapa preserva `turma_curso_id`; FINAL funciona.
    R8  GET nunca cria ConselhoClasse; oferta 2+ sem `turma_curso_id` recusa;
        pergunta inativa com resposta salva aparece.
    R9  sem foto de aluno em nenhum ponto da página.
    R10 contagem de queries constante com o número de alunos (sem N+1).
    R11 "Ver respostas" em lancamento/turma_aval e link do painel apontam para
        a rota nova, só para os 3 perfis, com target=_blank rel=noopener.
"""
import json
import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import event
from werkzeug.routing import BuildError

from app import db
from app.models import (
    Aluno,
    ConselhoClasse,
    ConselhoResposta,
    Curso,
    Inscricao,
    PerguntaConselho,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho
from _helpers import login_as, nova_inscricao, nova_oferta
from test_conselho_oferta import _setup

_URL_RESUMO = "/conselho/resumo/{turma}?etapa={etapa}&turma_curso_id={oferta}"
_URL_ANTIGA = "/turma/{turma}/avaliacao/resumo?etapa={etapa}&turma_curso_id={oferta}"

_ROLES_LEITURA = ("admin", "pedagogico", "secretaria")
# `pendente` é interceptado antes da rota pelo guard global (vai para a tela
# de aprovação); os demais perfis ativos chegam à rota e recebem 403.
_ROLES_SEM_LEITURA = ("professor", "gerencia", "servico_social")

_CAMPOS_ETAPA = {
    "INICIAL": "avaliacao_inicial",
    "PERCURSO": "avaliacao_percurso",
    "FINAL": "avaliacao_final",
}


def _cenario(app, *, role="admin", ofertas=1):
    """Semeia o cenário do conselho com perguntas de INICIAL e FINAL."""
    ids = _setup(app, ofertas=ofertas, role=role)

    with app.app_context():
        usuario = db.session.get(User, ids["user_id"])
        usuario.unidade_id = ids["un_a"]
        periodo = PeriodoLetivo.query.filter_by(unidade_id=ids["un_a"]).first()
        ids["periodo"] = periodo.id
        # `_setup` monta a turma antes de o período ter id; aqui o vínculo
        # explícito garante `turma.periodo_letivo` nas telas de resumo/painel.
        turma = db.session.get(Turma, ids["turma"])
        turma.periodo_letivo_id = periodo.id

        p_inicial_aluno = PerguntaConselho(
            etapa=EtapaConselho.INICIAL,
            tipo="ALUNO",
            texto="Como o aluno participa das aulas?",
            opcoes="Sempre | Às vezes | Nunca",
            ativo=True,
        )
        p_inicial_aluno_2 = PerguntaConselho(
            etapa=EtapaConselho.INICIAL,
            tipo="ALUNO",
            texto="O aluno entrega as tarefas?",
            opcoes="Sim | Não",
            ativo=True,
        )
        p_inicial_turma = PerguntaConselho(
            etapa=EtapaConselho.INICIAL,
            tipo="TURMA",
            texto="Como a turma evoluiu?",
            opcoes="Boa | Regular | Ruim",
            ativo=True,
        )
        p_inicial_turma_2 = PerguntaConselho(
            etapa=EtapaConselho.INICIAL,
            tipo="TURMA",
            texto="A turma participa dos projetos?",
            opcoes="Sim | Não",
            ativo=True,
        )
        p_final_aluno = PerguntaConselho(
            etapa=EtapaConselho.FINAL,
            tipo="ALUNO",
            texto="Como foi o semestre?",
            opcoes="Avançou | Parcial",
            ativo=True,
        )
        p_final_turma = PerguntaConselho(
            etapa=EtapaConselho.FINAL,
            tipo="TURMA",
            texto="Avaliação final da turma",
            opcoes="Sim | Não",
            ativo=True,
        )
        db.session.add_all([
            p_inicial_aluno,
            p_inicial_aluno_2,
            p_inicial_turma,
            p_inicial_turma_2,
            p_final_aluno,
            p_final_turma,
        ])
        db.session.flush()
        ids["p_inicial_aluno"] = p_inicial_aluno.id
        ids["p_inicial_aluno_2"] = p_inicial_aluno_2.id
        ids["p_inicial_turma"] = p_inicial_turma.id
        ids["p_inicial_turma_2"] = p_inicial_turma_2.id
        ids["p_final_aluno"] = p_final_aluno.id
        ids["p_final_turma"] = p_final_turma.id
        db.session.commit()

    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_b", oferta_idx=0)
    return ids


def _enturma(app, ids, aluno_key, oferta_idx=0):
    with app.app_context():
        nova_inscricao(
            ids[aluno_key], ids["turma"], ids["ofertas"][oferta_idx]
        )
        db.session.commit()


def _login(client, ids, role="admin"):
    if role == "professor":
        login_as(client, ids["prof"], ids["un_a"])
    else:
        login_as(client, ids["user_id"], ids["un_a"])


def _gravar_resposta_direto(
    app,
    ids,
    *,
    etapa="INICIAL",
    aluno_key="aluno_a",
    pergunta_id,
    resposta,
    autor_nome="Testador",
    oferta_idx=0,
):
    """Insere (ou atualiza) uma resposta e devolve o id do ConselhoClasse."""
    with app.app_context():
        aluno_id = ids[aluno_key]
        oferta_id = ids["ofertas"][oferta_idx]
        conselho = ConselhoClasse.query.filter_by(
            turma_id=ids["turma"],
            turma_curso_id=oferta_id,
            aluno_id=aluno_id,
            etapa=etapa,
        ).first()
        if conselho is None:
            conselho = ConselhoClasse(
                turma_id=ids["turma"],
                turma_curso_id=oferta_id,
                aluno_id=aluno_id,
                etapa=etapa,
                unidade_id=ids["un_a"],
                observacao="",
            )
            db.session.add(conselho)
            db.session.flush()

        resp = ConselhoResposta.query.filter_by(
            conselho_id=conselho.id,
            aluno_id=aluno_id,
            pergunta_id=pergunta_id,
        ).first()
        if resp is None:
            resp = ConselhoResposta(
                conselho_id=conselho.id,
                aluno_id=aluno_id,
                pergunta_id=pergunta_id,
                unidade_id=ids["un_a"],
            )
            db.session.add(resp)
        resp.resposta = resposta
        resp.autor_nome = autor_nome
        db.session.commit()
        return conselho.id


def _definir_observacao(app, conselho_id, texto):
    with app.app_context():
        conselho = db.session.get(ConselhoClasse, conselho_id)
        conselho.observacao = texto
        db.session.commit()


def _gravar_coletivo(app, ids, *, etapa="INICIAL", respostas, oferta_idx=0):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["ofertas"][oferta_idx])
        setattr(
            oferta,
            _CAMPOS_ETAPA[etapa],
            json.dumps(respostas, ensure_ascii=False),
        )
        db.session.commit()


def _url_resumo(ids, *, etapa="INICIAL", oferta_idx=0, aluno_id=None):
    url = _URL_RESUMO.format(
        turma=ids["turma"],
        etapa=etapa,
        oferta=ids["ofertas"][oferta_idx],
    )
    if aluno_id is not None:
        url += f"&aluno_id={aluno_id}"
    return url


def _url_antiga(ids, *, etapa="INICIAL", oferta_idx=0):
    return _URL_ANTIGA.format(
        turma=ids["turma"],
        etapa=etapa,
        oferta=ids["ofertas"][oferta_idx],
    )


def _contar_conselhos(app):
    with app.app_context():
        return ConselhoClasse.query.count()


def _html(client, ids, **kwargs):
    resposta = client.get(_url_resumo(ids, **kwargs))
    assert resposta.status_code == 200
    return resposta.data.decode("utf-8")


# ---------------------------------------------------------------------------
# R1 — perfis e isolamento por unidade
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", _ROLES_LEITURA)
def test_r1_resumo_200_para_roles_leitura(client, app, role):
    ids = _cenario(app, role=role)
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    _login(client, ids, role)
    assert client.get(_url_resumo(ids)).status_code == 200


@pytest.mark.parametrize("role", _ROLES_SEM_LEITURA)
def test_r1_resumo_403_para_outros_perfis(client, app, role):
    ids = _cenario(app, role=role)
    _login(client, ids, role)
    assert client.get(_url_resumo(ids)).status_code == 403


def test_r1_resumo_404_turma_outra_unidade(client, app):
    ids = _cenario(app, role="admin")
    with app.app_context():
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add(un_b)
        db.session.flush()
        periodo_b = PeriodoLetivo(
            nome="Periodo B",
            data_inicio=date(2026, 2, 2),
            data_fim=date(2026, 6, 30),
            unidade_id=un_b.id,
            ativo=True,
        )
        db.session.add(periodo_b)
        turma_b = Turma(
            nome="Turma Alheia",
            turno="Manhã",
            data_inicio=date(2026, 2, 2),
            data_fim=date(2026, 6, 30),
            periodo_letivo_id=periodo_b.id,
            unidade_id=un_b.id,
            ativo=True,
        )
        db.session.add(turma_b)
        db.session.commit()
        id_turma_b = turma_b.id

    _login(client, ids, "admin")
    r = client.get(
        f"/conselho/resumo/{id_turma_b}?etapa=INICIAL"
        f"&turma_curso_id={ids['ofertas'][0]}"
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# R2 — rota única; a antiga foi removida sem redirecionamento
# ---------------------------------------------------------------------------

def test_r2_rota_antiga_nao_existe_e_nao_redireciona(client, app):
    ids = _cenario(app, role="admin")
    _login(client, ids, "admin")
    r = client.get(_url_antiga(ids))
    assert r.status_code == 404, "a rota antiga não pode existir nem redirecionar"


def test_r2_url_for_antigo_levanta_build_error(app):
    with app.test_request_context():
        with pytest.raises(BuildError):
            from flask import url_for

            url_for("conselho.resumo_avaliacao_turma", turma_id=1)


def test_r2_templates_sem_url_for_antigo(app):
    raiz = Path(app.root_path) / "templates"
    achados = []
    for tpl in raiz.rglob("*.html"):
        texto = tpl.read_text(encoding="utf-8")
        if "resumo_avaliacao" in texto:
            achados.append(str(tpl))
    assert achados == [], f"resquícios da rota antiga: {achados}"


def test_r2_url_for_novo_funciona(app):
    with app.test_request_context():
        from flask import url_for

        url = url_for(
            "conselho.resumo_conselho", turma_id=7, etapa="FINAL",
            turma_curso_id=9,
        )
    assert url.startswith("/conselho/resumo/7")
    assert "etapa=FINAL" in url
    assert "turma_curso_id=9" in url


# ---------------------------------------------------------------------------
# R3 — individual + coletivo juntos; só a alternativa escolhida
# ---------------------------------------------------------------------------

def test_r3_pagina_unica_traz_individual_e_coletivo(client, app):
    ids = _cenario(app, role="admin")
    conselho_id = _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Às vezes",
    )
    _definir_observacao(app, conselho_id, "Observação individual.")
    _gravar_coletivo(
        app, ids,
        respostas={
            str(ids["p_inicial_turma"]): "Boa",
            str(ids["p_inicial_turma_2"]): "Sim",
            "_obs": "Observação coletiva.",
        },
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    assert "Resumo do Conselho de Classe" in html
    assert "Avaliação individual dos alunos" in html
    assert "Avaliação coletiva do curso (oferta)" in html
    # Individual: pergunta + alternativa escolhida com a letra.
    assert "Como o aluno participa das aulas?" in html
    assert "B) Às vezes" in html
    assert "Observação individual." in html
    # Coletivo: pergunta + alternativa escolhida com a letra.
    assert "Como a turma evoluiu?" in html
    assert "A) Boa" in html
    assert "A turma participa dos projetos?" in html
    assert "A) Sim" in html
    assert "Observação coletiva." in html


def test_r3_opcoes_nao_escolhidas_nao_aparecem(client, app):
    ids = _cenario(app, role="admin")
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    _gravar_coletivo(
        app, ids, respostas={str(ids["p_inicial_turma"]): "Boa"},
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    # Individual: "Às vezes" e "Nunca" são alternativas não escolhidas.
    assert "A) Sempre" in html
    assert "Às vezes" not in html
    assert "Nunca" not in html
    # Coletivo: "Regular" e "Ruim" são alternativas não escolhidas.
    assert "A) Boa" in html
    assert "Regular" not in html
    assert "Ruim" not in html


def test_r3_pergunta_sem_resposta_nao_aparece(client, app):
    ids = _cenario(app, role="admin")
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    # Pergunta TURMA sem resposta salva não pode virar linha do coletivo.
    _gravar_coletivo(
        app, ids, respostas={str(ids["p_inicial_turma"]): "Boa"},
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    assert "O aluno entrega as tarefas?" not in html
    assert "A turma participa dos projetos?" not in html


def test_r3_resposta_dissertativa_sem_letra(client, app):
    ids = _cenario(app, role="admin")
    with app.app_context():
        pergunta = db.session.get(PerguntaConselho, ids["p_inicial_aluno_2"])
        pergunta.opcoes = None
        db.session.commit()
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno_2"],
        resposta="Texto livre do professor.",
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    assert "O aluno entrega as tarefas?" in html
    assert "Texto livre do professor." in html
    assert "A) Texto livre do professor." not in html


# ---------------------------------------------------------------------------
# R4 — escape e quebras de linha nas observações
# ---------------------------------------------------------------------------

def test_r4_observacao_individual_escapada_e_com_quebras(client, app):
    ids = _cenario(app, role="admin")
    conselho_id = _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="<b>forte</b>",
    )
    _definir_observacao(
        app, conselho_id, "<script>alert('x')</script>\nlinha 2"
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    assert "<script>alert('x')</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>forte</b>" not in html
    assert "&lt;b&gt;forte&lt;/b&gt;" in html
    assert "linha 2" in html
    assert "white-space: pre-line" in html


def test_r4_observacao_coletiva_escapada_e_com_quebras(client, app):
    ids = _cenario(app, role="admin")
    _gravar_coletivo(
        app, ids,
        respostas={
            str(ids["p_inicial_turma"]): "Boa",
            "_obs": "<b>turma</b>\nsegunda linha",
        },
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    assert "&lt;b&gt;turma&lt;/b&gt;" in html
    assert "<b>turma</b>" not in html
    assert "segunda linha" in html
    # `_obs` é chave reservada: não vira pergunta nem aparece crua.
    assert "_obs" not in html


# ---------------------------------------------------------------------------
# R5 — nome social e autor da última gravação
# ---------------------------------------------------------------------------

def test_r5_nome_social_tem_prioridade(client, app):
    ids = _cenario(app, role="admin")
    with app.app_context():
        aluno = db.session.get(Aluno, ids["aluno_a"])
        aluno.nome_social = "Ana Social"
        db.session.commit()
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
        autor_nome="Professora Maria",
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    assert "Ana Social" in html
    assert "Aluno Ana" not in html
    assert "Professora Maria" in html


# ---------------------------------------------------------------------------
# R6 — ações de escrita só para admin/pedagogico
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", ("admin", "pedagogico"))
def test_r6_admin_e_pedagogico_veem_editar(client, app, role):
    ids = _cenario(app, role=role)
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    _login(client, ids, role)
    html = _html(client, ids)

    assert "Editar avaliação da turma" in html
    assert re.search(r">\s*Editar\s*</a>", html)
    assert f"#aluno-{ids['aluno_a']}" in html
    assert f"#aluno-{ids['aluno_b']}" in html


def test_r6_secretaria_nao_ve_editar(client, app):
    ids = _cenario(app, role="secretaria")
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    _login(client, ids, "secretaria")
    html = _html(client, ids)

    assert "Editar avaliação da turma" not in html
    assert not re.search(r">\s*Editar\s*</a>", html)
    assert "#aluno-" not in html


# ---------------------------------------------------------------------------
# R7 — seletor de etapa preserva a oferta; FINAL funciona
# ---------------------------------------------------------------------------

def test_r7_seletor_de_etapa_preserva_turma_curso_id(client, app):
    ids = _cenario(app, role="admin")
    _login(client, ids, "admin")
    html = _html(client, ids)

    for etapa in ("INICIAL", "PERCURSO", "FINAL"):
        assert re.search(
            rf'href="/conselho/resumo/{ids["turma"]}\?etapa={etapa}'
            rf'&(?:amp;)?turma_curso_id={ids["ofertas"][0]}"',
            html,
        ), f"seletor deveria preservar a oferta na etapa {etapa}"


def test_r7_final_individual_e_coletivo(client, app):
    ids = _cenario(app, role="admin")
    _gravar_resposta_direto(
        app, ids, etapa="FINAL",
        pergunta_id=ids["p_final_aluno"], resposta="Avançou",
    )
    _gravar_coletivo(
        app, ids, etapa="FINAL",
        respostas={str(ids["p_final_turma"]): "Sim"},
    )
    _login(client, ids, "admin")
    html = _html(client, ids, etapa="FINAL")

    assert "Como foi o semestre?" in html
    assert "A) Avançou" in html
    assert "Avaliação final da turma" in html
    assert "A) Sim" in html


# ---------------------------------------------------------------------------
# R8 — GET não escreve; oferta 2+; pergunta inativa
# ---------------------------------------------------------------------------

def test_r8_get_nao_cria_conselho_classe(client, app):
    ids = _cenario(app, role="admin")
    _login(client, ids, "admin")
    antes = _contar_conselhos(app)
    assert client.get(_url_resumo(ids)).status_code == 200
    depois = _contar_conselhos(app)
    assert depois == antes, "GET do resumo não pode criar ConselhoClasse"


def test_r8_get_nao_altera_avaliacao_coletiva(client, app):
    ids = _cenario(app, role="admin")
    _gravar_coletivo(
        app, ids, respostas={str(ids["p_inicial_turma"]): "Boa"},
    )
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        antes = oferta.avaliacao_inicial
    _login(client, ids, "admin")
    assert client.get(_url_resumo(ids)).status_code == 200
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        assert oferta.avaliacao_inicial == antes


def test_r8_duas_ofertas_sem_escolha_recusa(client, app):
    ids = _cenario(app, role="admin", ofertas=2)
    _login(client, ids, "admin")
    r = client.get(f"/conselho/resumo/{ids['turma']}?etapa=INICIAL")
    assert r.status_code == 404


def test_r8_pergunta_inativa_com_resposta_aparece(client, app):
    ids = _cenario(app, role="admin")
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    with app.app_context():
        pergunta = db.session.get(PerguntaConselho, ids["p_inicial_aluno"])
        pergunta.ativo = False
        db.session.commit()

    _login(client, ids, "admin")
    html = _html(client, ids)
    assert "Como o aluno participa das aulas?" in html
    assert "inativa" in html


# ---------------------------------------------------------------------------
# R9 — sem foto de aluno
# ---------------------------------------------------------------------------

def test_r9_resumo_nao_carrega_foto_de_aluno(client, app):
    ids = _cenario(app, role="admin")
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    _login(client, ids, "admin")
    html = _html(client, ids)

    assert "foto_aluno" not in html
    assert "registros/foto" not in html
    assert not re.search(r'<img[^>]+aluno', html, re.IGNORECASE)


# ---------------------------------------------------------------------------
# R10 — contagem de queries constante (sem N+1 por aluno)
# ---------------------------------------------------------------------------

def _contar_queries(client, url):
    consultas = []

    def _registrar(conn, cursor, statement, parameters, context, many):
        consultas.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", _registrar)
    try:
        assert client.get(url).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _registrar)
    return len(consultas)


def test_r10_queries_nao_variam_com_numero_de_alunos(client, app):
    ids = _cenario(app, role="admin")
    _gravar_resposta_direto(
        app, ids, etapa="INICIAL",
        pergunta_id=ids["p_inicial_aluno"], resposta="Sempre",
    )
    _gravar_coletivo(
        app, ids, respostas={str(ids["p_inicial_turma"]): "Boa"},
    )
    _login(client, ids, "admin")
    url = _url_resumo(ids)

    com_dois = _contar_queries(client, url)

    with app.app_context():
        for numero in range(5):
            aluno = Aluno(
                nome=f"Aluno Extra {numero}",
                unidade_id=ids["un_a"],
                ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, ids["turma"], ids["ofertas"][0])
        db.session.commit()

    com_sete = _contar_queries(client, url)
    assert com_sete == com_dois, (
        f"resumo não pode fazer N+1 por aluno: {com_dois} queries com 2 "
        f"alunos e {com_sete} com 7"
    )


# ---------------------------------------------------------------------------
# R11 — "Ver respostas" nas telas de lançamento/avaliação e painel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("role", _ROLES_LEITURA)
def test_r11_lancamento_mostra_botao_para_roles_leitura(client, app, role):
    ids = _cenario(app, role=role)
    _login(client, ids, role)
    r = client.get(
        f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL"
        f"&oferta_sel={ids['ofertas'][0]}"
    )
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert f"/conselho/resumo/{ids['turma']}" in html
    assert 'target="_blank" rel="noopener"' in html


def test_r11_lancamento_sem_botao_para_professor(client, app):
    ids = _cenario(app, role="professor")
    _login(client, ids, "professor")
    r = client.get(
        f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL"
        f"&oferta_sel={ids['ofertas'][0]}"
    )
    assert r.status_code == 200
    assert f"/conselho/resumo/{ids['turma']}" not in r.data.decode("utf-8")


@pytest.mark.parametrize("role", _ROLES_LEITURA)
def test_r11_turma_aval_mostra_botao_para_roles_leitura(client, app, role):
    ids = _cenario(app, role=role)
    _login(client, ids, role)
    r = client.get(
        f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL"
        f"&oferta_sel={ids['ofertas'][0]}"
    )
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert f"/conselho/resumo/{ids['turma']}" in html
    assert 'target="_blank" rel="noopener"' in html


def test_r11_turma_aval_sem_botao_para_professor(client, app):
    ids = _cenario(app, role="professor")
    _login(client, ids, "professor")
    r = client.get(
        f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL"
        f"&oferta_sel={ids['ofertas'][0]}"
    )
    assert r.status_code == 200
    assert f"/conselho/resumo/{ids['turma']}" not in r.data.decode("utf-8")


def test_r11_painel_link_novo_e_sem_link_coletivo_separado(client, app):
    ids = _cenario(app, role="admin", ofertas=2)
    _gravar_resposta_direto(
        app, ids, etapa="FINAL",
        pergunta_id=ids["p_final_aluno"], resposta="Avançou",
    )
    with app.app_context():
        oferta_1 = db.session.get(TurmaCurso, ids["ofertas"][0])
        oferta_1.avaliacao_final = json.dumps(
            {str(ids["p_final_turma"]): "Sim"}, ensure_ascii=False
        )
        # A segunda oferta tem SOMENTE avaliação coletiva, sem ConselhoClasse.
        oferta_2 = db.session.get(TurmaCurso, ids["ofertas"][1])
        oferta_2.avaliacao_final = json.dumps(
            {str(ids["p_final_turma"]): "Não"}, ensure_ascii=False
        )
        db.session.commit()

    _login(client, ids, "admin")
    r = client.get(
        f"/relatorios/painel?turma_id={ids['turma']}"
        f"&periodo_letivo_id={ids['periodo']}"
    )
    assert r.status_code == 200
    html = r.data.decode("utf-8")

    assert "Ver respostas — Final" in html
    assert (
        f"/conselho/resumo/{ids['turma']}?etapa=FINAL"
        f"&amp;turma_curso_id={ids['ofertas'][0]}" in html
        or f"/conselho/resumo/{ids['turma']}?etapa=FINAL"
        f"&turma_curso_id={ids['ofertas'][0]}" in html
    )
    assert f"turma_curso_id={ids['ofertas'][1]}" in html
    # Link separado da avaliação coletiva foi unificado em "Ver respostas".
    assert "Ver avaliação coletiva" not in html
    # Lista com rótulo da opção + contagem continua no painel.
    assert re.search(
        r"Avançou</span>:\s*<span class=\"fw-bold\">1</span>", html
    ), "painel deveria listar a opção com sua contagem"
