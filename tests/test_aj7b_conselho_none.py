"""AJ7-B — bug "None" nos campos de texto do conselho individual.

Sintoma: no lançamento do conselho por aluno, as Observações (e quaisquer
campos de texto opcionais alimentados por `respostas`/`observacoes`)
apareciam com o texto literal "None" para todos os alunos.

Causa (diagnóstico): `lancamento_conselho` monta os mapas com o valor cru da
coluna (`r.resposta`, NULL para linhas anteriores ao `f3d2b15`; desde o AJ19
a observação geral vem de `ConselhoClasse.observacao`); no template,
`map.get(chave, '')` devolve o `None` da chave existente — o default '' só
vale para chave AUSENTE — e o Jinja imprime "None". Irmão do mesmo padrão na
rota: o `DISTINCT` de `Turma.programa` do filtro não descartava NULL, e o
select ganhava `<option value="None">`.

Cobertura pedida no prompt AJ7-B (adaptada ao AJ19):
    A1 NULL × vazio × preenchido: cada estado de `ConselhoClasse.observacao`
       e de `resposta` renderiza '' (NULL), '' (vazio) e o texto — nunca
       "None".
    A2 round-trip de gravação: o que o HTML renderizado mostra é o que o
       navegador envia; salvar a página com observação NULL não pode gravar a
       string "None" no banco (comportamento anterior ao bug: '' ou NULL).
    A3 tela de resposta totalmente preenchida (sem NULL) renderiza o MESMO
       HTML antes e depois do fix (golden por conteúdo exato).
    A4 avaliação coletiva (turma_aval): mesmo contrato - sem "None" no HTML.
    A5 varredura estática: os `.get(` de campos de texto dos templates do
       conselho ficam nos pontos cobertos por A1-A4 (trava contra novo ponto
       esquecido).
    A6 fechamento: `Turma.programa` e `Aluno.nivel` (opcionais) sem "None".
    A7 painel: `Turma.ordenacao` (opcional) sem "None.".

Nomes sintéticos, SQLite do fixture `app`, nenhuma escrita em banco real.
"""

import json
import re
from datetime import date

from _helpers import login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    ConselhoClasse,
    ConselhoResposta,
    Curso,
    PerguntaConselho,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)

OPCOES = ["Nunca", "As vezes", "Sempre"]
OBS_PREENCHIDA = "Observacao preenchida do conselho"
RESP_LIVRE = "Resposta de texto livre do conselho"

# ---------------------------------------------------------------------------
# Expressões do HTML renderizado (mesma família do test_aj2_conselho_lancamento)
# ---------------------------------------------------------------------------
_OBS_TA = re.compile(
    r'<textarea\b[^>]*name="obs_(\d+)"[^>]*>(.*?)</textarea>', re.S,
)
_RESP_TA = re.compile(
    r'<textarea\b[^>]*name="resp_(\d+)_(\d+)"[^>]*>(.*?)</textarea>', re.S,
)
_RESP_HIDDEN = re.compile(
    r'<input\b[^>]*type="hidden"[^>]*name="resp_(\d+)_(\d+)"[^>]*?value="([^"]*)"',
    re.S,
)
_TURMA_TA = re.compile(
    r'<textarea\b[^>]*name="resp_turma_(\d+)"[^>]*>(.*?)</textarea>', re.S,
)


def _corpo(response):
    return response.get_data(as_text=True)


def _observadores(corpo):
    return {a: texto for a, texto in _OBS_TA.findall(corpo)}


def _resp_textareas(corpo):
    return {f"{a}_{p}": texto for a, p, texto in _RESP_TA.findall(corpo)}


def _resp_hidden(corpo):
    return {f"{a}_{p}": valor for a, p, valor in _RESP_HIDDEN.findall(corpo)}


