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
