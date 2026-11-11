"""AJ18-C2 — UI: Aluno ainda não entrado na oferta renderiza desabilitado.

Cobre a interface de lançamento (lancar.html, frequencia.js e core.py GET):
1. GET em data anterior à entrada renderiza o aluno desabilitado com
   "Entrou em dd/mm" e sem name nos inputs de rádio;
2. Na data de entrada e depois, renderiza normal (com name e sem disabled);
3. Aluno com entrada NULL sempre normal em qualquer data;
4. Regressão: oferta sem nenhuma data de entrada renderiza HTML idêntico ao padrão;
5. Ida e volta: POST com o formulário renderizado em data anterior grava apenas
   os alunos elegíveis e não grava o aluno desabilitado;
6. Valor obrigatório A–D: aluno desabilitado não conta para a obrigatoriedade
   de valores do esportista;
7. JS estático: funções puras em frequencia.js executadas via node confirmando
   que conceitosMarcados ignora inputs :disabled.
"""

from datetime import date, time, timedelta
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from _helpers import (
    dia_de_aula_ate, hoje_ref, login_as, nova_inscricao, nova_oferta,
)
from app import db
from app.models import (
    Aluno, Curso, Frequencia, PeriodoLetivo, Turma,
    TurmaCurso, Unidade, User, ValorEsportista,
)
from app.models.enums import ConceitoFrequencia
from app.services.turma_curso import datas_aula_oferta
from app.utils.frequencia import datas_bloqueadas_str

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())
DIAS_GRADE = "Segunda, Quarta"
DATA_ENTRADA_DOIS = date(2026, 10, 12)

ARQ_JS = (
    Path(__file__).resolve().parent.parent
    / "app" / "static" / "js" / "frequencia.js"
)


def _usuario(nome, email, role, unidade_id):
    user = User(
        name=nome, email=email, role=role, first_login=False,
        unidade_id=unidade_id,
    )
    user.set_password("SenhaLocal!123")
    return user