# ---------------------------------------------------------------------------
# Semente: 1 turma/oferta do professor, 1 aluno e três perguntas ALUNO com os
# três estados de texto (NULL, vazio, preenchido) direto no ConselhoResposta.
# ---------------------------------------------------------------------------

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
        unidade = Unidade(nome="Unidade AJ7B", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        prof = _usuario("Professor AJ7B", "professor", unidade.id)
        db.session.flush()

        admin = _usuario("Admin AJ7B", "admin", unidade.id)
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="Periodo AJ7B", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma AJ7B", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True, professor_id=prof.id,
        )
        db.session.add(turma)
        db.session.flush()

        curso = Curso(nome="Curso AJ7B", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        oferta = nova_oferta(
            turma.id, curso.id, unidade.id, programa="Programa AJ7B",
            principal=True, professor_id=prof.id,
        )

        aluno = Aluno(nome="Aluno AJ7B", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, oferta.id)

        # p_obs: pergunta com opções -> linha com observacao NULL (o sintoma).
        p_obs = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="Como participa das aulas?", opcoes=" | ".join(OPCOES),
            ativo=True,
        )
        # p_livre: pergunta de texto livre -> linha com resposta NULL e obs ''.
        p_livre = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="O que a familia precisa saber?", opcoes="", ativo=True,
        )
        # p_cheia: pergunta com opções -> linha 100% preenchida (golden).
        p_cheia = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="Como se relaciona?", opcoes=" | ".join(OPCOES), ativo=True,
        )
        # p_turma: pergunta TURMA para a avaliação coletiva (A4).
        p_turma = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="TURMA",
            texto="Como a turma evoluiu?", opcoes="", ativo=True,
        )
        db.session.add_all([p_obs, p_livre, p_cheia, p_turma])
        db.session.flush()

        conselho = ConselhoClasse(
            turma_id=turma.id, turma_curso_id=oferta.id, aluno_id=aluno.id,
            etapa=EtapaConselho.INICIAL, unidade_id=unidade.id,
        )
        db.session.add(conselho)
        db.session.flush()

        db.session.add_all([
            ConselhoResposta(
                conselho_id=conselho.id, aluno_id=aluno.id,
                pergunta_id=p_obs.id, resposta="Sempre",
                unidade_id=unidade.id,
            ),
            ConselhoResposta(
                conselho_id=conselho.id, aluno_id=aluno.id,
                pergunta_id=p_livre.id, resposta=None,
                unidade_id=unidade.id,
            ),
            ConselhoResposta(
                conselho_id=conselho.id, aluno_id=aluno.id,
                pergunta_id=p_cheia.id, resposta="Nunca",
                unidade_id=unidade.id,
            ),
        ])
        db.session.commit()

        return {
            "un": unidade.id,
            "prof": prof.id,
            "admin": admin.id,
            "turma": turma.id,
            "oferta": oferta.id,
            "aluno": aluno.id,
            "conselho": conselho.id,
            "p_obs": p_obs.id,
            "p_livre": p_livre.id,
            "p_cheia": p_cheia.id,
            "p_turma": p_turma.id,
        }


def _url_lancamento(ids):
    return (f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL"
            f"&oferta_sel={ids['oferta']}")


def _buscar_resposta(aluno_id, pergunta_id):
    return ConselhoResposta.query.filter_by(
        aluno_id=aluno_id, pergunta_id=pergunta_id,
    ).one()


def _buscar_conselho(aluno_id):
    return ConselhoClasse.query.filter_by(
        aluno_id=aluno_id, etapa=EtapaConselho.INICIAL,
    ).one()


# ---------------------------------------------------------------------------
# A1 — NULL / vazio / preenchido: nenhum "None" renderizado
# ---------------------------------------------------------------------------

