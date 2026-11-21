"""AJ28 — impressão do "Resumo - Primeira Vista" (`/relatorios/`).

Cobre: cabeçalho/rodapé de impressão, 9 blocos, listas longas e vazias,
contrato do CSS/JS de impressão e, principalmente, a não regressão da tela
(os cards continuam com o mesmo HTML de antes da AJ28).
"""

from __future__ import annotations

import difflib
from pathlib import Path

from _helpers import login_as

import app.relatorios.geral as modulo_geral
from app.database import db
from app.models import Unidade, User

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "relatorios" / "geral.html"
CSS = RAIZ / "app" / "static" / "css" / "relatorios" / "geral.css"
JS = RAIZ / "app" / "static" / "js" / "relatorios" / "geral.js"
SNAPSHOT_CARDS = RAIZ / "tests" / "snapshots" / "aj28_geral_cards_before.txt"

BLOCOS = (
    "Comunidade Ativa",
    "Painel do Conselho",
    "Distribuição por Sexo",
    "Média de Idade Geral",
    "Média por Programa",
    "Média por Turma",
    "Frequência por Programa",
    "Desempenho por Professor",
    "Frequência por Turma",
)


def _setup(app):
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ28", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        usuario = User(
            name="Colaborador AJ28",
            email="aj28@teste.local",
            role="admin",
            first_login=False,
            unidade_id=unidade.id,
        )
        usuario.set_password("SenhaLocal!123")
        db.session.add(usuario)
        db.session.commit()
        return {
            "user_id": usuario.id,
            "unidade": unidade.id,
            "unidade_nome": unidade.nome,
        }


def _patch_dados(monkeypatch, *, turmas=0, professores=0, programas=0):
    """Substitui só os cálculos da rota (sem tocar consultas/permissões)."""
    turmas_media = {
        f"TURMA-AJ28-{i:02d}": 14.0 + i / 10 for i in range(1, turmas + 1)
    }
    profs = {
        f"PROF-AJ28-{i:02d}": 70 + i for i in range(1, professores + 1)
    }
    progs = {
        f"Programa AJ28 {i}": 25.0 + i for i in range(1, programas + 1)
    }
    monkeypatch.setattr(
        modulo_geral,
        "calcular_estatisticas_idade",
        lambda unidade_id=None: {
            "media_geral": 21.5,
            "media_programa": progs,
            "media_turma": turmas_media,
        },
    )
    monkeypatch.setattr(
        modulo_geral,
        "calcular_frequencias_relatorio",
        lambda turmas_do_banco, unidade_id=None: (
            88.0,
            {f"Programa AJ28 {i}": 80 + i for i in range(1, programas + 1)},
            {
                f"TURMA-AJ28-{i:02d}": 50 + i
                for i in range(1, turmas + 1)
            },
            profs,
        ),
    )
    monkeypatch.setattr(
        modulo_geral,
        "calcular_metricas_conselho",
        lambda unidade_id=None: {
            "progresso_aulas": 90,
            "progresso_reunioes": 70,
            "turmas_concluidas": 7,
            "total_turmas": 10,
        },
    )
    return {"turmas": turmas, "profs": professores, "programas": programas}


def _get(client, ids):
    return client.get("/relatorios/")


def test_rota_e_contexto_de_escopo(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    resposta = _get(client, ids)
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert 'id="conteudo-impressao"' in html
    # A rota não tem filtro de turma: o cabeçalho mostra a unidade e "Todas".
    assert "Escopo: Unidade Unidade AJ28 · Turma: Todas" in html
    assert "<strong>Unidade:</strong> Unidade AJ28" in html
    assert "<strong>Turma:</strong> Todas" in html
    assert "Colaborador: <strong>Colaborador AJ28</strong>" in html
    assert "Emitido em <span class=\"geral-emissao\"></span>" in html


def test_nove_blocos_e_botoes(app, client, monkeypatch):
    ids = _setup(app)
    _patch_dados(monkeypatch, turmas=10, professores=3, programas=2)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)

    for bloco in BLOCOS:
        assert bloco in html, f"bloco ausente: {bloco}"
    assert "7 de 10 ofertas finalizadas" in html
    assert "Conteúdos Registrados" in html
    assert "Ofertas Avaliadas" in html

    # Barra de botões intacta e fora da impressão; só o onclick mudou.
    assert 'class="d-print-none d-flex gap-2 flex-wrap"' in html
    assert "Exportar Alunos" in html
    assert "Exportar Painel" in html
    assert 'onclick="prepararImpressao()"' in html
    assert "window.print()" not in html
    assert TEMPLATE.read_text(encoding="utf-8").count("window.print()") == 0


def test_cabecalho_e_rodapé_de_impressao(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)

    inicio = html.index('<header class="print-only report-header geral-print-header">')
    cabecalho = html[inicio:html.index("</header>", inicio) + len("</header>")]
    for trecho in (
        "print-only", "geral-print-header", "report-logo",
        "Resumo - Primeira Vista", "Escopo:", "Emitido em",
        "geral-emissao", "Colaborador:",
    ):
        assert trecho in cabecalho

    assert 'class="print-only print-footer-container"' in html
    assert 'id="print-date"' in html
    assert "Data/Hora:" in html
    assert "URL:" in html
    assert "v " in html  # v {{ app_version }}-{{ app_stage }}


