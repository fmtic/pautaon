"""AJ32 — funções puras do autosave de nível na enturmação (node).

Padrão de ``tests/test_aj30_autosave_js.py``: ``node -e`` com
``module.exports`` de ``app/static/js/turmas/nivel_autosave.js`` e skip
documentado quando node não está no PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ARQ_JS = (
    Path(__file__).resolve().parents[1]
    / "app"
    / "static"
    / "js"
    / "turmas"
    / "nivel_autosave.js"
)

HARNESS = r"""
const P = require(process.argv[1]);

const fila = P.criarFila();
P.definirConfirmado(fila, '10:7', 'Avançado');
const vazio = { pendente: P.temPendencia(fila), erro: P.temErro(fila) };

const primeiro = P.agendar(fila, '10:7', 'Iniciante');
P.iniciar(fila, '10:7', primeiro);
const durante = { pendente: P.temPendencia(fila), erro: P.temErro(fila) };

// Nova alteração na mesma linha enquanto envio em voo: vale a última.
const emVoo = P.agendar(fila, '10:7', 'Não se aplica');
const depois = { pendente: P.temPendencia(fila) };
const reenviar = P.finalizar(fila, '10:7', true, '', 'Iniciante');
const confirmadoAposSucesso = P.valorReversao(fila, '10:7');

// Outra linha não bloqueia.
P.definirConfirmado(fila, '10:8', 'Básico');
const outra = P.agendar(fila, '10:8', 'Intermediário');

// Erro: mensagem preservada e reversão ao confirmado.
P.iniciar(fila, '10:8', outra);
const falha = P.finalizar(fila, '10:8', false, 'Oferta inválida para atualização de nível.');
const comErro = {
  tem: P.temErro(fila),
  msg: P.erroDaLinha(fila, '10:8'),
  reversao: P.valorReversao(fila, '10:8'),
  estado: P.estadoIndicador('erro', P.erroDaLinha(fila, '10:8')),
};
P.iniciar(fila, '10:8', outra);
P.finalizar(fila, '10:8', true, '', 'Intermediário');
const limpo = P.temErro(fila);

const payload = P.payloadNivel({
  alunoId: 7, turmaId: 5, turmaCursoId: 10, nivel: 'Avançado'
});

process.stdout.write(JSON.stringify({
  vazio, primeiro, durante, emVoo, depois, reenviar, confirmadoAposSucesso,
  outra, falha, comErro, limpo, payload,
  debounce: P.DEBOUNCE_MS,
  mostraSalvo: P.MOSTRAR_SALVO_MS,
  estados: {
    salvando: P.estadoIndicador('salvando'),
    salvo: P.estadoIndicador('salvo'),
    padrao: P.estadoIndicador(''),
  },
  msgServidor: P.mensagemErro('Inscrição ativa não encontrada para esta oferta.', 404),
  msg400: P.mensagemErro('', 400),
  msg403: P.mensagemErro('', 403),
  msg404: P.mensagemErro('', 404),
  msg500: P.mensagemErro('', 500),
  msgRede: P.mensagemErro('', 0),
  chave: P.chaveLinha({ turmaCursoId: 10, alunoId: 7 }),
}));
"""


@pytest.fixture(scope="module")
def node():
    caminho = shutil.which("node")
    if caminho is None:
        pytest.skip("node não disponível no PATH — funções puras validadas só no servidor")
    return caminho


@pytest.fixture(scope="module")
def saida(node):
    proc = subprocess.run(
        [node, "-e", HARNESS, str(ARQ_JS)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_fila_por_linha_e_ultima_alteracao_vence(saida):
    assert saida["vazio"] == {"pendente": False, "erro": False}
    assert saida["primeiro"] == "Iniciante"
    assert saida["durante"] == {"pendente": True, "erro": False}
    assert saida["emVoo"] is None
    assert saida["depois"] == {"pendente": True}
    assert saida["reenviar"] == "Não se aplica"
    assert saida["confirmadoAposSucesso"] == "Iniciante"


def test_outra_linha_nao_bloqueia(saida):
    assert saida["outra"] == "Intermediário"


def test_erro_reverte_para_valor_confirmado_e_mensagem_preservada(saida):
    assert saida["falha"] is None
    assert saida["comErro"]["tem"] is True
    assert saida["comErro"]["msg"] == "Oferta inválida para atualização de nível."
    assert saida["comErro"]["reversao"] == "Básico"
    assert "Oferta inválida" in saida["comErro"]["estado"]["texto"]
    assert saida["comErro"]["estado"]["classe"] == "text-danger"
    assert saida["limpo"] is False


def test_payload_tempos_estados_e_mensagens(saida):
    assert saida["payload"] == {
        "aluno_id": "7",
        "turma_id": "5",
        "turma_curso_id": "10",
        "nivel": "Avançado",
    }
    assert saida["debounce"] == 300
    assert saida["mostraSalvo"] == 2000
    assert saida["estados"]["salvando"]["texto"] == "Salvando…"
    assert saida["estados"]["salvo"]["texto"] == "✓ Salvo"
    assert saida["estados"]["padrao"]["texto"] == "Salvamento automático"
    assert saida["msgServidor"] == "Inscrição ativa não encontrada para esta oferta."
    assert "Sessão expirada" in saida["msg400"]
    assert saida["msg403"] == "Permissão negada para alterar este nível."
    assert "não encontrado" in saida["msg404"]
    assert saida["msg500"] == "Erro HTTP 500"
    assert "Falha de rede" in saida["msgRede"]
    assert saida["chave"] == "10:7"
