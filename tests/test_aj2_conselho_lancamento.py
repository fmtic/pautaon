"""AJ2 bloco A — lançamento do conselho: resposta e observação separadas.

Cobre o commit `f3d2b15 fix(conselho): separa resposta e observacao no
lancamento` e o `9794165` (cor das perguntas / nome_exibicao fica no AJ2-E4),
substituindo o placeholder do AJ2 pela cobertura real pedida no prompt AJ3:

    T1 GET: perguntas com opções renderizam o controle de resposta
       `resp_<aluno>_<pergunta>` (input hidden + botões) e um
       `textarea obs_<aluno>_<pergunta>` separado; nenhum valor de opção
       aparece dentro do textarea de observação.
    T2 POST `resp_` + `obs_` grava `resposta` (valor puro da opção) e
       `observacao` (texto livre) em colunas distintas; o GET seguinte mostra
       a alternativa marcada e o texto no textarea.
    T3 `obs_` enviado vazio não recebe a alternativa.
    T4 `obs_` ausente do POST preserva a observação gravada; `obs_` vazio
       enviado de propósito limpa (comportamento do código atual).
    T5 pergunta de texto livre continua gravando o texto em `resposta`
       (sem regressão em relação ao que existed antes do `f3d2b15`).
    T6 regressões do entorno: oferta encerrada bloqueia sem gravar, professor
       de outra oferta leva 403, autor do lançamento (F1) só troca com mudança
       de conteúdo e a avaliação coletiva abre/grava como antes.
    T7 contraste WCAG da cor das perguntas (`--conselho-pergunta-cor`) contra
       branco, com a fórmula de luminância relativa.
    T8 o `conselho.js` e o handler inline do botão de alternativa não escrevem
       em `obs_`: prova textual + comportamento real executado em node.

Semente reaproveitada de `tests/test_conselho_professor.py` (professor da
OFERTA, duas turmas cruzadas), com uma pergunta ALUNO de opções, uma ALUNO de
texto livre e uma TURMA.
"""

import html
import json
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

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

OPCOES = ["Nunca", "Às vezes", "Sempre"]
TEXTO_OPCAO_MARCADA = "Sempre"

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATE_LANCAMENTO = RAIZ / "app" / "templates" / "conselho" / "lancamento.html"
JS_CONSELHO = RAIZ / "app" / "static" / "js" / "conselho" / "conselho.js"

# ---------------------------------------------------------------------------
# Expressões do HTML renderizado (o template quebra os atributos em várias
# linhas, daí re.S em tudo; nenhuma aspa dupla aparece dentro do onclick,
# então o valor do atributo é capturado com [^"]*).
# ---------------------------------------------------------------------------
_OBS_TA = re.compile(
    r'<textarea\b[^>]*name="obs_(\d+)_(\d+)"[^>]*>(.*?)</textarea>', re.S,
)
_RESP_TA = re.compile(
    r'<textarea\b[^>]*name="resp_(\d+)_(\d+)"[^>]*>(.*?)</textarea>', re.S,
)
_RESP_HIDDEN = re.compile(
    r'<input\b[^>]*type="hidden"[^>]*name="resp_(\d+)_(\d+)"[^>]*?value="([^"]*)"',
    re.S,
)
_OPCAO_BTN = re.compile(r'data-valor="([^"]*)"\s*onclick="([^"]*)"', re.S)
_MARCA_OPCAO = re.compile(
    r'class="([^"]*conselho-opcao[^"]*)"[^>]*?data-valor="([^"]*)"', re.S,
)
_HIDDEN_TARGET = re.compile(r"document\.getElementById\('([^']+)'\)\.value\s*=")
_COR_VAR = re.compile(r'--conselho-pergunta-cor:\s*(#[0-9a-fA-F]{6})\b')


def _corpo(response):
    return response.get_data(as_text=True)


def _observadores(corpo):
    """`{'<aluno>_<pergunta>': conteúdo do textarea obs_}`."""
    return {f"{a}_{p}": texto for a, p, texto in _OBS_TA.findall(corpo)}


def _resp_hidden(corpo):
    return {f"{a}_{p}": valor for a, p, valor in _RESP_HIDDEN.findall(corpo)}


def _resp_textareas(corpo):
    return {f"{a}_{p}": texto for a, p, texto in _RESP_TA.findall(corpo)}


