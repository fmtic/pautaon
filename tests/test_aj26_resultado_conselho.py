"""AJ26 — Resultado do Conselho: conceito predominante, filtro e impressão.

Cobre:
    - cálculo do conceito pela MESMA base de `percs` do fechamento;
    - coluna ``Conceito`` no lugar de ``Próximo curso / Nível``;
    - origem das datas do "Período do Conselho" (``periodo_conselho``);
    - filtro de turmas em checkboxes, restrito ao período letivo;
    - padrão de impressão da AJ23 e CSV com a nova coluna.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from _helpers import login_as, nova_inscricao, nova_oferta

from app.database import db
from app.models import (
    Aluno,
    ConfiguracaoSistema,
    ConselhoClasse,
    Curso,
    Frequencia,
    PeriodoConselho,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho
from app.utils.logica import (
    calcular_estatisticas_frequencia,
    conceito_predominante,
    percs_por_conceito,
)

RAIZ = Path(__file__).resolve().parents[1]
DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _setup(app):
    """Duas turmas no período 1, uma no período 2, com conselhos fechados."""
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ26", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        usuario = User(
            name="User AJ26", email="aj26@teste.local", role="admin",
            first_login=False, unidade_id=unidade.id,
        )
        usuario.set_password("SenhaLocal!123")
        p1 = PeriodoLetivo(
            nome="Período AJ26-1", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        p2 = PeriodoLetivo(
            nome="Período AJ26-2", data_inicio=date(2026, 8, 1),
            data_fim=date(2026, 12, 18), unidade_id=unidade.id, ativo=True,
        )
        curso = Curso(nome="Curso AJ26", unidade_id=unidade.id, ativo=True)
        db.session.add_all([usuario, p1, p2, curso])
        db.session.flush()

        turmas = {}
        ofertas = {}
        for chave, nome, periodo in (
            ("a", "Turma Alfa AJ26", p1),
            ("b", "Turma Beta AJ26", p1),
            ("c", "Turma Gama AJ26", p2),
        ):
            turma = Turma(
                nome=nome, turno="Manhã", data_inicio=periodo.data_inicio,
                data_fim=periodo.data_fim, periodo_letivo_id=periodo.id,
                unidade_id=unidade.id, ativo=True,
            )
            db.session.add(turma)
            db.session.flush()
            turmas[chave] = turma
            ofertas[chave] = nova_oferta(
                turma.id, curso.id, unidade.id, programa="Esporte", principal=True
            )

        # Janela de fechamento do período 1 + janela de outro período.
        db.session.add_all([
            PeriodoConselho(
                nome="Conselho Final AJ26-1", data_inicio=date(2026, 6, 1),
                data_fim=date(2026, 6, 20), conselho_final=True,
                periodo_letivo_id=p1.id, unidade_id=unidade.id,
            ),
            PeriodoConselho(
                nome="Conselho Final AJ26-2", data_inicio=date(2026, 11, 2),
                data_fim=date(2026, 11, 13), conselho_final=True,
                periodo_letivo_id=p2.id, unidade_id=unidade.id,
            ),
        ])
        # Fonte antiga (errada) com datas bem diferentes, para provar que o
        # relatório não as usa.
        db.session.add_all([
            ConfiguracaoSistema(chave="inicio_conselho", valor="1999-01-02"),
            ConfiguracaoSistema(chave="fim_conselho", valor="1999-01-30"),
        ])

        alunos = {}
        conceitos = {
            "unico": ["A", "A", "A", "F"],
            "empate": ["A", "A", "B", "B"],
            "sem_lancamento": [],
            "so_f_e_j": ["F", "J", "J"],
            "com_f_e_j": ["B", "B", "B", "A", "F", "J"],
        }
        for chave, lista_conceitos in conceitos.items():
            aluno = Aluno(
                nome=f"Aluno {chave} AJ26", unidade_id=unidade.id, ativo=True
            )
            db.session.add(aluno)
            db.session.flush()
            alunos[chave] = aluno
            nova_inscricao(aluno.id, turmas["a"].id, ofertas["a"].id)
            db.session.add(ConselhoClasse(
                aluno_id=aluno.id, turma_id=turmas["a"].id,
                turma_curso_id=ofertas["a"].id, etapa=EtapaConselho.FINAL,
                unidade_id=unidade.id, situacao_final="Aprovado",
                concluido=True, data_inicio=DATA_INI, data_fim=DATA_FIM,
            ))
            for indice, conceito in enumerate(lista_conceitos):
                db.session.add(Frequencia(
                    aluno_id=aluno.id, turma_id=turmas["a"].id,
                    turma_curso_id=ofertas["a"].id,
                    data=DATA_INI + timedelta(days=indice),
                    conceito=conceito, unidade_id=unidade.id,
                ))

        db.session.commit()
        return {
            "user_id": usuario.id,
            "unidade": unidade.id,
            "p1": p1.id,
            "p2": p2.id,
            "turma_a": turmas["a"].id,
            "turma_b": turmas["b"].id,
            "turma_c": turmas["c"].id,
            "oferta_a": ofertas["a"].id,
        }


def _get(client, ids, **params):
    consulta = {"periodo_letivo_id": ids["p1"], "turmas": ids["turma_a"]}
    consulta.update(params)
    return client.get("/relatorios/conselho", query_string=consulta)


# ---------------------------------------------------------------------------
# Regra do conceito — base única
# ---------------------------------------------------------------------------

def test_conceito_unico_empate_e_sem_lancamento():
    assert conceito_predominante(
        calcular_estatisticas_frequencia(["A", "A", "A", "F"])
    ) == "A — 75%"
    assert conceito_predominante(
        calcular_estatisticas_frequencia(["A", "A", "B", "B"])
    ) == "A/B — 50%"
    assert conceito_predominante(
        calcular_estatisticas_frequencia([])
    ) == "—"
    # Só F/J: nenhum conceito A–D concorre.
    assert conceito_predominante(
        calcular_estatisticas_frequencia(["F", "J", "J"])
    ) == "—"


def test_conceito_ignora_f_e_j_no_ranking_mas_mantem_denominador():
    estatisticas = calcular_estatisticas_frequencia(
        ["B", "B", "B", "A", "F", "J"]
    )
    percs = percs_por_conceito(estatisticas)
    assert percs["B"] == 50.0
    assert percs["A"] == 16.7
    assert percs["F"] == 16.7
    assert percs["J"] == 16.7
    assert conceito_predominante(estatisticas) == "B — 50%"


def test_conceito_usa_arredondamento_do_fechamento_e_empate_amplo():
    estatisticas = calcular_estatisticas_frequencia(["A", "B", "C", "D"])
    assert percs_por_conceito(estatisticas)["A"] == 25.0
    assert conceito_predominante(estatisticas) == "A/B/C/D — 25%"
    estatisticas = calcular_estatisticas_frequencia(["A", "B", "C"])
    assert conceito_predominante(estatisticas) == "A/B/C — 33.3%"


# ---------------------------------------------------------------------------
# Renderização e origem das datas
# ---------------------------------------------------------------------------

def test_render_com_coluna_conceito_e_sem_coluna_antiga(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    resposta = _get(client, ids)
    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert "<th" in html and "Conceito</th>" in html
    assert "Próximo curso / Nível" not in html
    assert "Próximo curso" not in html
    assert "A — 75%" in html
    assert "A/B — 50%" in html
    assert "B — 50%" in html
    assert "class=\"px-3 py-2 text-center small conceito-predominante\"" in html


def test_periodo_do_conselho_vem_de_periodo_conselho_do_periodo(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    html = _get(client, ids).get_data(as_text=True)
    # Janela FINAL do período 1 cadastrada em `periodo_conselho`.
    assert "01/06/2026" in html
    assert "20/06/2026" in html
    # Datas globais da configuração antiga não aparecem.
    assert "02/01/1999" not in html
    assert "30/01/1999" not in html

    html2 = _get(client, ids, periodo_letivo_id=ids["p2"],
                 turmas=ids["turma_c"]).get_data(as_text=True)
    assert "02/11/2026" in html2
    assert "13/11/2026" in html2
    assert "01/06/2026" not in html2


def test_periodo_sem_janela_final_mostra_traco(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    with app.app_context():
        PeriodoConselho.query.filter_by(periodo_letivo_id=ids["p1"]).delete()
        db.session.commit()

    html = _get(client, ids).get_data(as_text=True)
    assert "Período do Conselho" in html
    assert "01/06/2026" not in html
    assert "02/01/1999" not in html


# ---------------------------------------------------------------------------
# Filtro de turmas
# ---------------------------------------------------------------------------

def test_filtro_tem_checkboxes_busca_e_botoes(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    html = _get(client, ids).get_data(as_text=True)
    assert 'id="turmas_select"' not in html
    assert 'name="turmas" multiple' not in html
    assert 'id="buscaTurmas"' in html
    assert 'id="listaTurmas"' in html
    assert 'id="marcarTodasTurmas"' in html
    assert 'id="limparTurmas"' in html
    checkboxes = re.findall(r'<input[^>]*name="turmas"[^>]*>', html)
    assert len(checkboxes) == 2
    assert all('type="checkbox"' in tag for tag in checkboxes)
    assert "Turma Alfa AJ26" in html and "Turma Beta AJ26" in html
    assert "Curso AJ26" in html


def test_filtro_lista_apenas_turmas_do_periodo_selecionado(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    html_p1 = _get(client, ids).get_data(as_text=True)
    assert "Turma Alfa AJ26" in html_p1
    assert "Turma Beta AJ26" in html_p1
    assert "Turma Gama AJ26" not in html_p1

    html_p2 = _get(client, ids, periodo_letivo_id=ids["p2"],
                   turmas=ids["turma_c"]).get_data(as_text=True)
    assert "Turma Gama AJ26" in html_p2
    assert "Turma Alfa AJ26" not in html_p2
    assert "Turma Beta AJ26" not in html_p2


def test_todas_as_turmas_desabilita_lista_e_mantem_parametros(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    resposta = _get(client, ids, turmas_all=1, oferta_sel=ids["oferta_a"])
    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200  # oferta_sel continua aceito na rota
    assert 'id="turmas_all"' in html and "checked" in html
    checkboxes = re.findall(r'<input[^>]*name="turmas"[^>]*>', html)
    assert checkboxes and all("disabled" in tag for tag in checkboxes)
    assert "name=\"periodo_letivo_id\"" in html
    assert "name=\"turmas_all\"" in html
    template = (
        RAIZ / "app" / "templates" / "relatorios" / "resultado_conselho.html"
    ).read_text(encoding="utf-8")
    assert 'name="oferta_sel"' in template


def test_isolamento_por_unidade_continua_valido(app, client):
    ids = _setup(app)
    with app.app_context():
        outra = Unidade(nome="Unidade AJ26-B", ativo=True)
        db.session.add(outra)
        db.session.flush()
        usuario = User(
            name="Forasteiro AJ26", email="aj26b@teste.local", role="admin",
            first_login=False, unidade_id=outra.id,
        )
        usuario.set_password("SenhaLocal!123")
        db.session.add(usuario)
        db.session.commit()
        outro_id = usuario.id

    login_as(client, str(outro_id), ids["unidade"] + 1)
    resposta = _get(client, ids)
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert "Turma Alfa AJ26" not in html
    assert "Aluno unico AJ26" not in html


# ---------------------------------------------------------------------------
# Impressão e CSV (contrato de arquivos)
# ---------------------------------------------------------------------------

def test_cabecalho_de_impressao_tem_periodo_do_conselho_e_escopo(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    html = _get(client, ids).get_data(as_text=True)
    assert 'id="conteudo-impressao"' in html
    header = re.search(r'<header[^>]*resultado-print-header.*?</header>', html, re.S)
    assert header is not None
    trecho = header.group(0)
    for texto in (
        "resultado-print-header", "report-logo", "Resultado do Conselho",
        "Período do Conselho", "01/06/2026", "20/06/2026", "Emitido em",
        "resultado-emissao", "Colaborador:", "Escopo:",
    ):
        assert texto in trecho
    assert "print-footer-container" in html
    assert "Data/Hora:" in html
    assert "URL:" in html
    assert 'id="print-date"' in html
    assert "prepararImpressao()" in html
    # Foto de aluno nunca entra no relatório.
    assert "foto_aluno" not in html
    assert "foto-aluno" not in html


def test_controles_e_cards_fora_da_impressao(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = _get(client, ids).get_data(as_text=True)

    assert 'class="card filter-card shadow-sm mb-4 no-print d-print-none"' in html
    assert 'class="row g-3 mb-4 d-print-none"' in html
    assert 'class="card status-card shadow-sm mb-4 d-print-none"' in html

    template = (
        RAIZ / "app" / "templates" / "relatorios" / "resultado_conselho.html"
    ).read_text(encoding="utf-8")
    assert "alert alert-warning no-print d-print-none" in template
    assert "resumo de status é omitido" in template


def test_css_de_impressao_segue_padrao_aj23(client):
    css = client.get("/static/css/relatorios/resultado_conselho.css").get_data(
        as_text=True
    )
    assert "@media print" in css
    assert "@page" in css and "size: A4 landscape" in css
    assert "margin: 1cm" in css
    assert "display: table-header-group" in css
    assert "break-inside: avoid" in css and "page-break-inside: avoid" in css
    assert "border: 1px solid #adb5bd !important" in css
    assert "font-size: 8.5pt" in css
    assert "background-color: #f1f3f5 !important" in css
    assert "print-color-adjust: exact" in css
    assert "#tabelaResultado .badge" in css
    assert "border: 1px solid #212529 !important" in css
    assert ".resultado-print-header" in css
    assert "#conteudo-impressao .resultado-print-header" in css
    assert "7.5pt" in css
    assert "margin-left: 0 !important" in css
    assert "#conteudo-impressao .card.d-print-none" in css


def test_js_tem_beforeprint_e_csv_com_nova_coluna():
    js = (RAIZ / "app" / "static" / "js" / "relatorios"
          / "resultado_conselho.js").read_text(encoding="utf-8")
    assert "window.addEventListener('beforeprint', preencherEmissao)" in js
    funcao = re.search(r"function prepararImpressao\(\) \{.*?\n    \}", js, re.S)
    assert funcao is not None
    assert funcao.group(0).index("preencherEmissao()") < funcao.group(0).index(
        "window.print()"
    )
    assert "window.exportarCSV = exportarCSV" in js
    assert "tabelaResultado" in js
    assert "Próximo curso" not in js
    assert "Conceito" not in js  # o cabeçalho vem do DOM da tabela
    assert "periodo.addEventListener('change'" in js
    assert "url.searchParams.delete('turmas')" in js
    assert "url.searchParams.delete('turmas_all')" in js
    assert "url.searchParams.delete('oferta_sel')" in js
