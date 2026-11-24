"""AJ30 — funções puras do autosave do fechamento (executadas em node).

Segue o padrão de ``tests/test_aj29_nome_pdf_js.py``: ``node -e`` com o
``module.exports`` de ``app/static/js/conselho/autosave.js`` e skip
documentado quando node não está no PATH. Nenhuma dependência JS nova.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ARQ_JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "conselho" / "autosave.js"

HARNESS = r"""
const P = require(process.argv[1]);

const fila = P.criarFila();
const vazio = { pendente: P.temPendencia(fila), erro: P.temErro(fila) };

const p1 = P.payloadDaLinha({alunoId: 7, situacao: 'Participante', curso: '3', nivel: ''});
const primeiro = P.agendar(fila, '7', p1);
P.iniciar(fila, '7', primeiro);
const durante = { pendente: P.temPendencia(fila), erro: P.temErro(fila) };

// Nova alteração na MESMA linha enquanto o envio está em voo: vale a última.
const p2 = P.payloadDaLinha({alunoId: 7, situacao: 'Evadido', curso: '', nivel: ''});
const emVoo = P.agendar(fila, '7', p2);
const depoisDoSegundo = { pendente: P.temPendencia(fila) };
const reenviar = P.finalizar(fila, '7', true, '');

// Outras linhas NÃO ficam bloqueadas pela fila da linha 7.
const outra = P.agendar(fila, '8', {aluno_id: '8', situacao: 'Aprovado'});

// Erro persiste até um sucesso; a mensagem do servidor é preservada.
P.iniciar(fila, '8', outra);
const falha = P.finalizar(fila, '8', false, 'Situação final inválida: X');
const comErro = {
  tem: P.temErro(fila),
  mensagem: P.erroDaLinha(fila, '8'),
  estado: P.estadoIndicador('erro', P.erroDaLinha(fila, '8')),
};
const limpo = P.finalizar(fila, '8', false, '') === null
  ? (P.iniciar(fila, '8', outra), P.finalizar(fila, '8', true, ''), P.temErro(fila))
  : 'inesperado';

const estados = {
  salvando: P.estadoIndicador('salvando'),
  salvo: P.estadoIndicador('salvo'),
  vazio: P.estadoIndicador(''),
};

process.stdout.write(JSON.stringify({
  vazio, p1, primeiro, durante, emVoo, depoisDoSegundo, reenviar, outra,
  falha, comErro, limpo, estados,
  debounce: P.DEBOUNCE_MS,
  mostraSalvo: P.MOSTRAR_SALVO_MS,
  impressaoVazia: P.textoImpressaoSituacao('', 'Não definido'),
  impressaoAprovado: P.textoImpressaoSituacao('Aprovado', 'Aprovado'),
  msgServidor: P.mensagemErro('Próximo curso não encontrado.', 400),
  msg400: P.mensagemErro('', 400),
  msg500: P.mensagemErro('', 500),
  msgRede: P.mensagemErro('', 0),
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
    processo = subprocess.run(
        [node, "-e", HARNESS, str(ARQ_JS)],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert processo.returncode == 0, processo.stderr
    return json.loads(processo.stdout)


def test_fila_comeca_vazia_e_respeita_uma_linha_por_vez(saida):
    assert saida["vazio"] == {"pendente": False, "erro": False}
    assert saida["primeiro"] == saida["p1"]
    assert saida["durante"] == {"pendente": True, "erro": False}
    assert saida["emVoo"] is None
    assert saida["depoisDoSegundo"] == {"pendente": True}
    assert saida["reenviar"]["situacao"] == "Evadido"


def test_outra_linha_nao_e_bloqueada(saida):
    assert saida["outra"] == {"aluno_id": "8", "situacao": "Aprovado"}


def test_erro_guarda_mensagem_e_sucesso_limpa(saida):
    assert saida["falha"] is None
    assert saida["comErro"]["tem"] is True
    assert saida["comErro"]["mensagem"] == "Situação final inválida: X"
    assert saida["comErro"]["estado"] == {
        "texto": "⚠ Erro ao salvar",
        "titulo": "Situação final inválida: X",
        "classe": "autosave-erro",
        "mostrarRetry": True,
    }
    assert saida["limpo"] is False


def test_payload_de_uma_linha_e_estados_do_indicador(saida):
    assert saida["p1"] == {
        "aluno_id": "7", "situacao": "Participante",
        "proximo_curso_id": "3", "proximo_nivel_id": None,
    }
    assert saida["estados"]["salvando"]["texto"] == "⟳ Salvando…"
    assert saida["estados"]["salvando"]["classe"] == "autosave-salvando"
    assert saida["estados"]["salvo"] == {
        "texto": "✓ Salvo", "titulo": "Alterações salvas",
        "classe": "autosave-salvo", "mostrarRetry": False,
    }
    assert saida["estados"]["vazio"]["texto"] == ""


def test_impressao_de_situacao_ausente_e_traco(saida):
    assert saida["impressaoVazia"] == "—"
    assert saida["impressaoAprovado"] == "Aprovado"


def test_tempos_e_mensagens_de_erro(saida):
    assert saida["debounce"] == 300
    assert saida["mostraSalvo"] == 2000
    assert saida["msgServidor"] == "Próximo curso não encontrado."
    assert "Sessão expirada" in saida["msg400"]
    assert saida["msg500"] == "Erro HTTP 500"
    assert "Falha de rede" in saida["msgRede"]
