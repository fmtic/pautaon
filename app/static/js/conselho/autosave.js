/**
 * AJ30 — autosave do fechamento do conselho, uma linha por vez.
 *
 * As funções de estado/fila/payload são PURAS (sem DOM, sem timer, sem rede)
 * para serem exercitadas em node no padrão de `tests/test_aj29_nome_pdf_js.py`.
 * A parte de navegador (fundo deste arquivo) só roda quando `document`
 * existe; a tela de fechamento inclui este script depois de `conselho.js`.
 *
 * Contrato de rede: POST JSON para `<path da página>/salvar` com
 * `{oferta_id, aluno_id, situacao, proximo_curso_id, proximo_nivel_id}` —
 * somente a linha alterada, com o token CSRF do `<meta name="csrf-token">`.
 */
(function (root) {
    'use strict';

    var DEBOUNCE_MS = 300;
    var MOSTRAR_SALVO_MS = 2000;

    /** Fila nova: por linha há no máximo um envio em voo e um estado pendente. */
    function criarFila() {
        return { emVoo: {}, pendente: {}, erros: {}, ultimo: {} };
    }

    /**
     * Registra uma nova intenção de salvar.
     * Devolve o payload a enviar JÁ, ou null se a linha já está em voo
     * (nesse caso o payload fica pendente e vale o ÚLTIMO estado).
     */
    function agendar(fila, chave, payload) {
        fila.ultimo[chave] = payload;
        if (fila.emVoo[chave]) {
            fila.pendente[chave] = payload;
            return null;
        }
        return payload;
    }

    function iniciar(fila, chave, payload) {
        fila.emVoo[chave] = payload || fila.ultimo[chave] || null;
        delete fila.pendente[chave];
    }

    /**
     * Fecha o envio. Devolve o payload pendente (para reenviar o último
     * estado) ou null. Erros ficam registrados até um novo envio bem-sucedido.
     */
    function finalizar(fila, chave, sucesso, mensagem) {
        delete fila.emVoo[chave];
        if (sucesso) {
            delete fila.erros[chave];
        } else {
            fila.erros[chave] = mensagem || 'Falha ao salvar.';
        }
        return fila.pendente[chave] || null;
    }

    function temPendencia(fila) {
        return Object.keys(fila.emVoo).length > 0
            || Object.keys(fila.pendente).length > 0;
    }

    function temErro(fila) {
        return Object.keys(fila.erros).length > 0;
    }

    function erroDaLinha(fila, chave) {
        return fila.erros[chave] || '';
    }

    /** Constrói o payload de UMA linha a partir de valores já lidos do DOM. */
    function payloadDaLinha(dados) {
        return {
            aluno_id: String(dados.alunoId == null ? '' : dados.alunoId),
            situacao: dados.situacao || '',
            proximo_curso_id: dados.curso || null,
            proximo_nivel_id: dados.nivel || null
        };
    }

    /** Texto/aria/classe do indicador. A mensagem do servidor vai para title
     *  e aria-label — nunca se perde num alert. */
    function estadoIndicador(estado, mensagem) {
        switch (estado) {
            case 'salvando':
                return {
                    texto: '⟳ Salvando…',
                    titulo: 'Salvando alterações desta linha…',
                    classe: 'autosave-salvando',
                    mostrarRetry: false
                };
            case 'salvo':
                return {
                    texto: '✓ Salvo',
                    titulo: 'Alterações salvas',
                    classe: 'autosave-salvo',
                    mostrarRetry: false
                };
            case 'erro':
                return {
                    texto: '⚠ Erro ao salvar',
                    titulo: mensagem || 'Falha ao salvar esta linha.',
                    classe: 'autosave-erro',
                    mostrarRetry: true
                };
            default:
                return { texto: '', titulo: '', classe: '', mostrarRetry: false };
        }
    }

    /** Texto impresso da situação: vazio é "—", nunca o rótulo "Não definido". */
    function textoImpressaoSituacao(valor, rotulo) {
        return valor ? String(rotulo || '') : '—';
    }

    /** Prioriza a mensagem devolvida pelo servidor; fallbacks para HTTP/rede. */
    function mensagemErro(mensagemServidor, status) {
        var texto = String(mensagemServidor || '').trim();
        if (texto) return texto;
        if (status === 400 || status === 419) {
            return 'Sessão expirada ou token de segurança inválido. Recarregue a página e tente novamente.';
        }
        if (status) return 'Erro HTTP ' + status;
        return 'Falha de rede ao salvar. Verifique sua conexão e tente novamente.';
    }

    var api = {
        DEBOUNCE_MS: DEBOUNCE_MS,
        MOSTRAR_SALVO_MS: MOSTRAR_SALVO_MS,
        criarFila: criarFila,
        agendar: agendar,
        iniciar: iniciar,
        finalizar: finalizar,
        temPendencia: temPendencia,
        temErro: temErro,
        erroDaLinha: erroDaLinha,
        payloadDaLinha: payloadDaLinha,
        estadoIndicador: estadoIndicador,
        textoImpressaoSituacao: textoImpressaoSituacao,
        mensagemErro: mensagemErro
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    root.autosaveFechamento = api;

    if (typeof document === 'undefined' || typeof window === 'undefined') return;

    var fila = criarFila();
    var timers = {};
    var salvoTimers = {};

    function tokenCsrf() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? (meta.getAttribute('content') || '') : '';
    }

    function urlSalvar() {
        return window.location.pathname.replace(/\/$/, '') + '/salvar';
    }

    function linhaDaChave(chave) {
        var tabela = document.getElementById('tabelaFechamento');
        if (!tabela) return null;
        return tabela.querySelector('tr[data-aluno-id="' + chave + '"]');
    }

    function pintar(chave, estado, mensagem) {
        var linha = linhaDaChave(chave);
        if (!linha) return;
        var area = linha.querySelector('.autosave-indicador');
        if (!area) return;
        var texto = area.querySelector('.autosave-estado');
        var botao = area.querySelector('.autosave-retry');
        var info = estadoIndicador(estado, mensagem);

        area.className = 'autosave-indicador d-print-none ' + info.classe;
        if (texto) {
            texto.textContent = info.texto;
            texto.title = info.titulo;
            texto.setAttribute('aria-label', info.titulo);
        }
        if (botao) {
            botao.classList.toggle('d-none', !info.mostrarRetry);
            botao.title = info.titulo;
            botao.setAttribute('aria-label', 'Tentar novamente: ' + info.titulo);
        }
    }

    function limparTimerSalvo(chave) {
        if (salvoTimers[chave]) {
            clearTimeout(salvoTimers[chave]);
            delete salvoTimers[chave];
        }
    }

    function enviar(chave) {
        var tabela = document.getElementById('tabelaFechamento');
        var payload = fila.ultimo[chave]
            || (tabela ? payloadDaLinha({
                alunoId: chave,
                situacao: (tabela.querySelector('tr[data-aluno-id="' + chave + '"] .situacao-select') || {}).value,
                curso: (tabela.querySelector('tr[data-aluno-id="' + chave + '"] .proxima-select') || {}).value,
                nivel: (tabela.querySelector('tr[data-aluno-id="' + chave + '"] .nivel-select') || {}).value
            }) : null);
        if (!payload) return;

        var ofertaId = tabela ? tabela.getAttribute('data-oferta-id') : '';
        limparTimerSalvo(chave);
        pintar(chave, 'salvando');
        iniciar(fila, chave, payload);

        fetch(urlSalvar(), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': tokenCsrf()
            },
            body: JSON.stringify({
                oferta_id: parseInt(ofertaId, 10),
                aluno_id: payload.aluno_id,
                situacao: payload.situacao,
                proximo_curso_id: payload.proximo_curso_id,
                proximo_nivel_id: payload.proximo_nivel_id
            })
        })
            .then(function (resposta) {
                return resposta.json().catch(function () {
                    return { success: false, message: '' };
                }).then(function (dados) {
                    return {
                        ok: resposta.ok && !!(dados && dados.success),
                        mensagem: dados && dados.message,
                        status: resposta.status
                    };
                });
            })
            .then(function (resultado) {
                var mensagem = resultado.ok
                    ? ''
                    : mensagemErro(resultado.mensagem, resultado.status);
                var proximo = finalizar(fila, chave, resultado.ok, mensagem);
                if (resultado.ok) {
                    pintar(chave, 'salvo');
                    salvoTimers[chave] = setTimeout(function () {
                        pintar(chave, '');
                        delete salvoTimers[chave];
                    }, MOSTRAR_SALVO_MS);
                } else {
                    pintar(chave, 'erro', mensagem);
                }
                if (proximo) enviar(chave);
            })
            .catch(function (erro) {
                var mensagem = mensagemErro('', 0) + (erro && erro.message ? ' (' + erro.message + ')' : '');
                var proximo = finalizar(fila, chave, false, mensagem);
                pintar(chave, 'erro', mensagem);
                if (proximo) enviar(chave);
            });
    }

    function agendarEnvio(chave, payload) {
        var proximo = agendar(fila, chave, payload);
        if (timers[chave]) clearTimeout(timers[chave]);
        if (proximo) {
            pintar(chave, 'salvando');
            timers[chave] = setTimeout(function () {
                delete timers[chave];
                enviar(chave);
            }, DEBOUNCE_MS);
        }
        // Se já havia envio em voo, `proximo` é null: o estado pendente só
        // é disparado quando a resposta anterior chegar (fila por linha).
    }

    function lerLinha(row) {
        var selects = row.querySelectorAll('select');
        return payloadDaLinha({
            alunoId: row.getAttribute('data-aluno-id'),
            situacao: selects[0] ? selects[0].value : '',
            curso: selects[1] ? selects[1].value : '',
            nivel: selects[2] ? selects[2].value : ''
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var tabela = document.getElementById('tabelaFechamento');
        if (!tabela || !tabela.getAttribute('data-oferta-id')) return;

        tabela.querySelectorAll('tbody tr').forEach(function (row) {
            var chave = row.getAttribute('data-aluno-id');
            if (!chave) return;
            row.querySelectorAll('select').forEach(function (sel) {
                sel.addEventListener('change', function () {
                    agendarEnvio(chave, lerLinha(row));
                });
            });
            var botao = row.querySelector('.autosave-retry');
            if (botao) {
                botao.addEventListener('click', function () {
                    agendarEnvio(chave, fila.ultimo[chave] || lerLinha(row));
                });
            }
        });

        window.addEventListener('beforeunload', function (evento) {
            if (!temPendencia(fila) && !temErro(fila)) return;
            evento.preventDefault();
            evento.returnValue = '';
        });
    });
})(typeof globalThis !== 'undefined' ? globalThis : this);
