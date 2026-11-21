"""AJ27 — Resultado do Conselho: quebra natural, coluna Conceito e separador.

Cobre:
    - ordem final das colunas na tela e no CSV (CSV é gerado do DOM);
    - classe ``inicio-turma`` na 1ª linha de cada turma/oferta;
    - neutralização da regra global ``.table { page-break-inside: avoid
      !important }`` e do card que envolve a tabela;
    - contratos de impressão da AJ26 preservados.
"""

from __future__ import annotations

import re
from pathlib import Path

from _helpers import login_as, nova_inscricao
from test_aj26_resultado_conselho import _get, _setup

from app.database import db
from app.models import Aluno, ConselhoClasse, TurmaCurso
from app.models.enums import EtapaConselho

RAIZ = Path(__file__).resolve().parents[1]
COLUNAS = [
    "Turma",
    "Programa",
    "Professor",
    "Aluno",
    "Nível",
    "Conceito",
    "Presença",
    "Situação Final",
]


def _com_segunda_turma(app):
    """Acrescenta uma linha na turma Beta para existir 2 grupos na tabela."""
    ids = _setup(app)
    with app.app_context():
        oferta_b = (
            TurmaCurso.query.filter_by(turma_id=ids["turma_b"], ativo=True)
            .order_by(TurmaCurso.id)
            .first()
        )
        assert oferta_b is not None
        aluno = Aluno(
            nome="Aluno Segunda Turma AJ27",
            unidade_id=ids["unidade"],
            ativo=True,
        )
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, ids["turma_b"], oferta_b.id)
        db.session.add(ConselhoClasse(
            aluno_id=aluno.id,
            turma_id=ids["turma_b"],
            turma_curso_id=oferta_b.id,
            etapa=EtapaConselho.FINAL,
            unidade_id=ids["unidade"],
            situacao_final="Aprovado",
            concluido=True,
        ))
        db.session.commit()
    return ids


def _corpo(html):
    return html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]


def test_ordem_das_colunas_na_tela_e_no_csv(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids, turmas_all=1).get_data(as_text=True)

    cabecalho = html.split('id="tabelaResultado"', 1)[1].split("<thead>", 1)[1]
    cabecalho = cabecalho.split("</thead>", 1)[0]
    colunas = [
        re.sub(r"<[^>]+>", "", valor).strip()
        for valor in re.findall(r"<th[^>]*>(.*?)</th>", cabecalho, re.S)
    ]
    assert colunas == COLUNAS
    assert colunas.index("Conceito") == colunas.index("Nível") + 1
    assert colunas.index("Conceito") < colunas.index("Presença")

    # O CSV não tem lista própria de cabeçalhos: lê `th, td` do DOM, então a
    # ordem exportada é exatamente a ordem acima.
    js = (
        RAIZ / "app" / "static" / "js" / "relatorios" / "resultado_conselho.js"
    ).read_text(encoding="utf-8")
    assert "querySelectorAll('th, td')" in js
    assert "querySelectorAll('tr')" in js
    assert "ordem das colunas do CSV vem do DOM" in js


def test_separador_na_primeira_linha_de_cada_turma(app, client):
    ids = _com_segunda_turma(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids, turmas_all=1).get_data(as_text=True)
    linhas = re.findall(r"<tr([^>]*)>", _corpo(html))

    assert len(linhas) == 6
    assert "inicio-turma" not in linhas[0]  # primeira turma da tabela
    assert all("inicio-turma" not in atributos for atributos in linhas[1:5])
    assert "inicio-turma" in linhas[5]  # 1ª linha da turma Beta
    # A 1ª turma da tabela não recebe separador (é o início do conjunto).
    assert sum("inicio-turma" in atributos for atributos in linhas) == 1

    # O agrupamento é por turma + oferta, gerado no template (não por JS).
    template = (
        RAIZ / "app" / "templates" / "relatorios" / "resultado_conselho.html"
    ).read_text(encoding="utf-8")
    assert "loop.changed((linha.turma, linha.oferta))" in template
    assert "'inicio-turma' if inicio_grupo and not loop.first else ''" in template


def test_wrapper_da_tabela_nao_herda_report_header(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)

    assert 'class="card shadow-sm mb-5 resultado-tabela-card"' in html
    # A primeira linha da tabela não é marcada, e a classe do separador não
    # vem de JS.
    assert 'class="inicio-turma"' not in html
    assert "inicio-turma" not in (
        RAIZ / "app" / "static" / "js" / "relatorios" / "resultado_conselho.js"
    ).read_text(encoding="utf-8")


def test_css_anula_avoid_global_e_nao_quebra_entre_turmas(client):
    css = client.get("/static/css/relatorios/resultado_conselho.css").get_data(
        as_text=True
    )

    bloco_wrapper = css.split("#conteudo-impressao .resultado-tabela-card {", 1)[1]
    bloco_wrapper = bloco_wrapper.split("}", 1)[0]
    assert "break-inside: auto !important" in bloco_wrapper
    assert "page-break-inside: auto !important" in bloco_wrapper
    assert "overflow: visible !important" in bloco_wrapper
    assert "margin: 0 !important" in bloco_wrapper

    bloco_tabela = css.split("#tabelaResultado {", 1)[1].split("}", 1)[0]
    assert "page-break-inside: auto !important" in bloco_tabela
    assert "break-inside: auto !important" in bloco_tabela

    bloco_separador = css.split("#tabelaResultado tbody tr.inicio-turma {", 1)[1]
    bloco_separador = bloco_separador.split("}", 1)[0]
    assert "border-top: 2pt dashed #212529 !important" in bloco_separador
    assert "break-before" not in css
    assert "page-break-before" not in css

    # AJ26 preservada.
    assert "@page" in css and "size: A4 landscape" in css
    assert "display: table-header-group" in css
    bloco_linha = css.split("#tabelaResultado tbody tr {", 1)[1].split("}", 1)[0]
    assert "break-inside: avoid" in bloco_linha
    assert "page-break-inside: avoid" in bloco_linha
