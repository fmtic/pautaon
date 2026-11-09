# ruff: noqa: F811
"""AJ16-B — lado visual do valor do esportista na AULA.

Cobre o que o servidor entrega ao navegador:
    - um único grupo de checkboxes `valor_ids` para a oferta+data (como temas),
      exibido quando existe catálogo ativo na unidade;
    - nenhum select/pergunta de valor por aluno (o campo antigo
      `postura_aluno_<id>` não existe mais);
    - estado inicial correto ao reabrir um lançamento já salvo (inclusive
      valor inativo já vinculado, marcado e rotulado como inativo);
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
from _valor_aula import cenario, corpo_pauta, definir_valores, post

ARQ_JS = (
    Path(__file__).resolve().parent.parent
    / "app" / "static" / "js" / "frequencia.js"
)

HARNESS = """
const F = require(process.argv[1]);
const casos = [
    { conceitos: ['A'], valorIds: ['7'], catalogoAtivo: true },
    { conceitos: ['A'], valorIds: [], catalogoAtivo: true },
    { conceitos: ['B'], valorIds: [], catalogoAtivo: true },
    { conceitos: ['D'], valorIds: [], catalogoAtivo: false },
    { conceitos: ['F'], valorIds: [], catalogoAtivo: true },
    { conceitos: ['J'], valorIds: ['7'], catalogoAtivo: true },
    { conceitos: [], valorIds: [], catalogoAtivo: true },
    { conceitos: ['A', 'F'], valorIds: [], catalogoAtivo: true },
];
console.log(JSON.stringify({
    presenca: F.CONCEITOS_PRESENCA,
    temPresenca: [['A'], ['F'], ['J'], [], ['A', 'F']].map(F.aulaTemPresenca),
    pendente: casos.map(F.valorAulaPendente),
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


def _grupo_valores(corpo):
    achado = re.search(
        r'<div[^>]*id="select-valor-aula".*?</div>\s*<small',
        corpo,
        re.S,
    )
    assert achado, "grupo de valores da aula não renderizou"
    return achado.group(0)


def _checkbox(corpo, valor_id):
    achado = re.search(
        r'<input[^>]*name="valor_ids"[^>]*value="%d"[^>]*>' % valor_id,
        corpo,
    )
    assert achado, f"checkbox do valor {valor_id} não renderizou"
    return achado.group(0)


# ---------------------------------------------------------------------------
# HTML: grupo único da aula (sem select por aluno)
# ---------------------------------------------------------------------------

def test_grupo_unico_de_valores_por_aula(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    corpo = corpo_pauta(client, ids)

    assert 'id="select-valor-aula"' in corpo
    assert corpo.count('name="valor_ids"') == 2  # Alegria e Foco (ativos)
    assert 'name="postura_aluno_' not in corpo


def test_estado_inicial_marca_o_conjunto_salvo(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    post(client, ids, {ids["aluno"]: "A"},
         [ids["valores"]["ativo"], ids["valores"]["outro"]])
    corpo = corpo_pauta(client, ids)

    assert "checked" in _checkbox(corpo, ids["valores"]["ativo"])
    assert "checked" in _checkbox(corpo, ids["valores"]["outro"])
    # Inativo nunca vinculado não é renderizado.
    assert "Disciplina" not in corpo


def test_valor_inativo_vinculado_aparece_marcado_e_rotulado(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])
    definir_valores(app, ids, [ids["valores"]["inativo"]])

    corpo = corpo_pauta(client, ids)

    assert "Disciplina (inativo)" in corpo
    assert "checked" in _checkbox(corpo, ids["valores"]["inativo"])


def test_valor_inativo_sem_uso_nao_aparece(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    corpo = corpo_pauta(client, ids)

    assert "Alegria" in corpo
    assert "Foco" in corpo
    assert "Disciplina" not in corpo


def test_aviso_quando_nao_ha_catalogo(app, client):
    ids = cenario(app, com_valores=False)
    login_as(client, ids["admin"], ids["un"])

    corpo = corpo_pauta(client, ids)

    assert "Nenhum valor cadastrado no planejamento." in corpo
    assert 'data-valor-obrigatorio' not in corpo


def test_form_marca_obrigatoriedade_quando_ha_catalogo(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    assert 'data-valor-obrigatorio="1"' in corpo_pauta(client, ids)


def test_aviso_desabilitado_no_html_para_o_js_controlar(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])
    corpo = corpo_pauta(client, ids)

    assert 'id="aviso-valor-pendente"' in corpo
    assert 'id="aviso-valor-pendente-texto"' in corpo


def test_readonly_desabilita_os_checkboxes(app, client):
    from app import db
    from app.models import User

    ids = cenario(app)
    with app.app_context():
        sec = User(
            name="Sec UI AJ16B", email="sec.ui.aj16b@x.com",
            role="secretaria", first_login=False, unidade_id=ids["un"],
        )
        sec.set_password("SenhaLocal!123")
        db.session.add(sec)
        db.session.commit()
        sec_id = sec.id

    login_as(client, sec_id, ids["un"])
    corpo = corpo_pauta(client, ids)

    assert "disabled" in _checkbox(corpo, ids["valores"]["ativo"])


# ---------------------------------------------------------------------------
# Aviso de cadastro: só para quem gerencia o planejamento
# ---------------------------------------------------------------------------

def test_aviso_de_cadastro_so_para_quem_gerencia_planejamento(app, client):
    ids = cenario(app, com_valores=False)

    login_as(client, ids["admin"], ids["un"])
    assert "Cadastre os valores no Planejamento" in corpo_pauta(client, ids)

    login_as(client, ids["professor"], ids["un"])
    assert "Cadastre os valores no Planejamento" not in corpo_pauta(client, ids)


def test_aviso_de_cadastro_ausente_quando_ha_catalogo(app, client):
    ids = cenario(app)
    login_as(client, ids["admin"], ids["un"])

    assert "Cadastre os valores no Planejamento" not in corpo_pauta(client, ids)


# ---------------------------------------------------------------------------
# JS: funções puras (node)
# ---------------------------------------------------------------------------

def test_js_conceitos_de_presenca(saida_js):
    assert saida_js["presenca"] == ["A", "B", "C", "D"]


def test_js_reconhece_presenca_na_aula(saida_js):
    assert saida_js["temPresenca"] == [True, False, False, False, True]


def test_js_pendencia_reproduz_a_excecao_do_servidor(saida_js):
    # (A com valor), (A sem), (B sem), (D sem valor e sem catálogo),
    # (F sem), (J com valor), (sem conceito), (A+F sem valor)
    assert saida_js["pendente"] == [
        False, True, True, False, False, False, False, True,
    ]
