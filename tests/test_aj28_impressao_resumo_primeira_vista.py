"""AJ28 / AJ28-B — impressão do "Resumo - Primeira Vista" (`/relatorios/`).

Cobre: cabeçalho/rodapé de impressão, 9 blocos, listas longas e vazias,
contrato do CSS/JS de impressão e, principalmente, a não regressão da tela
(os cards continuam com o mesmo HTML de antes da AJ28; só ganharam o wrapper
`d-print-none`). A AJ28-B acrescenta o bloco impresso dedicado, testado
neste mesmo módulo.
"""

from __future__ import annotations

import difflib
import re
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
    # A rota não tem filtro de turma: UMA linha de escopo, sem repetir unidade.
    assert "Unidade: Unidade AJ28 · Turma: Todas" in html
    assert "Escopo:" not in html
    assert "<strong>Unidade:</strong>" not in html
    assert "<strong>Turma:</strong>" not in html
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
        "Resumo - Primeira Vista", "Unidade: Unidade AJ28 · Turma: Todas",
        "Emitido em", "geral-emissao", "Colaborador:",
    ):
        assert trecho in cabecalho
    # AJ28-B: a unidade aparece UMA vez no papel.
    assert cabecalho.count("Unidade AJ28") == 1
    assert "Escopo:" not in cabecalho

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

    # 30 turmas aparecem em "Média por Turma", "Frequência por Turma" e
    # na tabela "Por turma" do bloco impresso da AJ28-B.
    for indice in range(1, dados["turmas"] + 1):
        nome = f"TURMA-AJ28-{indice:02d}"
        assert html.count(nome) == 3, f"{nome}: esperado nas duas listas + impressão"
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
    """Regressão de tela: só o wrapper `d-print-none` pode ter mudado."""
    origem = TEMPLATE.read_text(encoding="utf-8")
    inicio = origem.index('    <div class="d-print-none">\n    <!-- Linha 1: Visão Geral e Comunidade -->')
    # O bloco impresso da AJ28-B vem DEPOIS do wrapper dos cards: o snapshot
    # deve parar no fechamento desse wrapper, antes do comentário da AJ28-B.
    fim = origem.index("\n    {# ───", inicio)
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


# ---------------------------------------------------------------------------
# AJ28-B — layout de impressão próprio (cards continuam só na tela)
# ---------------------------------------------------------------------------

BLOCO_IMPRESSO_INICIO = '<section class="print-only geral-print-resumo"'


def _bloco_impresso(html):
    inicio = html.index(BLOCO_IMPRESSO_INICIO)
    return html[inicio:html.index("</section>", inicio) + len("</section>")]


def _cartoes(html):
    inicio = html.index('    <div class="d-print-none">')
    return html[inicio:html.index(BLOCO_IMPRESSO_INICIO)]


def _linha(bloco, tipo, nome):
    """Linha de uma das tabelas impressas cuja 1ª célula é `nome`."""
    inicio = bloco.index(f"geral-print-tabela-{tipo}")
    tabela = bloco[inicio:]
    tabela = tabela[:tabela.index("</table>", tabela.index("<tbody>"))]
    for linha in re.findall(r"<tr>(.*?)</tr>", tabela, flags=re.S):
        if f">{nome}<" in linha:
            return linha
    raise AssertionError(f"linha não encontrada em {tipo}: {nome}")


def _patch_dados_custom(
    monkeypatch,
    *,
    media_turma,
    freq_turma,
    media_programa,
    freq_programa,
    freq_professor,
):
    monkeypatch.setattr(
        modulo_geral,
        "calcular_estatisticas_idade",
        lambda unidade_id=None: {
            "media_geral": 21.5,
            "media_programa": media_programa,
            "media_turma": media_turma,
        },
    )
    monkeypatch.setattr(
        modulo_geral,
        "calcular_frequencias_relatorio",
        lambda turmas_do_banco, unidade_id=None: (
            88.0, freq_programa, freq_turma, freq_professor
        ),
    )
    monkeypatch.setattr(
        modulo_geral,
        "calcular_metricas_conselho",
        lambda unidade_id=None: {
            "progresso_aulas": 90.0,
            "progresso_reunioes": 66.7,
            "turmas_concluidas": 7,
            "total_turmas": 10,
        },
    )


def test_bloco_impresso_contem_todos_os_valores_da_tela(app, client, monkeypatch):
    ids = _setup(app)
    dados = _patch_dados(monkeypatch, turmas=12, professores=4, programas=2)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)
    bloco = _bloco_impresso(html)
    cartoes = _cartoes(html)

    # Contagens e sexo: exatamente os números dos cards, sem recálculo.
    comunidade = re.findall(r'<h3 class="mb-0 fw-bold">([^<]+)</h3>', cartoes)
    assert len(comunidade) == 3
    for valor in comunidade:
        assert f'<strong class="geral-print-kpi-valor">{valor}</strong>' in bloco
    sexo = re.findall(r'<h4 class="mb-0 fw-bold mt-1">([^<]+)</h4>', cartoes)
    assert len(sexo) == 3
    faixa = bloco[bloco.index("geral-print-kpi-sexo"):bloco.index("geral-print-kpi-conselho")]
    for valor in sexo:
        assert f"<strong>{valor}</strong>" in faixa

    geral = re.search(
        r'<h2 class="display-6 fw-bold mb-0 text-dark">([^<]+)</h2>', cartoes
    ).group(1)
    assert f'<strong class="geral-print-kpi-valor">{geral}</strong>' in bloco

    # Conselho: duas porcentagens + "N de M" na mesma linha de escopo.
    assert "Conteúdos registrados <strong>90%</strong>" in bloco
    assert "Ofertas avaliadas <strong>70%</strong> (7 de 10 ofertas finalizadas)" in bloco

    # Todas as chaves e todos os valores das seis listas da tela.
    for i in range(1, dados["turmas"] + 1):
        nome = f"TURMA-AJ28-{i:02d}"
        media = str(round(14.0 + i / 10, 1))
        perc = 50 + i
        linha = _linha(bloco, "turmas", nome)
        assert media in linha and f"{perc}%" in linha
    for i in range(1, dados["programas"] + 1):
        nome = f"Programa AJ28 {i}"
        linha = _linha(bloco, "programas", nome)
        assert str(float(25 + i)) in linha and f"{80 + i}%" in linha
    for i in range(1, dados["profs"] + 1):
        nome = f"PROF-AJ28-{i:02d}"
        assert f">{nome}<" in _linha(bloco, "professores", nome)
        assert f">{70 + i}%" in _linha(bloco, "professores", nome)