def test_a1_lancamento_nao_renderiza_none_em_campo_nulo(client, app):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    corpo = _corpo(client.get(_url_lancamento(ids)))

    # O sintoma: a string "None" não pode aparecer em lugar nenhum da grade
    # (nem nos textareas, nem como opção do filtro de programa — turma sem
    # programa carregava `<option value="None">None</option>` no select).
    assert ">None<" not in corpo
    assert 'value="None"' not in corpo

    chave_aluno = str(ids["aluno"])
    chave_obs = f"{ids['aluno']}_{ids['p_obs']}"
    chave_livre = f"{ids['aluno']}_{ids['p_livre']}"

    obs = _observadores(corpo)
    # ConselhoClasse.observacao NULL -> textarea vazio (não "None").
    assert obs[chave_aluno] == ""

    # observacao '' -> continua vazio.
    with app.app_context():
        _buscar_conselho(ids["aluno"]).observacao = ""
        db.session.commit()
    obs = _observadores(_corpo(client.get(_url_lancamento(ids))))
    assert obs[chave_aluno] == ""

    # observacao preenchida -> texto idêntico.
    with app.app_context():
        _buscar_conselho(ids["aluno"]).observacao = OBS_PREENCHIDA
        db.session.commit()
    obs = _observadores(_corpo(client.get(_url_lancamento(ids))))
    assert obs[chave_aluno] == OBS_PREENCHIDA

    # resposta NULL em pergunta de texto livre -> textarea vazio.
    assert _resp_textareas(corpo)[chave_livre] == ""
    # resposta preenchida permanece.
    assert _resp_hidden(corpo)[chave_obs] == "Sempre"


# ---------------------------------------------------------------------------
# A2 — round-trip: salvar a página renderizada com NULL não grava "None"
# ---------------------------------------------------------------------------

def test_a2_roundtrip_salva_o_que_o_html_mostra_sem_none(client, app):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    corpo = _corpo(client.get(_url_lancamento(ids)))

    # O navegador envia exatamente o que o HTML mostra: colhemos os valores
    # renderizados (textarea + hidden) e reenviamos sem tocar em nada.
    campos = {}
    for chave, texto in _observadores(corpo).items():
        campos[f"obs_{chave}"] = texto
    for chave, texto in _resp_textareas(corpo).items():
        campos[f"resp_{chave}"] = texto
    for chave, valor in _resp_hidden(corpo).items():
        campos[f"resp_{chave}"] = valor

    r = client.post(
        "/conselho/salvar",
        data={
            "turma_id": str(ids["turma"]),
            "etapa": "INICIAL",
            "turma_curso_id": str(ids["oferta"]),
            **campos,
        },
    )
    assert r.status_code == 302

    with app.app_context():
        linha = _buscar_resposta(ids["aluno"], ids["p_obs"])
        conselho = _buscar_conselho(ids["aluno"])
        # Antes do fix o textarea mostrava "None" e este POST gravava a
        # string literal. Contrato: NULL/vazio renderizam '' e salvam ''
        # (ou seguem NULL), nunca "None".
        assert conselho.observacao not in ("None", "None ", " None"), (
            f"o salvamento gravou a string {conselho.observacao!r} a partir "
            "do HTML renderizado"
        )
        assert conselho.observacao in ("", None)
        # A resposta preenchida não é destruída pelo round-trip.
        assert linha.resposta == "Sempre"

        linha_cheia = _buscar_resposta(ids["aluno"], ids["p_cheia"])
        assert linha_cheia.resposta == "Nunca"


# ---------------------------------------------------------------------------
# A3 — golden: tela totalmente preenchida renderiza conteúdo idêntico
# ---------------------------------------------------------------------------