def _seed(app, *, entrada_dois=DATA_ENTRADA_DOIS, com_valores=False):
    with app.app_context():
        un = Unidade(nome="Unidade AJ18C2", ativo=True)
        db.session.add(un)
        db.session.flush()

        prof = _usuario("Prof AJ18C2", "prof.aj18c2@x.com", "professor", un.id)
        admin = _usuario("Admin AJ18C2", "admin.aj18c2@x.com", "admin", un.id)
        db.session.add_all([prof, admin])
        db.session.flush()

        ini = HOJE - timedelta(days=40)
        fim = HOJE + timedelta(days=40)
        periodo = PeriodoLetivo(
            nome="P AJ18C2", data_inicio=ini, data_fim=fim, unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma AJ18C2", unidade_id=un.id,
            periodo_letivo_id=periodo.id, professor_id=prof.id, ativo=True,
            data_inicio=ini, data_fim=fim,
        )
        db.session.add(turma)
        db.session.flush()

        curso = Curso(nome="Curso AJ18C2", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        oferta = nova_oferta(
            turma.id, curso.id, un.id, principal=True,
            professor_id=prof.id, dias_semana=DIAS_GRADE,
            hora_inicio=time(8), hora_fim=time(10),
        )

        aluno_um = Aluno(nome="Aluno Um C2", unidade_id=un.id, ativo=True)
        aluno_dois = Aluno(nome="Aluno Dois C2", unidade_id=un.id, ativo=True)
        db.session.add_all([aluno_um, aluno_dois])
        db.session.flush()

        nova_inscricao(aluno_um.id, turma.id, oferta.id)
        nova_inscricao(
            aluno_dois.id, turma.id, oferta.id,
            data_entrada_oferta=entrada_dois,
        )

        valor_id = None
        if com_valores:
            val = ValorEsportista(
                nome="Disciplina C2", unidade_id=un.id, ativo=True,
            )
            db.session.add(val)
            db.session.flush()
            valor_id = val.id

        db.session.commit()
        return {
            "un": un.id, "prof": prof.id, "admin": admin.id,
            "turma": turma.id, "oferta": oferta.id,
            "aluno_um": aluno_um.id, "aluno_dois": aluno_dois.id,
            "alunos": [aluno_um.id, aluno_dois.id],
            "valor_id": valor_id,
        }


def _datas_ate_hoje(app, ids, oferta_id):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        turma = db.session.get(Turma, ids["turma"])
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        return [
            d for d in datas_aula_oferta(oferta, blocked=blocked) if d <= HOJE
        ]


def _iso(d):
    return d.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# 1) GET em data anterior à entrada
# ---------------------------------------------------------------------------
def test_get_data_anterior_renderiza_desabilitado_com_rotulo_e_sem_name(app, client):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_antes = next(d for d in datas if d < DATA_ENTRADA_DOIS)

    login_as(client, ids["prof"], ids["un"])

    url = f"/frequencia?turma_id={ids['turma']}&turma_curso={ids['oferta']}&data={_iso(data_antes)}"
    resp = client.get(url)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # 1. Indicação "Entrou em dd/mm" presente para o aluno 2
    esperado_rotulo = f"Entrou em {DATA_ENTRADA_DOIS.strftime('%d/%m')}"
    assert esperado_rotulo in html, f"Esperava rótulo '{esperado_rotulo}' no HTML"

    # 2. Aluno 2 NÃO deve ter o atributo name="aluno_<id>"
    name_aluno_dois = f'name="aluno_{ids["aluno_dois"]}"'
    assert name_aluno_dois not in html, (
        f"Aluno de entrada futura não deve ter {name_aluno_dois} nos inputs"
    )

    # 3. Os inputs do aluno 2 devem conter disabled
    # Cada conceito A, B, C, D, F, J do aluno 2 tem id="aluno_<id>_<c>" e disabled
    for c in ["A", "B", "C", "D", "F", "J"]:
        id_input = f'id="aluno_{ids["aluno_dois"]}_{c}"'
        assert id_input in html
        # Busca a tag input com esse id e confere se tem disabled
        tag = re.search(r'<input[^>]*id="' + re.escape(f"aluno_{ids['aluno_dois']}_{c}") + r'"[^>]*>', html)
        assert tag is not None
        assert "disabled" in tag.group(0)

    # 4. Aluno 1 (entrada NULL) renderiza NORMAL com name e SEM disabled
    name_aluno_um = f'name="aluno_{ids["aluno_um"]}"'
    assert name_aluno_um in html
    tag_um = re.search(r'<input[^>]*id="' + re.escape(f"aluno_{ids['aluno_um']}_A") + r'"[^>]*>', html)
    assert tag_um is not None
    assert name_aluno_um in tag_um.group(0)
    assert "disabled" not in tag_um.group(0)


# ---------------------------------------------------------------------------
# 2) GET na data de entrada ou posterior
# ---------------------------------------------------------------------------
def test_get_data_na_entrada_ou_posterior_renderiza_normal(app, client):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_apos = next(d for d in datas if d >= DATA_ENTRADA_DOIS)

    login_as(client, ids["prof"], ids["un"])

    url = f"/frequencia?turma_id={ids['turma']}&turma_curso={ids['oferta']}&data={_iso(data_apos)}"
    resp = client.get(url)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Nenhum rótulo "Entrou em" deve aparecer
    assert "Entrou em" not in html

    # Ambos os alunos têm name="aluno_<id>" e NÃO têm disabled
    for aid in (ids["aluno_um"], ids["aluno_dois"]):
        name_aluno = f'name="aluno_{aid}"'
        assert name_aluno in html
        tag = re.search(r'<input[^>]*id="' + re.escape(f"aluno_{aid}_A") + r'"[^>]*>', html)
        assert tag is not None
        assert name_aluno in tag.group(0)
        assert "disabled" not in tag.group(0)


# ---------------------------------------------------------------------------
# 3) Aluno com entrada NULL sempre normal
# ---------------------------------------------------------------------------
def test_aluno_entrada_null_sempre_normal(app, client):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])

    login_as(client, ids["prof"], ids["un"])

    for d in datas[:3]:
        url = f"/frequencia?turma_id={ids['turma']}&turma_curso={ids['oferta']}&data={_iso(d)}"
        resp = client.get(url)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        name_aluno_um = f'name="aluno_{ids["aluno_um"]}"'
        assert name_aluno_um in html
        tag = re.search(r'<input[^>]*id="' + re.escape(f"aluno_{ids['aluno_um']}_A") + r'"[^>]*>', html)
        assert tag is not None
        assert "disabled" not in tag.group(0)


# ---------------------------------------------------------------------------
# 4) Regressão: oferta sem nenhuma entrada definida
# ---------------------------------------------------------------------------
def test_regressao_oferta_sem_entrada_renderiza_todos_normais(app, client):
    ids = _seed(app, entrada_dois=None)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])

    login_as(client, ids["prof"], ids["un"])

    url = f"/frequencia?turma_id={ids['turma']}&turma_curso={ids['oferta']}&data={_iso(datas[0])}"
    resp = client.get(url)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "Entrou em" not in html
    assert f'name="aluno_{ids["aluno_um"]}"' in html
    assert f'name="aluno_{ids["aluno_dois"]}"' in html


