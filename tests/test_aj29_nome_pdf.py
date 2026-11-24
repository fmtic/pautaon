"""AJ29 — nome padrão do arquivo PDF nos relatórios impressos.

Testes de contrato no servidor (templates, base e módulo JS). O comportamento
puro do JS é executado em node em ``tests/test_aj29_nome_pdf_js.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
BASE = RAIZ / "app" / "templates" / "base.html"
JS = RAIZ / "app" / "static" / "js" / "impressao_pdf.js"

PRINCIPAIS = (
    (
        "app/templates/relatorios/geral.html",
        "Resumo-Primeira-Vista",
        ("escopo_unidade",),
        ("{data}",),
    ),
    (
        "app/templates/relatorios/resultado_conselho.html",
        "Resultado-Conselho",
        ("unidade_contexto", "periodo_selecionado.nome"),
        ("{data}",),
    ),
    (
        "app/templates/conselho/fechamento.html",
        "Fechamento-Conselho",
        ("oferta.curso.nome", "turma.nome"),
        ("{data}",),
    ),
)


def atributos_pdf(caminho: Path) -> list[str]:
    return re.findall(r'data-pdf-nome="([^"]*)"', caminho.read_text(encoding="utf-8"))


def test_base_carrega_modulo_antes_dos_scripts_de_pagina():
    origem = BASE.read_text(encoding="utf-8")
    assert origem.count("js/impressao_pdf.js") == 1
    pos_modulo = origem.index("js/impressao_pdf.js")
    pos_bootstrap = origem.index("bootstrap/js/bootstrap.bundle.min.js")
    pos_app = origem.index("js/app.js")
    pos_bloco = origem.index("{% block scripts %}")
    assert pos_modulo < pos_bootstrap < pos_app < pos_bloco


def test_modulo_js_tem_contrato_de_titulo_e_sanitizacao():
    origem = JS.read_text(encoding="utf-8")
    for trecho in (
        "beforeprint", "afterprint", "addEventListener",
        "conteudo-impressao", "data-pdf-nome", "doc.body || null",
        "normalize('NFD')", "[\\u0300-\\u036f]",
        "[^A-Za-z0-9._-]", "-{2,}", "slice(0, LIMITE)",
        " tituloOriginal ", "doc.title = nome", "doc.title = tituloOriginal",
        "'{data}'", "module.exports",
    ):
        assert trecho in origem, trecho
    assert "LIMITE = 100" in origem
    # Não substitui nem remove as funções de impressão já existentes.
    # (ignora os comentários de documentação, que citam esses nomes)
    codigo = re.sub(r"/\*.*?\*/|//[^\n]*", "", origem, flags=re.DOTALL)
    assert "prepararImpressao" not in codigo
    assert "window.print" not in codigo


@pytest.mark.parametrize(
    "relativo,prefixo,variaveis,tokens",
    PRINCIPAIS,
    ids=("geral", "resultado_conselho", "fechamento"),
)
def test_templates_principais_tem_atributo_no_padrao(
    relativo, prefixo, variaveis, tokens
):
    atributos = atributos_pdf(RAIZ / relativo)
    assert len(atributos) == 1, (relativo, atributos)
    valor = atributos[0]
    assert valor.startswith(prefixo + "{% if ") or valor.startswith(prefixo)
    for variavel in variaveis:
        assert variavel in valor, (relativo, variavel)
    for token in tokens:
        assert token in valor
    # Trecho vazio é omitido: todo acréscimo contextual está dentro de `if`.
    assert valor.count("{% if ") >= len(variaveis)
    assert valor.count("{% endif %}") == valor.count("{% if ")
    # Nenhum valor é impresso cru sem proteção de existência.
    assert "None" not in valor


def test_atributos_de_pdf_nao_contem_dados_pessoais():
    for caminho in (RAIZ / relativo for relativo, *_ in PRINCIPAIS):
        for valor in atributos_pdf(caminho):
            baixo = valor.lower()
            assert "aluno" not in baixo or "historico-aluno" in baixo
            assert "current_user.name" not in valor
            assert ".cpf" not in valor
            assert ".email" not in valor