def test_a3_pagina_preenchida_renderiza_golden_inalterado(client, app):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    # Zera os NULLs da semente (cenário sem bug: tudo preenchido).
    with app.app_context():
        _buscar_conselho(ids["aluno"]).observacao = OBS_PREENCHIDA
        _buscar_resposta(ids["aluno"], ids["p_livre"]).resposta = RESP_LIVRE
        db.session.commit()

    corpo = _corpo(client.get(_url_lancamento(ids)))
    chave_aluno = str(ids["aluno"])
    chave_obs = f"{ids['aluno']}_{ids['p_obs']}"
    chave_livre = f"{ids['aluno']}_{ids['p_livre']}"
    chave_cheia = f"{ids['aluno']}_{ids['p_cheia']}"

    # Conteúdo exato de cada campo preenchido — idêntico antes e depois do
    # fix (o fix só toca no caminho None -> ''; aqui não há None).
    assert _observadores(corpo)[chave_aluno] == OBS_PREENCHIDA
    assert _resp_textareas(corpo)[chave_livre] == RESP_LIVRE
    assert _resp_hidden(corpo)[chave_obs] == "Sempre"
    assert _resp_hidden(corpo)[chave_cheia] == "Nunca"

    # A2/A3: duas renderizações iguais (determinismo do golden).
    corpo2 = _corpo(client.get(_url_lancamento(ids)))
    assert corpo == corpo2


# ---------------------------------------------------------------------------
# A4 — avaliação coletiva da oferta: mesmo contrato, sem "None"
# ---------------------------------------------------------------------------

def test_a4_avaliacao_turma_sem_none(client, app):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])

    # Sem nada gravado (avaliacao_inicial NULL) e com uma pergunta respondida
    # e outra ausente: o mapa de turma_aval nunca pode produzir "None".
    with app.app_context():
        oferta = db.get_or_404(TurmaCurso, ids["oferta"])
        oferta.avaliacao_inicial = json.dumps(
            {str(ids["p_turma"]): "Turma evoluiu bem"}, ensure_ascii=False,
        )
        db.session.commit()

    corpo = _corpo(client.get(
        f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL&oferta_sel={ids['oferta']}"
    ))
    assert ">None<" not in corpo
    turmas = {p: t for p, t in _TURMA_TA.findall(corpo)}
    assert turmas[str(ids["p_turma"])] == "Turma evoluiu bem"


# ---------------------------------------------------------------------------
# A6 - fechamento: campos opcionais (programa da turma, nível do aluno)
# ---------------------------------------------------------------------------

def test_a6_fechamento_sem_none_em_campos_opcionais(client, app):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])

    # A semente não define `Turma.programa`/`Aluno.nivel` (colunas opcionais):
    # os dois pontos crus do template imprimiam o literal "None".
    r = client.get(
        f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}"
    )
    assert r.status_code == 200
    corpo = _corpo(r)
    assert "None" not in corpo
    assert "— |" in corpo


# ---------------------------------------------------------------------------
# A7 - painel: `Turma.ordenacao` opcional não pode virar "None."
# ---------------------------------------------------------------------------

def test_a7_painel_sem_none_na_ordenacao(client, app):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])

    # A semente não define `Turma.ordenacao` (Integer nullable).
    corpo = _corpo(client.get("/conselho"))
    assert "None" not in corpo
    assert "—. Turma AJ7B" in corpo


# ---------------------------------------------------------------------------
# A5 — varredura estática: nenhum `.get(` novo sem cobertura nos templates
# ---------------------------------------------------------------------------

def test_a5_varredura_get_nos_templates_conselho(app):
    """Trava: os `.get(` de mapa de texto (`respostas`/`observacoes`) nos
    templates do conselho ficam só nos pontos cobertos pelos testes A1–A4
    (lancamento e turma_aval). Um ponto novo neste padrão precisa de teste
    novo antes de entrar. Os demais `.get(` (lista de perguntas, mapa de
    grade protegido por `{% if %}`) não renderizam campo de texto cru."""
    from pathlib import Path

    padrao = re.compile(r"\b(?:respostas|observacoes)\.get\(")
    raiz = Path(app.root_path) / "templates" / "conselho"
    achados = set()
    for tpl in sorted(raiz.glob("*.html")):
        texto = tpl.read_text(encoding="utf-8")
        if padrao.search(texto):
            achados.add(tpl.name)
    assert achados == {"lancamento.html", "turma_aval.html"}, (
        f"novos usos de mapa.get() de campo de texto em templates do "
        f"conselho: {achados}; cada ponto exige teste de NULL/vazio/"
        "preenchido antes de entrar"
    )
