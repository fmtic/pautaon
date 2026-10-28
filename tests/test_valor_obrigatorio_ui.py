# ruff: noqa: F811
"""V2 — lado visual da obrigatoriedade (HTML renderizado + funções do JS).

Cobre o que o servidor entrega ao navegador:

    - `required` no select de Valor/Postura quando o conceito é A–D e existe
      catálogo ativo na unidade; `disabled` e sem `required` em F/J e sem
      conceito;
    - estado inicial correto ao reabrir um lançamento já salvo (valor
      selecionado, select habilitado);
    - `data-valor-obrigatorio` no form só quando há catálogo (mesma exceção do
      servidor, que evita bloquear a pauta de unidade sem valores);
    - aviso "Cadastre os valores no Planejamento" visível apenas para perfis que
      gerenciam o planejamento;
    - funções puras do `frequencia.js` executadas em node.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from _helpers import login_as
from test_conselho_oferta import app, client  # noqa: F401
from test_valor_obrigatorio import _cenario, _post, _url_pauta

ARQ_JS = (
    Path(__file__).resolve().parent.parent
    / "app" / "static" / "js" / "frequencia.js"
)

HARNESS = """
const F = require(process.argv[1]);
const casos = [
    { conceito: 'A', valorId: '7', catalogoAtivo: true },
    { conceito: 'A', valorId: '', catalogoAtivo: true },
    { conceito: 'B', valorId: '', catalogoAtivo: true },
    { conceito: 'D', valorId: '', catalogoAtivo: false },
    { conceito: 'F', valorId: '', catalogoAtivo: true },
    { conceito: 'J', valorId: '7', catalogoAtivo: true },
    { conceito: '', valorId: '', catalogoAtivo: true },
];
console.log(JSON.stringify({
    presenca: F.CONCEITOS_PRESENCA,
    exige: ['A', 'B', 'C', 'D', 'F', 'J', ''].map(F.exigeValorEsportista),
    pendente: casos.map(F.valorEsportistaPendente),
}));
"""


@pytest.fixture(scope="module")
def node():
    caminho = shutil.which("node")
    if caminho is None:  # skip documentado: sem suíte JS no repo
        pytest.skip("node não disponível no PATH — regra validada só no servidor")
    return caminho


@pytest.fixture(scope="module")
def saida_js(node):
    processo = subprocess.run(
        [node, "-e", HARNESS, str(ARQ_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert processo.returncode == 0, processo.stderr
    return json.loads(processo.stdout)


def _select_postura(corpo, aluno_id):
    """A tag `<select>` do Valor do Esportista daquele aluno."""
    achado = re.search(
        r'<select[^>]*name="postura_aluno_%d"[^>]*>' % aluno_id, corpo,
    )
    assert achado, "select do Valor do Esportista não renderizou"
    return achado.group(0)


def _corpo_pauta(client, ids):
    return client.get(_url_pauta(ids)).get_data(as_text=True)


# ---------------------------------------------------------------------------
# HTML: required × disabled
# ---------------------------------------------------------------------------

def test_select_exige_valor_quando_ha_presenca_salva(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    _post(client, ids, {aluno: "A"}, {aluno: ids["valores"]["ativo"]})
    corpo = _corpo_pauta(client, ids)
    tag = _select_postura(corpo, aluno)

    assert "required" in tag
    assert "disabled" not in tag
    # Estado inicial ao reabrir: o valor salvo continua selecionado.
    assert f'value="{ids["valores"]["ativo"]}" selected' in corpo


def test_select_sem_conceito_fica_desabilitado_e_sem_required(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])

    tag = _select_postura(_corpo_pauta(client, ids), ids["alunos"][0])

    assert "disabled" in tag
    assert "required" not in tag


@pytest.mark.parametrize("conceito", ["F", "J"])
def test_select_desabilitado_em_falta_e_justificada(app, client, conceito):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    aluno = ids["alunos"][0]

    _post(client, ids, {aluno: "A"}, {aluno: ids["valores"]["ativo"]})
    _post(client, ids, {aluno: conceito})
    tag = _select_postura(_corpo_pauta(client, ids), aluno)

    assert "disabled" in tag
    assert "required" not in tag


def test_sem_required_quando_unidade_nao_tem_catalogo(app, client):
    ids = _cenario(app, com_valores=False)
    login_as(client, ids["admin"], ids["un"])

    corpo = _corpo_pauta(client, ids)
    tag = _select_postura(corpo, ids["alunos"][0])

    assert "disabled" in tag
    assert "required" not in tag
    assert 'data-valor-obrigatorio' not in corpo


def test_form_marca_obrigatoriedade_quando_ha_catalogo(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])

    assert 'data-valor-obrigatorio="1"' in _corpo_pauta(client, ids)


def test_aviso_desabilitado_no_html_para_o_js_controlar(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    corpo = _corpo_pauta(client, ids)

    assert 'id="aviso-valor-pendente"' in corpo
    assert 'id="aviso-valor-pendente-texto"' in corpo


# ---------------------------------------------------------------------------
# Aviso de cadastro: só para quem gerencia o planejamento
# ---------------------------------------------------------------------------

def test_aviso_de_cadastro_so_para_quem_gerencia_planejamento(app, client):
    ids = _cenario(app, com_valores=False)

    login_as(client, ids["admin"], ids["un"])
    assert "Cadastre os valores no Planejamento" in _corpo_pauta(client, ids)

    login_as(client, ids["professor"], ids["un"])
    assert "Cadastre os valores no Planejamento" not in _corpo_pauta(client, ids)


def test_aviso_de_cadastro_ausente_quando_ha_catalogo(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])

    assert "Cadastre os valores no Planejamento" not in _corpo_pauta(client, ids)


# ---------------------------------------------------------------------------
# JS: funções puras (node)
# ---------------------------------------------------------------------------

def test_js_conceitos_de_presenca(saida_js):
    assert saida_js["presenca"] == ["A", "B", "C", "D"]


def test_js_exige_valor_apenas_em_presenca(saida_js):
    # A, B, C, D, F, J, ""
    assert saida_js["exige"] == [True, True, True, True, False, False, False]


def test_js_pendencia_reproduz_a_excecao_do_servidor(saida_js):
    # (A com valor), (A sem valor), (B sem), (D sem valor e sem catálogo),
    # (F sem), (J com valor), ("" sem valor)
    assert saida_js["pendente"] == [False, True, True, False, False, False, False]