# ---------------------------------------------------------------------------
# 5) Ida e volta: POST do form renderizado em data anterior
# ---------------------------------------------------------------------------
def test_ida_e_volta_post_grava_somente_aluno_elegivel(app, client):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_antes = next(d for d in datas if d < DATA_ENTRADA_DOIS)

    login_as(client, ids["prof"], ids["un"])

    # Simula o envio do formulário exatamente como sai da tela:
    # inputs do aluno 2 não têm name, então o navegador envia só aluno 1.
    dados = {
        "turma": str(ids["turma"]),
        "turma_curso": str(ids["oferta"]),
        "data": _iso(data_antes),
        f"aluno_{ids['aluno_um']}": "A",
    }
    resp = client.post("/frequencia", data=dados, follow_redirects=False)
    assert resp.status_code == 302

    with app.app_context():
        # Aluno 1 gravou com conceito A
        f_um = Frequencia.query.filter_by(
            aluno_id=ids["aluno_um"], data=data_antes,
        ).one_or_none()
        assert f_um is not None
        assert f_um.conceito == ConceitoFrequencia.A

        # Aluno 2 NÃO gravou nada
        f_dois = Frequencia.query.filter_by(
            aluno_id=ids["aluno_dois"], data=data_antes,
        ).all()
        assert len(f_dois) == 0


# ---------------------------------------------------------------------------
# 6) Valor obrigatório A–D: aluno desabilitado não conta
# ---------------------------------------------------------------------------
def test_valor_obrigatorio_ignora_aluno_desabilitado(app, client):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS, com_valores=True)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_antes = next(d for d in datas if d < DATA_ENTRADA_DOIS)

    login_as(client, ids["prof"], ids["un"])

    # GET na data anterior: o form tem data-valor-obrigatorio="1"
    url = f"/frequencia?turma_id={ids['turma']}&turma_curso={ids['oferta']}&data={_iso(data_antes)}"
    resp = client.get(url)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'data-valor-obrigatorio="1"' in html

    # Quando nenhum aluno elegível recebe A–D (ex.: F ou sem conceito),
    # o POST não exige valor_ids e salva sem erro
    dados_sem_ad = {
        "turma": str(ids["turma"]),
        "turma_curso": str(ids["oferta"]),
        "data": _iso(data_antes),
        f"aluno_{ids['aluno_um']}": "F",
    }
    resp_post = client.post("/frequencia", data=dados_sem_ad, follow_redirects=False)
    assert resp_post.status_code == 302

    with app.app_context():
        f_um = Frequencia.query.filter_by(
            aluno_id=ids["aluno_um"], data=data_antes,
        ).one_or_none()
        assert f_um is not None
        assert f_um.conceito == ConceitoFrequencia.F


# ---------------------------------------------------------------------------
# 7) JS estático em Node: conceitosMarcados ignora :disabled
# ---------------------------------------------------------------------------
HARNESS_JS = """
const F = require(process.argv[1]);

// Mock do form simulando a seleção do DOM
function criarFormMock(radios) {
    return {
        querySelectorAll: function(seletor) {
            if (seletor.includes(':not(:disabled)')) {
                return radios.filter(r => !r.disabled && (!seletor.includes(':checked') || r.checked));
            }
            return radios.filter(r => !seletor.includes(':checked') || r.checked);
        }
    };
}

// Caso 1: 1 aluno habilitado (A) e 1 aluno desabilitado (B)
const form1 = criarFormMock([
    { name: 'aluno_1', value: 'A', checked: true, disabled: false },
    { name: 'aluno_2', value: 'B', checked: true, disabled: true },
]);
const conceitos1 = F.conceitosMarcados(form1);

// Caso 2: somente aluno desabilitado marcado com A
const form2 = criarFormMock([
    { name: 'aluno_2', value: 'A', checked: true, disabled: true },
]);
const conceitos2 = F.conceitosMarcados(form2);
const pendente2 = F.valorAulaPendente({
    conceitos: conceitos2,
    valorIds: [],
    catalogoAtivo: true,
});

console.log(JSON.stringify({
    conceitosHabilitados: conceitos1,
    conceitosSoDesabilitado: conceitos2,
    pendenciaSoDesabilitado: pendente2,
}));
"""


@pytest.fixture(scope="module")
def node():
    caminho = shutil.which("node")
    if caminho is None:
        pytest.skip("node não disponível no PATH")
    return caminho


def test_js_conceitos_marcados_ignora_disabled(node):
    processo = subprocess.run(
        [node, "-e", HARNESS_JS, str(ARQ_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert processo.returncode == 0, processo.stderr
    saida = json.loads(processo.stdout)

    # No caso 1, apenas 'A' (habilitado) é retornado, 'B' (desabilitado) é ignorado
    assert saida["conceitosHabilitados"] == ["A"]

    # No caso 2, aluno desabilitado resulta em lista vazia de conceitos
    assert saida["conceitosSoDesabilitado"] == []

    # E não gera pendência de valor obrigatório
    assert saida["pendenciaSoDesabilitado"] is False
