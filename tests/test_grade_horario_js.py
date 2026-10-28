"""H4 — Passo 4: funções puras do módulo compartilhado de agenda
(app/static/js/turmas/grade_horario.js) executadas em node.

O repo não tem suíte JS própria (sem package.json/CI de JS), mas node está
disponível no ambiente de desenvolvimento; este teste usa ``node -e`` com o
``module.exports`` do arquivo (o mesmo gancho usado manualmente no Passo 3)
e pula com justificativo documentado quando node não existe no PATH.

Cobre o contrato do H4 no lado JS:
    - conversão Date.getDay() → weekday Python: (getDay()+6)%7, sem domingo;
    - duração por dia (fim > início, mesmo dia);
    - ocorrências de um weekday no período (inclusive nas bordas);
    - C.H. estimativa = Σ duração × ocorrências por weekday;
    - serialização "dia:HH:MM-HH:MM|..." e seu inverso (comparação
      "mudou vs. original" do editar.js).

E o contrato do H4c/H4d (funções puras extraídas em H4d sem mudança de
comportamento):
    - podeHabilitarPorDia: interruptor só com 2+ dias;
    - parPadraoAposVolta: volta ao padrão — 1 dia, o par do dia restante vira o
      padrão (campo vazio mantém o atual); 0 dias, mantém o último par;
    - valorEspelhado: modo padrão espelha o par nos dias marcados;
    - estadoLinha: esmaecido/desabilitado de cada linha por modo e marcação.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ARQ_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "turmas" / "grade_horario.js"

HARNESS = """
const G = require(process.argv[1]);
const saida = {
    // getDay() JS → weekday Python: 0=Dom→6 (fora do domínio, sem domingo),
    // 1=Seg→0, 6=Sáb→5.
    dom: G.getDayParaWeekday(0),
    seg: G.getDayParaWeekday(1),
    sab: G.getDayParaWeekday(6),
    domInvalido: G.weekdayValido(G.getDayParaWeekday(0)),
    // Duração por dia.
    dur: G.duracaoDiaMinutos('08:00', '11:00'),
    durInvertida: G.duracaoDiaMinutos('11:00', '08:00'),
    durIguais: G.duracaoDiaMinutos('08:00', '08:00'),
    durVazio: G.duracaoDiaMinutos('', '11:00'),
    // Ocorrências de weekday no período (inclusive nas bordas).
    segFev: G.ocorrenciasWeekday('2026-02-02', '2026-02-28', 0),
    quaFev: G.ocorrenciasWeekday('2026-02-02', '2026-02-28', 2),
    domOcorre: G.ocorrenciasWeekday('2026-02-01', '2026-02-28', 6),
    datasInvertidas: G.ocorrenciasWeekday('2026-02-28', '2026-02-02', 0),
    // C.H. estimativa por dia (Seg 3h × 4 + Qua 3h × 4 em fevereiro/2026).
    chVariavel: G.estimarCHMinutos(
        [{dia: 0, inicio: '08:00', fim: '11:00'},
         {dia: 2, inicio: '14:00', fim: '17:00'}],
        '2026-02-02', '2026-02-28'),
    // Formatação.
    fmt3h: G.formatarCH(180),
    fmt1h30: G.formatarCH(90),
    fmtZero: G.formatarCH(0),
    // Serialização idêntica ao contrato do servidor (estado_agenda).
    serial: G.serializarGrade(
        [{dia: 0, inicio: '08:00', fim: '11:00'},
         {dia: 2, inicio: '14:00', fim: '17:00'}]),
    parcial: G.serializarGrade([{dia: 1, inicio: '', fim: ''}]),
    desserial: G.deserializarGrade('0:08:00-11:00|2:14:00-17:00|lixo'),
    // H4c/H4d: interruptor 2+ dias, volta ao padrão, espelhamento, estado de linha.
    pode0: G.podeHabilitarPorDia([]),
    pode1: G.podeHabilitarPorDia([0]),
    pode2: G.podeHabilitarPorDia([0, 2]),
    volta1: G.parPadraoAposVolta([2],
        {2: {inicio: '14:00', fim: '17:00'}},
        {inicio: '08:00', fim: '11:00'}),
    volta1Vazio: G.parPadraoAposVolta([2],
        {2: {inicio: '', fim: ''}},
        {inicio: '08:00', fim: '11:00'}),
    volta1Parcial: G.parPadraoAposVolta([2],
        {2: {inicio: '', fim: '17:00'}},
        {inicio: '08:00', fim: '11:00'}),
    volta0: G.parPadraoAposVolta([], {},
        {inicio: '08:00', fim: '11:00'}),
    espMarcado: G.valorEspelhado(true, false, '08:00', ''),
    espDesmarcado: G.valorEspelhado(false, false, '08:00', '14:00'),
    espPersonalizado: G.valorEspelhado(true, true, '08:00', '14:00'),
    linhaPadraoMarcado: G.estadoLinha(true, false),
    linhaPadraoDesmarcado: G.estadoLinha(false, false),
    linhaPersoMarcado: G.estadoLinha(true, true),
    linhaPersoDesmarcado: G.estadoLinha(false, true),
};
process.stdout.write(JSON.stringify(saida));
"""


@pytest.fixture(scope="module")
def node():
    caminho = shutil.which("node")
    if caminho is None:  # skip documentado: sem suíte JS no repo
        pytest.skip("node não disponível no PATH — funções puras validadas só no servidor")
    return caminho


@pytest.fixture(scope="module")
def saida(node):
    processo = subprocess.run(
        [node, "-e", HARNESS, str(ARQ_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",  # stdout do node é UTF-8 (em-dash do formatarCH)
        timeout=60,
    )
    assert processo.returncode == 0, processo.stderr
    return json.loads(processo.stdout)


def test_conversao_getday_sem_domingo(saida):
    assert (saida["dom"], saida["seg"], saida["sab"]) == (6, 0, 5)
    # Domingo cai fora do domínio 0–5 do contrato.
    assert saida["domInvalido"] is False


def test_duracao_por_dia(saida):
    assert saida["dur"] == 180
    assert saida["durInvertida"] is None
    assert saida["durIguais"] is None
    assert saida["durVazio"] is None


def test_ocorrencias_no_periodo(saida):
    # Segundas em fev/2026 a partir de 02/02: 2, 9, 16, 23.
    assert saida["segFev"] == 4
    assert saida["quaFev"] == 4
    # Domingo não é dia válido no contrato.
    assert saida["domOcorre"] == 0
    assert saida["datasInvertidas"] == 0


def test_ch_estimativa_soma_por_dia(saida):
    # 3h por segmento × 4 ocorrências × 2 dias = 1440 minutos.
    assert saida["chVariavel"] == 1440


def test_formatacao(saida):
    assert saida["fmt3h"] == "3h"
    assert saida["fmt1h30"] == "1h30min"
    assert saida["fmtZero"] == "—"


def test_serializacao_contrato_agenda(saida):
    # Mesmo formato de _serializar_estado_agenda (Python).
    assert saida["serial"] == "0:08:00-11:00|2:14:00-17:00"
    assert saida["parcial"] == "1:-"
    # Inverso tolerante: parte malformada é descartada.
    assert saida["desserial"] == [
        {"dia": 0, "inicio": "08:00", "fim": "11:00"},
        {"dia": 2, "inicio": "14:00", "fim": "17:00"},
    ]


# --- H4c/H4d: funções puras do componente (extraídas em H4d, mesmo comportamento)


def test_interruptor_so_com_2_mais_dias(saida):
    # Regra H4c: habilita só com 2+ dias marcados.
    assert (saida["pode0"], saida["pode1"], saida["pode2"]) == (False, False, True)


def test_volta_ao_padrao_1_dia_par_restante_vira_padrao(saida):
    assert saida["volta1"] == {"inicio": "14:00", "fim": "17:00"}


def test_volta_ao_padrao_campo_vazio_mantem_atual(saida):
    # Dia restante sem valor → padrão conserva o último par (não é apagado).
    assert saida["volta1Vazio"] == {"inicio": "08:00", "fim": "11:00"}
    # Parcial: só o lado preenchido do dia migra; o vazio mantém o padrão.
    assert saida["volta1Parcial"] == {"inicio": "08:00", "fim": "17:00"}


def test_volta_ao_padrao_0_dias_mantem_ultimo_par(saida):
    assert saida["volta0"] == {"inicio": "08:00", "fim": "11:00"}


def test_espelhamento_do_padrao_nos_dias(saida):
    # Modo padrão: dia marcado recebe o padrão; desmarcado mantém o próprio.
    assert saida["espMarcado"] == "08:00"
    assert saida["espDesmarcado"] == "14:00"
    # Modo personalizado: nunca espelha (não sobrescreve o digitado por dia).
    assert saida["espPersonalizado"] == "14:00"


def test_estado_linha_por_modo_e_marcacao(saida):
    # Modo padrão: todas as linhas esmaecidas e desabilitadas.
    assert saida["linhaPadraoMarcado"] == {"esmaecida": True, "camposDesabilitados": True}
    assert saida["linhaPadraoDesmarcado"] == {"esmaecida": True, "camposDesabilitados": True}
    # Personalizado: marcado ativo (sem esmaecer); desmarcado esmaecido/desabilitado.
    assert saida["linhaPersoMarcado"] == {"esmaecida": False, "camposDesabilitados": False}
    assert saida["linhaPersoDesmarcado"] == {"esmaecida": True, "camposDesabilitados": True}