def _alternativas_marcadas(corpo):
    """`{valor da opção: classes do botão}` dos botões `.conselho-opcao`."""
    return {valor: classes
            for classes, valor in _MARCA_OPCAO.findall(corpo)}


def _botoes_opcao(corpo):
    """`[(valor da opção, onclick desescapado)]` de todos os botões de opção."""
    return [(valor, html.unescape(onclick))
            for valor, onclick in _OPCAO_BTN.findall(corpo)]


# ---------------------------------------------------------------------------
# Semente
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


def _setup(app):
    """Turma X com oferta do P1 (duas perguntas ALUNO) e turma Y do P2.

    Mesma cruzamento de `tests/test_conselho_professor.py`: o professor da
    turma não é o professor da oferta, o que permite testar o 403 de quem não
    é da oferta sem depender de unidade.
    """
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ2", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        p1 = _usuario("Professor Um", "professor", unidade.id)
        p2 = _usuario("Professor Dois", "professor", unidade.id)
        admin = _usuario("Admin AJ2", "admin", unidade.id)
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="Periodo AJ2", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma_x = Turma(
            nome="Turma X", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True, professor_id=p2.id,
        )
        turma_y = Turma(
            nome="Turma Y", turno="Tarde", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True, professor_id=p1.id,
        )
        db.session.add_all([turma_x, turma_y])
        db.session.flush()

        curso_x = Curso(nome="Curso X", unidade_id=unidade.id, ativo=True)
        curso_y = Curso(nome="Curso Y", unidade_id=unidade.id, ativo=True)
        db.session.add_all([curso_x, curso_y])
        db.session.flush()

        ox = nova_oferta(
            turma_x.id, curso_x.id, unidade.id, programa="Programa X",
            principal=True, professor_id=p1.id,
        )
        oy = nova_oferta(
            turma_y.id, curso_y.id, unidade.id, programa="Programa Y",
            principal=True, professor_id=p2.id,
        )

        aluno_x = Aluno(nome="Aluno do X", unidade_id=unidade.id, ativo=True)
        aluno_y = Aluno(nome="Aluno do Y", unidade_id=unidade.id, ativo=True)
        db.session.add_all([aluno_x, aluno_y])
        db.session.flush()
        nova_inscricao(aluno_x.id, turma_x.id, ox.id)
        nova_inscricao(aluno_y.id, turma_y.id, oy.id)

        p_opcoes = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="Como participa das aulas?",
            opcoes=" | ".join(OPCOES), ativo=True,
        )
        p_livre = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="O que a família precisa saber?", opcoes="", ativo=True,
        )
        p_turma = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="TURMA",
            texto="Como a turma evoluiu?", opcoes="", ativo=True,
        )
        db.session.add_all([p_opcoes, p_livre, p_turma])
        db.session.commit()

        return {
            "un": unidade.id,
            "p1": p1.id,
            "p2": p2.id,
            "admin": admin.id,
            "turma_x": turma_x.id,
            "turma_y": turma_y.id,
            "ox": ox.id,
            "oy": oy.id,
            "aluno_x": aluno_x.id,
            "aluno_y": aluno_y.id,
            "p_opcoes": p_opcoes.id,
            "p_livre": p_livre.id,
            "p_turma": p_turma.id,
        }


def _url_lancamento(ids):
    return (f"/conselho/lancamento?turma={ids['turma_x']}&etapa=INICIAL"
            f"&oferta_sel={ids['ox']}")


