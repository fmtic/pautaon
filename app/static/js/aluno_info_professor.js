/**
 * aluno_info_professor.js — I1: modal "Informações para o professor".
 *
 * O HTML da pauta NUNCA carrega os textos do aluno: só o ícone com
 * `data-aluno-id` (e o nome, para o título). Os dados vêm de
 * `GET /aluno/<id>/info-professor`, que valida a regra de acesso no servidor
 * (professor efetivo da oferta, inscrição ativa, turma ativa, período não
 * encerrado).
 *
 * Renderização por `textContent`/`white-space: pre-wrap`: nada de `innerHTML`
 * com conteúdo do aluno — os textos saem como texto puro, com as quebras de
 * linha preservadas.
 */

const ENDPOINT = (alunoId) => `/aluno/${alunoId}/info-professor`;

const MENSAGENS = {
    403: 'Você não tem acesso às informações deste aluno.',
    404: 'Nenhuma informação cadastrada para este aluno.',
    rede: 'Não foi possível carregar as informações. Tente novamente.',
};

function tituloModal(nome) {
    return `Informações para o professor — ${nome}`;
}

/** Cria (uma vez) o bloco de texto de um item, já com quebras preservadas. */
function criarBloco(rotulo, texto) {
    const envelope = document.createElement('div');
    envelope.className = 'mb-3';

    const titulo = document.createElement('h6');
    titulo.className = 'fw-bold text-primary mb-1';
    titulo.textContent = rotulo;

    const corpo = document.createElement('div');
    corpo.className = 'texto-info-aluno';
    corpo.style.whiteSpace = 'pre-wrap';
    corpo.textContent = texto;

    envelope.append(titulo, corpo);
    return envelope;
}

/** Preenche o modal só com os blocos presentes na resposta. */
function preencherModal(corpoModal, dados) {
    corpoModal.replaceChildren();

    if (dados.acompanhante) {
        corpoModal.append(criarBloco('Quem acompanha?', dados.acompanhante));
    }
    if (dados.instrucoes) {
        corpoModal.append(
            criarBloco('Informações para o professor da turma', dados.instrucoes),
        );
    }
}

function mostrarStatus(corpoModal, mensagem, classe) {
    corpoModal.replaceChildren();
    const aviso = document.createElement('div');
    aviso.className = `alert ${classe} mb-0`;
    aviso.textContent = mensagem;
    corpoModal.append(aviso);
}

function mostrarErro(corpoModal, mensagem) {
    mostrarStatus(corpoModal, mensagem, 'alert-warning');
}

if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', function () {
        const modalEl = document.getElementById('modal-info-professor');
        if (!modalEl) return; // perfil sem o modal (não é professor)

        const tituloEl = document.getElementById('modal-info-professor-titulo');
        const corpoModal = document.getElementById('modal-info-professor-corpo');
        const modal = new bootstrap.Modal(modalEl);

        document.querySelectorAll('[data-aluno-id].btn-info-professor').forEach(botao => {
            botao.addEventListener('click', async function () {
                const alunoId = this.dataset.alunoId;
                const nome = this.dataset.alunoNome || '';

                if (tituloEl) tituloEl.textContent = tituloModal(nome);
                if (corpoModal) {
                    mostrarStatus(corpoModal, 'Carregando…', 'alert-light text-muted');
                }
                modal.show();

                try {
                    const resposta = await fetch(ENDPOINT(alunoId), {
                        headers: { Accept: 'application/json' },
                        cache: 'no-store',
                    });

                    if (!resposta.ok) {
                        mostrarErro(
                            corpoModal,
                            MENSAGENS[resposta.status] || MENSAGENS.rede,
                        );
                        return;
                    }

                    const dados = await resposta.json();
                    if (tituloEl && dados.nome) tituloEl.textContent = tituloModal(dados.nome);
                    preencherModal(corpoModal, dados);
                } catch (erro) {
                    mostrarErro(corpoModal, MENSAGENS.rede);
                }
            });
        });
    });
}
