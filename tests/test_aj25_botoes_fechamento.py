"""AJ25 — barra de ações do fechamento do conselho (atualizada na AJ30).

Cobre o alinhamento da barra de botões com o padrão das demais telas
(`relatorios/geral.html`, `conselho/perguntas.html`, `turmas/listar.html`).
AJ30 removeu "Salvar Fechamento" (autosave por linha) e acrescentou o texto
discreto "As alterações são salvas automaticamente."; Imprimir, Exportar
.CSV e Voltar seguem intactos.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from _helpers import login_as, nova_inscricao, nova_oferta

from app.database import db
from app.models import Aluno, Curso, PeriodoLetivo, Turma, Unidade, User

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "conselho" / "fechamento.html"


def _setup(app):
    """Uma turma com oferta única e um aluno inscrito."""
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ25", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        usuario = User(
            name="User AJ25", email="aj25@teste.local", role="admin",
            first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        inicio, fim = date(2026, 2, 2), date(2026, 6, 30)
        periodo = PeriodoLetivo(
            nome="Periodo AJ25", data_inicio=inicio, data_fim=fim,
            unidade_id=unidade.id, ativo=True,
        )
        curso = Curso(nome="Curso AJ25", unidade_id=unidade.id, ativo=True)
        db.session.add_all([usuario, periodo, curso])
        db.session.flush()

        turma = Turma(
            nome="Turma AJ25", turno="Manhã", data_inicio=inicio,
            data_fim=fim, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, curso.id, unidade.id, programa="Esporte", principal=True
        )
        aluno = Aluno(nome="Aluno AJ25 01", unidade_id=unidade.id, ativo=True)
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


def test_barra_mantem_botoes_onclick_e_dprintnone(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = client.get(
        f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}"
    ).get_data(as_text=True)

    grupo = re.search(
        r'<div class="d-flex gap-2 flex-wrap justify-content-end ms-auto d-print-none">'
        r'(.*?)</div>\s*</div>',
        html,
        re.S,
    )
    assert grupo is not None, "grupo de botões da barra não renderizado"
    botoes = re.findall(
        r'<button onclick="([^"]+)" class="([^"]+)">'
        r'\s*<i class="([^"]+)"></i>\s*([^<]+?)\s*</button>',
        grupo.group(1),
    )
    assert botoes == [
        (
            "prepararImpressao()",
            "btn btn-outline-secondary",
            "bi bi-printer me-1",
            "Imprimir",
        ),
        (
            "exportTableToCSV('Turma AJ25.csv')",
            "btn btn-outline-success",
            "bi bi-file-earmark-excel me-1",
            "Exportar .CSV",
        ),
    ]
    # AJ30: botão de salvar substituído por aviso discreto de autosave.
    assert "salvarFechamento()" not in html
    assert "Salvar Fechamento" not in html
    assert '<span class="text-muted small d-print-none align-self-center">As alterações são salvas automaticamente.</span>' in html
    assert (
        '<div class="d-flex flex-wrap justify-content-between '
        'align-items-center mb-4 gap-3 d-print-none">' in html
    )


def test_barra_segue_padrao_de_layout_das_listagens():
    template = TEMPLATE.read_text(encoding="utf-8")

    # Contêiner externo: flex + wrap + gap consistente + alinhamento central.
    assert (
        '<div class="d-flex flex-wrap justify-content-between '
        'align-items-center mb-4 gap-3 d-print-none">' in template
    )
    # Título e botões na mesma linha; curso como subtítulo (evita empurrar
    # os botões para baixo), sem margem vertical residual.
    assert '<h2 class="h4 fw-bold mb-0">' in template
    assert '<p class="text-muted small mb-0">Curso: {{ oferta.curso.nome }}</p>' in template
    # Grupo dos botões com gap e quebra em tela estreita.
    # Grupo empurrado para a direita; botões alinhados à direita ao quebrar.
    assert '<div class="d-flex gap-2 flex-wrap justify-content-end ms-auto d-print-none">' in template
    # Ícone do título mantém me-2; dos botões, me-1 (padrão das telas-modelo).
    assert 'bi bi-mortarboard me-2' in template
    assert "me-2" not in re.search(
        r'<div class="d-flex gap-2 flex-wrap justify-content-end ms-auto d-print-none">'
        r'(.*?)</div>',
        template,
        re.S,
    ).group(1)


def test_voltar_para_o_painel_do_conselho(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = client.get(
        f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}"
    ).get_data(as_text=True)

    grupo = re.search(
        r'<div class="d-flex gap-2 flex-wrap justify-content-end ms-auto d-print-none">'
        r'(.*?)</div>\s*</div>',
        html,
        re.S,
    )
    assert grupo is not None, "grupo de botões da barra não renderizado"
    acoes = grupo.group(1)

    voltar = re.search(
        r'<a href="([^"]+)" class="btn btn-outline-secondary">\s*'
        r'<i class="bi bi-arrow-left me-1"></i>\s*Voltar\s*</a>',
        acoes,
    )
    assert voltar is not None, "link Voltar ausente na barra do fechamento"
    assert voltar.group(1) == "/conselho"
    # Antes dos botões de ação e dentro do grupo `d-print-none`: não entra
    # na impressão e não altera a ordem dos botões fixada no teste acima.
    assert acoes.index("<a href=") < acoes.index("<button onclick=")
    assert "prepararImpressao()" in acoes
    assert "salvarFechamento()" not in acoes
