# ruff: noqa: F811
"""V2 — integridade estrutural do template de lançamento de frequência.

O `<div class="card mb-4 p-3">` aberto na ~linha 56 (card que envolve a pauta)
ficou sem `</div>` de fechamento desde antes da entrega A1 — em `a5b34c8` a
contagem já era 30/29. O navegador "conserta" o aninhamento, então o defeito
nunca apareceu em tela, mas qualquer edição no rodapé do form podia quebrar o
layout. Este teste fixa o contrato:

    - `<div>` balanceado no arquivo (contagem + `HTMLParser`, sem Jinja);
    - nenhum `</div>` órfão;
    - o texto renderizado não muda (mesmos rótulos de antes da correção).
"""

import re
from html.parser import HTMLParser
from pathlib import Path

from test_conselho_oferta import app, client  # noqa: F401

RAIZ = Path(__file__).resolve().parents[1]
TEMPLATE = RAIZ / "app" / "templates" / "frequencia" / "lancar.html"

JINJA = re.compile(r"{#.*?#}|{%.*?%}|{{.*?}}", re.S)


def _neutralizar_jinja(texto: str) -> str:
    """Troca blocos Jinja por espaços, preservando as quebras de linha."""

    def _sub(match: re.Match) -> str:
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))

    return JINJA.sub(_sub, texto)


class _PilhaDiv(HTMLParser):
    """Empilha a linha de cada `<div>` aberto; registra `</div>` sem par."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.abertos: list[int] = []
        self.orfaos: list[int] = []

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            self.abertos.append(self.getpos()[0])

    def handle_endtag(self, tag):
        if tag != "div":
            return
        if self.abertos:
            self.abertos.pop()
        else:
            self.orfaos.append(self.getpos()[0])


def _divs(html: str) -> tuple[int, int, _PilhaDiv]:
    """(abre, fecha, parser) de um HTML já sem Jinja."""
    parser = _PilhaDiv()
    parser.feed(html)
    parser.close()
    abre = len(re.findall(r"<div\b", html, re.I))
    fecha = len(re.findall(r"</div\s*>", html, re.I))
    return abre, fecha, parser


CONTEXTO_VAZIO = {
    "turmas": [],
    "turma_id": None,
    "data": None,
    "frequencias": {},
    "valores_esportista_ativos": [],
    "valores_por_aluno": {},
    "tema_selecionado": [],
    "obs_salva": "",
    "atividades_salvas": "",
    "turma": None,
    "alunos": [],
    "datas": [],
    "temas": [],
    "meses": [],
    "ofertas": [],
    "grade_oferta_map": {},
    "oferta_atual": None,
    "is_readonly": False,
}


def test_arquivo_tem_divs_balanceados():
    html = _neutralizar_jinja(TEMPLATE.read_text(encoding="utf-8"))
    abre, fecha, parser = _divs(html)

    assert abre == fecha, (
        f"lancar.html com <div> desbalanceado: {abre} aberturas x {fecha} "
        f"fechamentos; divs abertos e não fechados nas linhas {parser.abertos}"
    )
    assert not parser.orfaos, f"</div> sem abertura nas linhas {parser.orfaos}"


def test_render_nao_perde_textos(app):
    from flask import render_template

    with app.test_request_context("/frequencia"):
        corpo = render_template("frequencia/lancar.html", **CONTEXTO_VAZIO)

    # Rótulos e blocos que existem desde a A1 — a correção do `</div>` não
    # pode ter engolido conteúdo. O rótulo do Valor/Postura vive no cartão do
    # aluno e por isso não entra aqui (o contexto vazio não tem alunos).
    for texto in (
        "Lançamento de Frequência",
        "Atividades da aula",
        "Observações da Aula",
        "Este conteúdo será arquivado no diário de classe",
        "Frequência",
    ):
        assert texto in corpo, f"texto ausente após a correção: {texto!r}"

    abre, fecha, parser = _divs(corpo)
    assert abre == fecha, (
        f"HTML renderizado desbalanceado: {abre} x {fecha} "
        f"(divs abertos: {parser.abertos})"
    )
    assert not parser.orfaos, f"</div> órfão no render: {parser.orfaos}"