def _post_salvar(client, ids, campos):
    data = {
        "turma_id": str(ids["turma_x"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["ox"]),
    }
    data.update(campos)
    return client.post("/conselho/salvar", data=data)


def _buscar_resposta(aluno_id, pergunta_id):
    return ConselhoResposta.query.filter_by(
        aluno_id=aluno_id, pergunta_id=pergunta_id,
    ).one()


# ---------------------------------------------------------------------------
# T1 — GET: controles de resposta e de observação separados
# ---------------------------------------------------------------------------

def test_t1_get_renderiza_controle_de_resposta_e_textarea_de_observacao(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    corpo = _corpo(client.get(_url_lancamento(ids)))
    chave_opcoes = f"{ids['aluno_x']}_{ids['p_opcoes']}"
    chave_livre = f"{ids['aluno_x']}_{ids['p_livre']}"

    # Toda pergunta do formulário ganhou UM textarea obs_<aluno>_<pergunta>.
    obs = _observadores(corpo)
    assert set(obs) == {chave_opcoes, chave_livre}, (
        "o lançamento precisa de um textarea obs_ por pergunta (aluno×pergunta)"
    )

    # Pergunta com opções: a resposta é input hidden + botões, NÃO textarea.
    assert chave_opcoes in _resp_hidden(corpo)
    assert chave_opcoes not in _resp_textareas(corpo), (
        "pergunta com opções não pode continuar com textarea resp_ único"
    )
    # Pergunta de texto livre: continua textarea resp_.
    assert chave_livre in _resp_textareas(corpo)

    # Nenhum valor de opção aparece dentro de um textarea de observação.
    for chave, texto in obs.items():
        for opcao in OPCOES:
            assert opcao not in texto, (
                f"a opção {opcao!r} vazou para o textarea obs_{chave}"
            )
    assert obs[chave_opcoes].strip() == ""
    assert obs[chave_livre].strip() == ""

    # Os rótulos distinguem os dois campos (não é o mesmo campo repetido).
    assert 'placeholder="Digite sua observação..."' in corpo
    assert 'placeholder="Digite a resposta..."' in corpo

    # Os botões de alternativa existem, rotulados com letra e valor puro.
    botoes = _botoes_opcao(corpo)
    assert [valor for valor, _ in botoes] == OPCOES
    assert "active" not in _alternativas_marcadas(corpo)["Sempre"].split(), (
        "nenhuma alternativa nasce marcada num lançamento vazio"
    )


# ---------------------------------------------------------------------------
# T2 — POST resp_ + obs_: colunas separadas e reexibição
# ---------------------------------------------------------------------------

def test_t2_post_grava_resposta_e_observacao_sem_misturar(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"
    texto_livre = "A familia relata melhora nas ultimas semanas"

    r = _post_salvar(client, ids, {
        f"resp_{chave}": TEXTO_OPCAO_MARCADA,
        f"obs_{chave}": texto_livre,
    })
    assert r.status_code == 302

    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        # `resposta` é o valor PURO da opção: sem letra, sem texto livre.
        assert resposta.resposta == TEXTO_OPCAO_MARCADA
        assert resposta.observacao == texto_livre

    corpo = _corpo(client.get(_url_lancamento(ids)))
    assert _resp_hidden(corpo)[chave] == TEXTO_OPCAO_MARCADA
    assert _observadores(corpo)[chave] == texto_livre
    # A alternativa gravada volta marcada no HTML (e só ela).
    marcadas = _alternativas_marcadas(corpo)
    assert set(marcadas) == set(OPCOES), (
        f"os botões de alternativa precisam da classe conselho-opcao: {marcadas}"
    )
    assert "active" in marcadas[TEXTO_OPCAO_MARCADA].split()
    assert "fw-bold" in marcadas[TEXTO_OPCAO_MARCADA].split()
    for valor, classes in marcadas.items():
        if valor != TEXTO_OPCAO_MARCADA:
            assert "active" not in classes.split(), f"{valor} saiu marcada também"
    # O texto da observação não é despejado dentro do controle de resposta.
    assert texto_livre not in _resp_hidden(corpo)[chave]


def test_salvar_conselho_grava_e_completa_unidade_sem_trocar_autor(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"
    campos = {
        f"resp_{chave}": TEXTO_OPCAO_MARCADA,
        f"obs_{chave}": "",
    }

    assert _post_salvar(client, ids, campos).status_code == 302
    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        autor_id = resposta.autor_id
        assert resposta.unidade_id == ids["un"]
        resposta.unidade_id = None
        db.session.commit()

    assert _post_salvar(client, ids, campos).status_code == 302
    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        assert resposta.unidade_id == ids["un"]
        assert resposta.autor_id == autor_id


# ---------------------------------------------------------------------------
# T3 — obs_ enviado vazio: campo fica vazio, nunca recebe a alternativa
# ---------------------------------------------------------------------------

def test_t3_observacao_vazia_nao_recebe_a_alternativa(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"

    r = _post_salvar(client, ids, {
        f"resp_{chave}": TEXTO_OPCAO_MARCADA,
        f"obs_{chave}": "",
    })
    assert r.status_code == 302

    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        assert resposta.resposta == TEXTO_OPCAO_MARCADA
        assert resposta.observacao in (None, ""), (
            f"obs_ vazio gravou {resposta.observacao!r}"
        )

    # O textarea obs_ existe (é o controle novo) e aparece vazio.
    corpo = _corpo(client.get(_url_lancamento(ids)))
    obs = _observadores(corpo)
    assert chave in obs, "sem textarea obs_ o teste não prova nada"
    assert obs[chave] == ""
    for opcao in OPCOES:
        assert opcao not in obs[chave]


# ---------------------------------------------------------------------------
# T4 — obs_ ausente preserva; obs_ vazio enviado limpa
# ---------------------------------------------------------------------------

def test_t4_obs_ausente_preserva_e_obs_vazio_limpa(client, app):
    """Comportamento do código atual (após o `f3d2b15`).

    `_normalize_conselho_request` só coloca na chave de observações o campo que
    o formulário enviou, e o laço de gravação toca `observacao` apenas quando
    `has_obs`. Consequência documentada: omitir o campo preserva o texto
    anterior; enviá-lo vazio é uma ordem de limpeza explícita.
    """
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"
    primeiro_texto = "Observacao gravada no primeiro salvamento"

    _post_salvar(client, ids, {
        f"resp_{chave}": "Nunca",
        f"obs_{chave}": primeiro_texto,
    })
    with app.app_context():
        assert _buscar_resposta(ids["aluno_x"], ids["p_opcoes"]).observacao == primeiro_texto

    # POST que NÃO envia obs_ (só troca a alternativa): preserva o texto.
    r = _post_salvar(client, ids, {f"resp_{chave}": TEXTO_OPCAO_MARCADA})
    assert r.status_code == 302
    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        assert resposta.resposta == TEXTO_OPCAO_MARCADA
        assert resposta.observacao == primeiro_texto, (
            "omitir obs_ não pode apagar a observação já gravada"
        )

    # POST que envia obs_ vazio DE PROPÓSITO: limpa.
    r = _post_salvar(client, ids, {f"resp_{chave}": TEXTO_OPCAO_MARCADA,
                                   f"obs_{chave}": ""})
    assert r.status_code == 302
    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        assert resposta.observacao in (None, ""), (
            f"obs_ vazio deveria limpar e ficou {resposta.observacao!r}"
        )


# ---------------------------------------------------------------------------
# T5 — pergunta de texto livre: continua gravando em `resposta`
# ---------------------------------------------------------------------------

def test_t5_pergunta_texto_livre_continua_gravando_em_resposta(client, app):
    """Sem regressão em relação ao comportamento anterior ao `f3d2b15`.

    Antes, a pergunta sem opções era o único textarea `resp_` do card; o texto
    digitado ia para `ConselhoResposta.resposta`. O `f3d2b15` manteve esse
    caminho (textarea `resp_` + o novo `obs_` adicional), então o valor tem de
    continuar em `resposta` — e `observacao` segue intocada quando o campo não
    é enviado.
    """
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    chave = f"{ids['aluno_x']}_{ids['p_livre']}"
    dissertacao = ("Participa das atividades em grupo e trouxe a leitura "
                   "do contrato de convivencia")

    r = _post_salvar(client, ids, {f"resp_{chave}": dissertacao})
    assert r.status_code == 302

    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_livre"])
        assert resposta.resposta == dissertacao
        assert resposta.observacao is None

    corpo = _corpo(client.get(_url_lancamento(ids)))
    assert _resp_textareas(corpo)[chave] == dissertacao


# ---------------------------------------------------------------------------
# T6 — regressões do entorno
# ---------------------------------------------------------------------------

def _encerrar(app, oferta_id):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        oferta.conselho_concluido = True
        db.session.commit()


def test_t6a_oferta_encerrada_bloqueia_get_e_post_sem_gravar(client, app):
    ids = _setup(app)
    _encerrar(app, ids["ox"])
    login_as(client, ids["p1"], ids["un"])

    r = client.get(_url_lancamento(ids))
    assert r.status_code == 302
    with app.app_context():
        assert ConselhoClasse.query.count() == 0

    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"
    r = _post_salvar(client, ids, {
        f"resp_{chave}": TEXTO_OPCAO_MARCADA,
        f"obs_{chave}": "Tentativa apos encerramento",
    })
    assert r.status_code == 302
    with app.app_context():
        assert ConselhoResposta.query.count() == 0


def test_t6b_professor_de_outra_oferta_leva_403(client, app):
    ids = _setup(app)
    login_as(client, ids["p2"], ids["un"])

    assert client.get(_url_lancamento(ids)).status_code == 403

    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"
    r = _post_salvar(client, ids, {
        f"resp_{chave}": "Invasao",
        f"obs_{chave}": "Invasao na observacao",
    })
    assert r.status_code == 403
    with app.app_context():
        assert ConselhoResposta.query.count() == 0
        assert ConselhoClasse.query.count() == 0


def test_t6c_autor_do_lancamento_so_troca_com_mudanca_de_conteudo(client, app):
    ids = _setup(app)
    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"

    login_as(client, ids["p1"], ids["un"])
    _post_salvar(client, ids, {
        f"resp_{chave}": "Nunca",
        f"obs_{chave}": "Observacao do primeiro professor",
    })
    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        assert resposta.autor_id == ids["p1"]
        assert resposta.autor_nome == "Professor Um"

    # Reenviar o MESMO conteúdo como admin: autor continua o professor.
    login_as(client, ids["admin"], ids["un"])
    _post_salvar(client, ids, {
        f"resp_{chave}": "Nunca",
        f"obs_{chave}": "Observacao do primeiro professor",
    })
    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        assert resposta.autor_id == ids["p1"], (
            "regravar o mesmo conteúdo não pode trocar o autor"
        )
        assert resposta.autor_nome == "Professor Um"

    # Mudar só a OBSERVAÇÃO: o autor passa a ser quem alterou (é a escrita que
    # o f3d2b15 habilitou — antes o campo não era gravado e o autor nunca
    # trocava por causa dele).
    _post_salvar(client, ids, {
        f"resp_{chave}": "Nunca",
        f"obs_{chave}": "Observacao reescrita pelo admin",
    })
    with app.app_context():
        resposta = _buscar_resposta(ids["aluno_x"], ids["p_opcoes"])
        assert resposta.observacao == "Observacao reescrita pelo admin"
        assert resposta.autor_id == ids["admin"]
        assert resposta.autor_nome == "Admin AJ2"


def test_t6d_avaliacao_coletiva_abre_e_grava_como_antes(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    url = (f"/turma/{ids['turma_x']}/avaliacao?etapa=INICIAL"
           f"&oferta_sel={ids['ox']}")
    corpo = _corpo(client.get(url))
    assert "Como a turma evoluiu?" in corpo
    assert "Como participa das aulas?" not in corpo

    r = client.post(url, data={
        "turma_curso_id": str(ids["ox"]),
        f"resp_turma_{ids['p_turma']}": "Turma avancou no convívio",
    })
    assert r.status_code == 302
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["ox"])
        assert "Turma avancou no convívio" in (oferta.avaliacao_inicial or "")


# ---------------------------------------------------------------------------
# T7 — contraste WCAG da cor das perguntas
# ---------------------------------------------------------------------------

def _canal_srgb(byte):
    v = byte / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _luminancia(hexcor):
    r, g, b = (int(hexcor[i:i + 2], 16) for i in (1, 3, 5))
    return (0.2126 * _canal_srgb(r) + 0.7152 * _canal_srgb(g)
            + 0.0722 * _canal_srgb(b))


def _razao_contraste(cor_a, cor_b):
    la, lb = sorted((_luminancia(cor_a), _luminancia(cor_b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_t7_contraste_das_perguntas_passa_em_aa_normal(client, app):
    css = TEMPLATE_LANCAMENTO.read_text(encoding="utf-8")
    achado = _COR_VAR.search(css)
    assert achado, "--conselho-pergunta-cor não definida no template do lançamento"
    cor = achado.group(1).lower()

    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    corpo = _corpo(client.get(_url_lancamento(ids)))
    assert cor in corpo, "a cor do CSS precisa aparecer na página renderizada"

    fundo = "#ffffff"
    razao = _razao_contraste(cor, fundo)
    print(f"\n[AJ3-E3] contraste {cor} sobre {fundo}: {razao:.2f}:1")
    assert razao >= 4.5, (
        f"{cor} sobre branco dá {razao:.2f}:1 — abaixo do AA (4.5:1)"
    )


# ---------------------------------------------------------------------------
# T8 — conselho.js e o handler da alternativa não escrevem em obs_
# ---------------------------------------------------------------------------

_ARQUIVO_JS = """
function novoElemento(id, valor) {
  const classes = [];
  return {
    id,
    value: valor,
    classes,
    classList: {
      add(...c) { c.forEach((x) => { if (!classes.includes(x)) classes.push(x); }); },
      remove(...c) { c.forEach((x) => { const i = classes.indexOf(x); if (i >= 0) classes.splice(i, 1); }); },
      contains(x) { return classes.includes(x); },
    },
    _attrs: {},
    getAttribute(nome) { return Object.prototype.hasOwnProperty.call(this._attrs, nome) ? this._attrs[nome] : null; },
    parentElement: null,
  };
}

const cfg = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));
const resp = novoElemento(cfg.resp_id, '');
const obs = novoElemento(cfg.obs_id, cfg.obs_inicial);
const registro = {};
registro[cfg.resp_id] = resp;
registro[cfg.obs_id] = obs;

const botoes = cfg.opcoes.map((v) => {
  const b = novoElemento('botao_' + v, undefined);
  b._attrs['data-valor'] = v;
  return b;
});
const grupo = { querySelectorAll: (sel) => (sel === '.conselho-opcao' ? botoes : []) };
botoes.forEach((b) => { b.parentElement = grupo; });

const documento = { getElementById: (id) => registro[id] };
const alvo = botoes[cfg.indice];
new Function('document', cfg.handler).call(alvo, documento);

process.stdout.write(JSON.stringify({
  resp_valor: resp.value,
  obs_valor: obs.value,
  classes_alvo: alvo.classes,
}));
"""


def test_t8a_texto_conselho_js_e_handler_nao_tocam_obs(client, app):
    js = JS_CONSELHO.read_text(encoding="utf-8")
    assert "obs_" not in js, "conselho.js não deve conhecer nenhum campo obs_"
    alvos = re.findall(r"getElementById\('([^']+)'\)\.value\s*=", js)
    alvos += re.findall(r'getElementById\("([^"]+)"\)\.value\s*=', js)
    assert all(not alvo.startswith("obs_") for alvo in alvos), alvos

    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    corpo = _corpo(client.get(_url_lancamento(ids)))
    botoes = _botoes_opcao(corpo)
    assert botoes, "o lançamento precisa dos botões de alternativa"
    for _valor, handler in botoes:
        assert "obs_" not in handler, handler
        assert "<textarea" not in handler
        alvos = _HIDDEN_TARGET.findall(handler)
        assert alvos, "o handler precisa atribuir a resposta a algum campo"
        assert all(a.startswith("resp_") for a in alvos), alvos


def test_t8b_clique_na_alternativa_nao_altera_o_textarea(client, app, tmp_path):
    """Executa o handler real da página em node com um DOM mínimo.

    O DOM embarcado do Python não roda JS; em vez de depender de jsdom (que não
    é requisito do projeto), o teste monta só os três elementos que o handler
    usa — input hidden `resp_`, textarea `obs_` e o grupo de botões — roda o
    texto exato do `onclick` renderizado e confere os valores finais.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("node indisponível: teste de comportamento do clique pulado "
                    "(a prova textual em T8a continua rodando)")

    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])
    corpo = _corpo(client.get(_url_lancamento(ids)))
    chave = f"{ids['aluno_x']}_{ids['p_opcoes']}"
    botoes = _botoes_opcao(corpo)
    indice = next(i for i, (v, _h) in enumerate(botoes)
                  if v == TEXTO_OPCAO_MARCADA)
    _valor, handler = botoes[indice]

    texto_preexistente = "nota que o professor ja tinha digitado"
    cfg = {
        "handler": handler,
        "resp_id": f"resp_{chave}",
        "obs_id": f"obs_{chave}",
        "obs_inicial": texto_preexistente,
        "opcoes": OPCOES,
        "indice": indice,
    }
    arq_cfg = tmp_path / "clique.json"
    arq_cfg.write_text(json.dumps(cfg), encoding="utf-8")
    arq_js = tmp_path / "clique.js"
    arq_js.write_text(_ARQUIVO_JS.strip(), encoding="utf-8")

    roda = subprocess.run(
        [node, str(arq_js), str(arq_cfg)],
        capture_output=True, text=True, timeout=60, encoding="utf-8",
    )
    assert roda.returncode == 0, roda.stderr
    resultado = json.loads(roda.stdout)
    print(f"\n[AJ3-E3] clique na alternativa {TEXTO_OPCAO_MARCADA!r}: {resultado}")

    assert resultado["resp_valor"] == TEXTO_OPCAO_MARCADA
    assert resultado["obs_valor"] == texto_preexistente, (
        "o clique na alternativa reescreveu o textarea de observação"
    )
    assert "active" in resultado["classes_alvo"]
    assert "fw-bold" in resultado["classes_alvo"]
