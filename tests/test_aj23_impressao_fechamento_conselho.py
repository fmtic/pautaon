"""AJ23 — layout/impressão do fechamento do conselho.

Cobre o padrão de impressão aplicado a ``conselho/fechamento.html``:
cabeçalho institucional, foto só na tela, tabela com thead repetido e bordas
finas, badges legíveis em P&B, rodapé de auditoria e sincronização dos spans
de impressão com a seleção ATUAL dos selects (inclusive via Ctrl+P).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from _helpers import login_as, nova_inscricao, nova_oferta

from app.database import db
from app.models import Aluno, Curso, PeriodoLetivo, Turma, Unidade, User

RAIZ = Path(__file__).resolve().parents[1]
DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _setup(app, *, alunos=3):
    """Uma turma com oferta única e ``alunos`` inscritos (turma de vários)."""
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ23", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        usuario = User(
            name="User AJ23", email="aj23@teste.local", role="admin",
            first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        periodo = PeriodoLetivo(
            nome="Periodo AJ23", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        curso = Curso(nome="Curso AJ23", unidade_id=unidade.id, ativo=True)
        db.session.add_all([usuario, periodo, curso])
        db.session.flush()

        turma = Turma(
            nome="Turma AJ23", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, curso.id, unidade.id, programa="Esporte", principal=True
        )

        for indice in range(alunos):
            aluno = Aluno(
                nome=f"Aluno AJ23 {indice + 1}", unidade_id=unidade.id, ativo=True
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, turma.id, oferta.id)

        db.session.commit()
        return {
            "user_id": usuario.id,
            "unidade": unidade.id,
            "turma": turma.id,
            "oferta": oferta.id,
        }


def test_renderizacao_tem_foto_oculta_spans_cabecalho_e_rodapé(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])

    resposta = client.get(
        f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}"
    )
    html = resposta.get_data(as_text=True)
    assert resposta.status_code == 200
    assert html.count("data-aluno-id=") >= 3

    foto = re.search(r"<img[^>]*foto-aluno-fechamento[^>]*>", html)
    assert foto is not None, "foto do aluno não renderizada"
    assert "d-print-none" in foto.group(0)
    assert "me-3" not in foto.group(0)  # sem recuo residual no nome impresso
    assert "fechamento-aluno-linha" in html
    assert "fechamento-aluno-nome" in html

    for classe in ("situacao-texto", "proxima-texto", "nivel-texto"):
        assert classe in html

    assert "fechamento-print-header" in html
    assert "Conselho da Turma — Fechamento" in html
    assert "Emitido em" in html
    assert "fechamento-emissao" in html
    assert "print-footer-container" in html
    # O rodapé atual traz a versão da aplicação no lugar de "Impresso por:".
    assert re.search(r"v\s+\d[^<]*", html) is not None
    assert "Data/Hora:" in html
    assert "URL:" in html
    assert 'id="print-date"' in html
    assert "prepararImpressao()" in html

    selects = re.findall(r"<select[^>]*>", html)
    assert selects
    assert all("d-print-none" in tag for tag in selects)


def test_css_segue_padrao_de_impressao_dos_relatorios(client):
    css = client.get("/static/css/conselho/conselho.css").get_data(as_text=True)

    assert "@media print" in css
    assert "@page" in css and "size: A4 landscape" in css
    assert "margin: 1cm" in css
    assert "display: table-header-group" in css
    assert "break-inside: avoid" in css and "page-break-inside: avoid" in css
    assert "border: 1px solid #adb5bd !important" in css
    assert "font-size: 8.5pt" in css
    assert "background-color: #f1f3f5 !important" in css
    assert "print-color-adjust: exact" in css
    assert "#tabelaFechamento .badge" in css
    assert "border: 1px solid #212529 !important" in css
    assert ".foto-aluno-fechamento" in css
    assert "display: none !important" in css
    assert ".fechamento-print-header" in css
    assert "7.5pt" in css
    # Sem o reset da sidebar, o conteúdo sai da margem e corta na largura.
    assert ".app-main," in css
    assert "margin-left: 0 !important" in css
    assert "#conteudo-impressao .card.d-print-none" in css
    assert ".app-topbar," in css
    assert "#conteudo-impressao .fechamento-print-header" in css


def test_controles_interativos_fora_da_impressao():
    template = (
        RAIZ / "app" / "templates" / "conselho" / "fechamento.html"
    ).read_text(encoding="utf-8")

    # Resumo de tela e card de escolha de oferta (os dois cards iniciais).
    assert (
        template.count('class="card shadow-sm border-0 mb-4 d-print-none"') >= 2
    )
    linhas_legado = [
        linha for linha in template.splitlines() if "Legado:" in linha
    ]
    assert linhas_legado and all("d-print-none" in linha for linha in linhas_legado)


def test_spans_usam_selecao_atual_ate_sem_salvar():
    js = (
        RAIZ / "app" / "static" / "js" / "conselho" / "conselho.js"
    ).read_text(encoding="utf-8")

    assert "window.addEventListener('beforeprint', sincronizarSpans)" in js
    funcao = re.search(r"function prepararImpressao\(\) \{.*?\n\}", js, re.S)
    assert funcao is not None
    assert funcao.group(0).index("sincronizarSpans()") < funcao.group(
        0
    ).index("window.print()")
    # Próximo Curso: valor escolhido tem prioridade sobre o legado.
    assert "if (sel.value) return sel.options[sel.selectedIndex]?.text || '';" in js
    assert "return sel.dataset.legado || '';" in js
    assert "sel.addEventListener('change'" in js