def test_css_de_impressao_segue_padrao_aj23():
    css = CSS.read_text(encoding="utf-8")
    assert css.count("@page") == 1
    assert "size: A4 landscape" in css
    assert "margin: 1cm" in css
    assert "size: A4 portrait" not in css
    assert "margin: 1.5cm" not in css
    # Regras antigas de tela preservadas (CSS morto/herdado, sem remoção).
    for seletor in (".report-table thead th", ".filter-card", ".gender-icon",
                    ".card.bg-primary", ".progress"):
        assert seletor in css
    assert ".print-only {" in css

    # Listas com rolagem inline imprimem completas.
    for trecho in (
        'max-height: none !important',
        'height: auto !important',
        'overflow: visible !important',
        'overflow-y: visible !important',
        '[style*="max-height"]',
    ):
        assert trecho in css
    assert "print-color-adjust: exact" in css
    assert "-webkit-print-color-adjust: exact" in css
    assert ".progress-bar" in css
    assert "#conteudo-impressao .badge" in css
    assert "#conteudo-impressao .card" in css
    assert "#conteudo-impressao .geral-print-header" in css
    assert "#conteudo-impressao > header.print-only + div" in css
    assert "#conteudo-impressao .card:has(" in css
    assert "break-inside: avoid" in css
    assert "page-break-inside: avoid" in css
    assert "break-after: avoid" in css
    assert "break-before: auto !important" in css
    assert "#conteudo-impressao .lista-vazia" in css
    assert ".app-main," in css
    assert "margin-left: 0 !important" in css
    assert "#conteudo-impressao .print-footer-container" in css
    assert ".app-topbar," in css
    assert ".d-print-none," in css


def test_js_tem_preparar_impressao_e_beforeprint():
    js = JS.read_text(encoding="utf-8")
    assert "function prepararImpressao()" in js
    assert "function preencherEmissao()" in js
    funcao = js[js.index("function prepararImpressao()"):]
    funcao = funcao[:funcao.index("\n    }")]
    assert funcao.index("preencherEmissao()") < funcao.index("window.print()")
    assert "window.prepararImpressao = prepararImpressao" in js
    assert "window.addEventListener('beforeprint', preencherEmissao)" in js
    assert "print-date" in js
    assert "geral-emissao" in js


def test_listas_grandes_imprimem_todos_os_itens(app, client, monkeypatch):
    ids = _setup(app)
    dados = _patch_dados(monkeypatch, turmas=30, professores=15, programas=5)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)

    # 30 turmas aparecem em "Média por Turma" e em "Frequência por Turma".
    for indice in range(1, dados["turmas"] + 1):
        nome = f"TURMA-AJ28-{indice:02d}"
        assert html.count(nome) == 2, f"{nome}: esperado em duas listas"
    # 15 professores, apenas em "Desempenho por Professor".
    for indice in range(1, dados["profs"] + 1):
        assert f"PROF-AJ28-{indice:02d}" in html
    # Largura das barras continua vinda do servidor, inline.
    assert 'style="width: 85%"' in html
    assert html.count('class="progress" style="height: 6px;"') >= 5
    assert html.count('class="progress" style="height: 5px;"') >= 30
    # Nenhum recorte por CONTAGEM: o HTML contém todos os itens; o CSS de
    # impressão é quem libera a rolagem (testado acima).
    assert html.count("badge bg-light text-dark border") >= 30


def test_listas_vazias_só_aparecem_na_impressao(app, client, monkeypatch):
    ids = _setup(app)
    _patch_dados(monkeypatch, turmas=0, professores=0, programas=0)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)

    assert html.count('<div class="print-only lista-vazia">—</div>') == 5
    for bloco in BLOCOS:
        assert bloco in html
    assert "#conteudo-impressao .lista-vazia" in CSS.read_text(encoding="utf-8")


def test_html_dos_nove_cards_permanece_idêntico():
    """Regressão de tela: só `.print-only` e o `onclick` podem ter mudado."""
    origem = TEMPLATE.read_text(encoding="utf-8")
    inicio = origem.index("    <!-- Linha 1: Visão Geral e Comunidade -->")
    fim = origem.index("\n    {# Rodapé de auditoria", inicio)
    atual = [linha for linha in origem[inicio:fim].replace("\r\n", "\n").splitlines()
             if linha.strip()
             and "print-only lista-vazia" not in linha
             and linha.strip() != "{% else %}"]
    antes = [
        linha for linha in SNAPSHOT_CARDS.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    assert atual == antes, "\n".join(difflib.unified_diff(antes, atual, lineterm=""))

    # Nenhum hook de classe nova nos cards; estilos inline intactos.
    for proibida in ("resumo-card", "lista-impressao", "resumo-card-titulo",
                     "resumo-card-lista"):
        assert proibida not in origem
    assert origem.count('style="max-height: 180px; overflow-y: auto;"') == 1
    assert origem.count('style="max-height: 250px; overflow-y: auto;"') == 2
    assert 'style="width: {{ perc }}%"' in origem
    assert ".custom-scrollbar::-webkit-scrollbar" in origem


def test_contratos_das_ajs_anteriores_preservados():
    fechamento = (RAIZ / "app" / "templates" / "conselho" / "fechamento.html").read_text(encoding="utf-8")
    css_conselho = (RAIZ / "app" / "static" / "css" / "conselho" / "conselho.css").read_text(encoding="utf-8")
    resultado = (RAIZ / "app" / "templates" / "relatorios" / "resultado_conselho.html").read_text(encoding="utf-8")
    css_resultado = (RAIZ / "app" / "static" / "css" / "relatorios" / "resultado_conselho.css").read_text(encoding="utf-8")

    assert "fechamento-print-header" in fechamento
    assert "prepararImpressao()" in fechamento
    assert "#tabelaFechamento .badge" in css_conselho
    assert "resultado-print-header" in resultado
    assert "Período do Conselho" in resultado
    assert "Conceito" in resultado
    assert "inicio-turma" in resultado
    assert "#tabelaResultado" in css_resultado
    assert "page-break-inside: auto !important" in css_resultado
