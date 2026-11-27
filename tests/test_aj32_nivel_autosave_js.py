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

// AJ32-B: resposta com acento/espaço diferente não deve reenfileirar quando
// normalizado é igual ao confirmado; só reenfileira se usuário mudou após envio.
const filaLoop = P.criarFila();
P.definirConfirmado(filaLoop, '1:1', 'Intermediário');
const agLoop = P.agendar(filaLoop, '1:1', 'Intermediário '); // trim igual
const agLoopNull = agLoop; // deve ser null por igual ao confirmado
P.definirConfirmado(filaLoop, '1:2', 'Básico');
P.agendar(filaLoop, '1:2', 'Intermediário');
P.iniciar(filaLoop, '1:2', 'Intermediário');
const proxLoop = P.finalizar(filaLoop, '1:2', true, '', ' Intermediário '); // servidor devolve com espaços
const deveReenv = P.deveReenfileirar(filaLoop, '1:2', ' Intermediário ');
const confLoop = P.valorReversao(filaLoop, '1:2');

// usuário mudou durante envio -> deve reenfileirar
const filaMudou = P.criarFila();
P.definirConfirmado(filaMudou, '1:3', 'Básico');
P.agendar(filaMudou, '1:3', 'Intermediário');
P.iniciar(filaMudou, '1:3', 'Intermediário');
P.agendar(filaMudou, '1:3', 'Avançado');
const proxMudou = P.finalizar(filaMudou, '1:3', true, '', 'Intermediário');
const deveReenvMudou = P.deveReenfileirar(filaMudou, '1:3', 'Intermediário');

// limite de tentativas
const filaTent = P.criarFila();
P.definirConfirmado(filaTent, '1:4', 'Básico');
P.agendar(filaTent, '1:4', 'Avançado');
P.iniciar(filaTent, '1:4', 'Avançado');
P.finalizar(filaTent, '1:4', false, 'falha 1');
P.iniciar(filaTent, '1:4', 'Avançado');
P.finalizar(filaTent, '1:4', false, 'falha 2');
const pode2 = P.podeTentarNovamente(filaTent, '1:4');
P.iniciar(filaTent, '1:4', 'Avançado');
P.finalizar(filaTent, '1:4', false, 'falha 3');
const pode3 = P.podeTentarNovamente(filaTent, '1:4');
const revTent = P.valorReversao(filaTent, '1:4');

// AJ32-B: canonicalização do servidor (espaço/caixa) é confirmação válida.
const filaCanon = P.criarFila();
P.definirConfirmado(filaCanon, '1:5', 'Básico');
P.agendar(filaCanon, '1:5', '  avancado  ');
P.iniciar(filaCanon, '1:5', 'avancado');
const analiseCanon = P.analisarSucesso(filaCanon, '1:5', '  avancado  ', 'Avançado Nível 1');
const tentativasCanon = P.podeTentarNovamente(filaCanon, '1:5');

// AJ32-B: se o servidor não honra a mudança do usuário, para após 3 divergências.
const filaDiv = P.criarFila();
P.definirConfirmado(filaDiv, '1:6', 'Básico');
P.agendar(filaDiv, '1:6', 'Intermediário');
P.iniciar(filaDiv, '1:6', 'Intermediário');
P.agendar(filaDiv, '1:6', 'Avançado'); // usuário mudou durante envio
const analiseDiv1 = P.analisarSucesso(filaDiv, '1:6', 'Intermediário', 'Intermediário');
const podeDiv1 = P.marcarDivergencia(filaDiv, '1:6');
P.iniciar(filaDiv, '1:6', 'Avançado');
const analiseDiv2 = P.analisarSucesso(filaDiv, '1:6', 'Avançado', 'Intermediário');
const podeDiv2 = P.marcarDivergencia(filaDiv, '1:6');
P.iniciar(filaDiv, '1:6', 'Avançado');
const analiseDiv3 = P.analisarSucesso(filaDiv, '1:6', 'Avançado', 'Intermediário');
const podeDiv3 = P.marcarDivergencia(filaDiv, '1:6');
P.limparDivergencia(filaDiv, '1:6');
const divergenciaLimpa = P.podeTentarNovamente(filaDiv, '1:6');

// finalizar sem valorConfirmado não pode sobrescrever a última intenção:
// o chamador promove confirmado/ultimo depois de analisar a resposta.
const filaSemValor = P.criarFila();
P.definirConfirmado(filaSemValor, '1:7', 'Intermediário');
P.agendar(filaSemValor, '1:7', 'Básico');
P.agendar(filaSemValor, '1:7', 'Avançado Nível 1');
P.iniciar(filaSemValor, '1:7', filaSemValor.ultimo['1:7']);
delete filaSemValor.pendente['1:7'];
P.finalizar(filaSemValor, '1:7', true, '', undefined);
const ultimoSemValor = filaSemValor.ultimo['1:7'];

const payload = P.payloadNivel({
  alunoId: 7, turmaId: 5, turmaCursoId: 10, nivel: 'Avançado'
});

process.stdout.write(JSON.stringify({
  vazio, primeiro, durante, emVoo, depois, reenviar, confirmadoAposSucesso,
  outra, falha, comErro, limpo, payload,
  agLoopNull, proxLoop, deveReenv, confLoop,
  proxMudou, deveReenvMudou,
  pode2, pode3, revTent,
  analiseCanon, tentativasCanon,
  analiseDiv1, podeDiv1, analiseDiv2, podeDiv2, analiseDiv3, podeDiv3,
  divergenciaLimpa, ultimoSemValor,
  debounce: P.DEBOUNCE_MS,
  mostraSalvo: P.MOSTRAR_SALVO_MS,
  maxTent: P.MAX_TENTATIVAS,
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
    # confirmado segue o valor devolvido/aplicado pelo servidor (sucesso).
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
    assert saida["maxTent"] == 3
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


def test_aj32b_resposta_equivalente_nao_reenfileira_loop(saida):
    # trim/espaço: igual ao confirmado normalizado -> não agenda
    assert saida["agLoopNull"] is None
    # servidor devolveu valor com espaços, mas normalizado igual: não reenfileira
    assert saida["proxLoop"] is None
    assert saida["deveReenv"] is False
    assert saida["confLoop"] == "Intermediário"


def test_aj32b_usuario_mudou_durante_envio_reenfileira_uma_vez(saida):
    assert saida["proxMudou"] == "Avançado"
    assert saida["deveReenvMudou"] is True


def test_aj32b_limite_tentativas_para_e_reverte(saida):
    assert saida["pode2"] is True
    assert saida["pode3"] is False
    assert saida["revTent"] == "Básico"


def test_aj32b_canonicalizacao_do_servidor_e_confirmacao(saida):
    # Espaço/caixa diferentes não são divergência: confirma e não consome tentativa.
    assert saida["analiseCanon"] == "confirmado"
    assert saida["tentativasCanon"] is True


def test_aj32b_servidor_nao_honra_mudanca_para_apos_tres_divergencias(saida):
    assert saida["analiseDiv1"] == "reenviar"
    assert saida["podeDiv1"] is True
    assert saida["analiseDiv2"] == "reenviar"
    assert saida["podeDiv2"] is True
    assert saida["analiseDiv3"] == "reenviar"
    assert saida["podeDiv3"] is False
    assert saida["divergenciaLimpa"] is True


def test_aj32b_finalizar_sem_valor_preserva_ultima_intencao(saida):
    assert saida["ultimoSemValor"] == "Avançado Nível 1"