def test_juncao_por_chave_ausente_mostra_travessao(app, client, monkeypatch):
    ids = _setup(app)
    _patch_dados_custom(
        monkeypatch,
        media_turma={"TURMA-1": 12.34, "TURMA-2": 13.0},
        freq_turma={"TURMA-2": 88.0, "TURMA-3": 0.0},
        media_programa={"Programa A": 20.0},
        freq_programa={"Programa A": 80.0, "Programa B": 0.0},
        freq_professor={"Prof A": 75.0},
    )
    login_as(client, str(ids["user_id"]), ids["unidade"])
    bloco = _bloco_impresso(_get(client, ids).get_data(as_text=True))

    # TURMA-1: sem frequência; TURMA-2: completa; TURMA-3: sem média.
    assert "—" in _linha(bloco, "turmas", "TURMA-1")
    assert "12.3" in _linha(bloco, "turmas", "TURMA-1")
    assert "88.0%" in _linha(bloco, "turmas", "TURMA-2")
    assert "—" in _linha(bloco, "turmas", "TURMA-3")
    assert "0.0%" in _linha(bloco, "turmas", "TURMA-3")
    # Programa B existe só na frequência.
    assert "—" in _linha(bloco, "programas", "Programa B")
    assert "Programa B" in bloco


def test_ordenacao_natural_e_por_nome_no_bloco_impresso(app, client, monkeypatch):
    ids = _setup(app)
    _patch_dados_custom(
        monkeypatch,
        media_turma={
            "TURMA-10": 10.0,
            "TURMA-2": 12.0,
            "Sem número": 13.0,
            "TURMA-1": 14.0,
        },
        freq_turma={
            "TURMA-10": 10.0,
            "TURMA-2": 12.0,
            "TURMA-1": 14.0,
            "Sem número": 13.0,
        },
        media_programa={"Programa 10": 20.0, "Programa 2": 21.0},
        freq_programa={"Programa 2": 80.0, "Programa 10": 81.0},
        freq_professor={"Zélia": 70.0, "Ana": 90.0, "Bruno": 80.0},
    )
    login_as(client, str(ids["user_id"]), ids["unidade"])
    bloco = _bloco_impresso(_get(client, ids).get_data(as_text=True))

    def ordem(nomes):
        return sorted(nomes, key=bloco.index)

    assert ordem(["TURMA-1", "TURMA-2", "TURMA-10", "Sem número"]) == [
        "TURMA-1", "TURMA-2", "TURMA-10", "Sem número"
    ]
    assert ordem(["Programa 2", "Programa 10"]) == ["Programa 2", "Programa 10"]
    assert ordem(["Ana", "Bruno", "Zélia"]) == ["Ana", "Bruno", "Zélia"]


def test_marca_de_professor_segue_a_regra_do_badge(app, client, monkeypatch):
    ids = _setup(app)
    _patch_dados_custom(
        monkeypatch,
        media_turma={}, freq_turma={}, media_programa={}, freq_programa={},
        freq_professor={"Limite": 75.0, "Acima": 99.9, "Abaixo": 74.9, "Zero": 0.0},
    )
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)
    bloco = _bloco_impresso(html)

    for nome, perc in (("Limite", 75.0), ("Acima", 99.9),
                       ("Abaixo", 74.9), ("Zero", 0.0)):
        linha = _linha(bloco, "professores", nome)
        if perc >= 75:
            assert 'geral-print-marca atende">≥ 75%' in linha
            assert "bg-success-subtle text-success" in html  # badge da tela
        else:
            assert 'geral-print-marca abaixo">&lt; 75%' in linha
            assert "bg-warning-subtle text-dark" in html


def test_legenda_e_contrato_do_bloco_impresso(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)
    bloco = _bloco_impresso(html)

    for trecho in (
        "Legenda.",
        "presenças ÷ (presenças + faltas)",
        "faltas justificadas (J) não entram no cálculo",
        "A mesma regra vale para programa, turma e professor",
        "0,0% pode indicar que ainda não há lançamentos no período.",
        "Ofertas = cursos ofertados nas turmas.",
    ):
        assert trecho in bloco, trecho
    assert "h-100" not in bloco
    assert "card" not in bloco.lower()
    assert bloco.startswith(BLOCO_IMPRESSO_INICIO)

    # A tela continua com os 9 cards dentro do único wrapper d-print-none.
    assert html.count('    <div class="d-print-none">\n    <!-- Linha 1') == 1
    assert html.count('class="card h-100 shadow-sm') == 9
    css = CSS.read_text(encoding="utf-8")
    assert ".d-print-none," in css
    assert "#conteudo-impressao .geral-print-resumo" in css
    assert "#conteudo-impressao .geral-print-tabela thead" in css
    assert "display: table-header-group" in css
    assert "#conteudo-impressao .geral-print-tabela-professores" in css
    assert "#conteudo-impressao .geral-print-legenda" in css
    assert css.count("@page") == 1


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
