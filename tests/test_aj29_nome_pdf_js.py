"""AJ29 — funções puras e contrato de título do módulo compartilhado de PDF
(``app/static/js/impressao_pdf.js``) executadas em node.

Segue o padrão de ``tests/test_grade_horario_js.py``: ``node -e`` com o
``module.exports`` do arquivo, com skip documentado quando node não está no
PATH. Nenhuma dependência JS nova entra no repositório.

Cobre: acentos, espaços, caracteres inválidos, token ``{data}``, limite de
100 caracteres e a guarda/restauração do ``document.title`` (com DOM mínimo
mockado, inclusive a ausência de atributo e o fallback para ``<body>``).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ARQ_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "impressao_pdf.js"

HARNESS = r"""
const P = require(process.argv[1]);

function mockDoc(opcoes) {
    const o = opcoes || {};
    const conteudo = o.semConteudo ? null : {
        hasAttribute: (nome) => nome === 'data-pdf-nome' && o.noConteudo !== undefined,
        getAttribute: (nome) => nome === 'data-pdf-nome' ? o.noConteudo : null,
    };
    const body = o.semBody ? null : {
        hasAttribute: (nome) => nome === 'data-pdf-nome' && o.noBody !== undefined,
        getAttribute: (nome) => nome === 'data-pdf-nome' ? o.noBody : null,
    };
    return {
        title: o.titulo || 'Titulo Original — pautaON',
        getElementById: (id) => id === 'conteudo-impressao' ? conteudo : null,
        body: body,
    };
}

const doc = mockDoc({titulo: 'Resumo - Primeira Vista · pautaON',
                     noConteudo: 'Resumo-Primeira-Vista_MGB_{data}'});
const antes = P.antesDeImprimir(doc);
const durante = doc.title;
const restaurou = P.depoisDeImprimir(doc);
const depois = doc.title;

const semAtributo = mockDoc({titulo: 'Sem atributo'});
const antesSemAttr = P.antesDeImprimir(semAtributo);
const depoisSemAttr = semAtributo.title;

const soBody = mockDoc({titulo: 'So body', semConteudo: true,
                        noBody: 'Historico-Aluno_{data}'});
const antesBody = P.antesDeImprimir(soBody);
const depoisBody = P.depoisDeImprimir(soBody);

const vazio = mockDoc({titulo: 'Vazio', noConteudo: ''});
const antesVazio = P.antesDeImprimir(vazio);

process.stdout.write(JSON.stringify({
    acento: P.sanitizar('Resumo - Primeira Vista Ação'),
    acentosTodos: P.sanitizar('ÁÉÍÓÚ áéíóú Çç Ãõ'),
    espacos: P.sanitizar('  Resumo   Primeira   Vista  '),
    invalidos: P.sanitizar('A/B:C?D*E|F@G#H'),
    hifens: P.sanitizar('--Resumo---Primeira--Vista--'),
    underscorePonto: P.sanitizar('Resumo.Primeira_Vista-2026'),
    vazioSanitizado: P.sanitizar(''),
    token: P.nomePdf('Relatorio-Primeira-Vista_{data}', '2026-11-23'),
    tokenMeio: P.nomePdf('Pauta_{data}_Turma-1', '2026-01-02'),
    tokenDuplo: P.nomePdf('A_{data}_{data}', '2026-01-02'),
    longo: P.nomePdf('X'.repeat(150), '2026-11-23'),
    longoComHifen: P.nomePdf(('Ab-'.repeat(60)), '2026-11-23'),
    antes, durante, restaurou, depois,
    antesSemAttr, depoisSemAttr,
    antesBody, depoisBody: soBody.title,
    antesVazio, tituloVazio: vazio.title,
    dataHoje: P.dataLocal(),
}));
"""


@pytest.fixture(scope="module")
def node():
    caminho = shutil.which("node")
    if caminho is None:  # skip documentado: sem suíte JS no repo
        pytest.skip("node não disponível no PATH — funções puras validadas só no servidor")
    return caminho


@pytest.fixture(scope="module")
def saida(node):
    processo = subprocess.run(
        [node, "-e", HARNESS, str(ARQ_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert processo.returncode == 0, processo.stderr
    return json.loads(processo.stdout)


def test_sanitizacao_remove_acentos(saida):
    assert saida["acento"] == "Resumo-Primeira-Vista-Acao"
    assert saida["acentosTodos"] == "AEIOU-aeiou-Cc-Ao"


def test_sanitizacao_colapsa_espacos_e_caracteres_invalidos(saida):
    assert saida["espacos"] == "Resumo-Primeira-Vista"
    assert saida["invalidos"] == "A-B-C-D-E-F-G-H"
    assert saida["hifens"] == "Resumo-Primeira-Vista"


def test_sanitizacao_preserva_caracteres_permitidos(saida):
    assert saida["underscorePonto"] == "Resumo.Primeira_Vista-2026"
    assert saida["vazioSanitizado"] == ""


def test_token_data_e_substituido_antes_de_sanitizar(saida):
    assert saida["token"] == "Relatorio-Primeira-Vista_2026-11-23"
    assert saida["tokenMeio"] == "Pauta_2026-01-02_Turma-1"
    assert saida["tokenDuplo"] == "A_2026-01-02_2026-01-02"


def test_limite_de_100_caracteres_sem_hifen_solto(saida):
    assert len(saida["longo"]) == 100
    assert saida["longo"] == "X" * 100
    assert len(saida["longoComHifen"]) <= 100
    assert not saida["longoComHifen"].endswith("-")


def test_titulo_e_trocado_e_restaurado_no_afterprint(saida):
    # {data} usa a data local do navegador: o esperado é derivado da própria
    # função, senão o teste quebra todo dia 00:00 (era fixo em 2026-11-23).
    assert saida["antes"] == f"Resumo-Primeira-Vista_MGB_{saida['dataHoje']}"
    assert saida["durante"] == saida["antes"]
    assert saida["restaurou"] is True
    assert saida["depois"] == "Resumo - Primeira Vista · pautaON"


def test_sem_atributo_ou_atributo_vazio_nao_mexe_no_titulo(saida):
    assert saida["antesSemAttr"] is None
    assert saida["depoisSemAttr"] == "Sem atributo"
    assert saida["antesVazio"] is None
    assert saida["tituloVazio"] == "Vazio"


def test_fallback_para_body_quando_nao_ha_conteudo_impressao(saida):
    assert saida["antesBody"] == f"Historico-Aluno_{saida['dataHoje']}"
    assert saida["depoisBody"] == "So body"
