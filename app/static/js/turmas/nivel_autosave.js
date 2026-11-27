/**
 * AJ32 — autosave do nível do aluno na tela de enturmação (detalhe da turma).
 *
 * Padrão inspirado no autosave do fechamento do conselho: debounce 300ms,
 * fila por linha, indicador discreto, reversão em erro e aviso beforeunload.
 *
 * Funções puras exportadas para testes node (sem DOM/timers/rede).
 * A parte de navegador só roda quando `document` existe.
 */
(function (root) {
    'use strict';

    var DEBOUNCE_MS = 300;
    var MOSTRAR_SALVO_MS = 2000;

    function criarFila() {
        return { emVoo: {}, pendente: {}, erros: {}, ultimo: {}, confirmado: {} };
    }

    function definirConfirmado(fila, chave, valor) {
        fila.confirmado[chave] = valor == null ? '' : String(valor);
        if (!(chave in fila.ultimo)) fila.ultimo[chave] = fila.confirmado[chave];
    }

    function agendar(fila, chave, valor) {
        var normalizado = valor == null ? '' : String(valor);
        fila.ultimo[chave] = normalizado;
        if (fila.emVoo[chave]) {
            fila.pendente[chave] = normalizado;
            return null;
        }
        return normalizado;
    }

    function iniciar(fila, chave, valor) {
        fila.emVoo[chave] = valor == null ? (fila.ultimo[chave] || '') : String(valor);
        delete fila.pendente[chave];
    }

    function finalizar(fila, chave, sucesso, mensagem, valorConfirmado) {
        delete fila.emVoo[chave];
        if (sucesso) {
            delete fila.erros[chave];
            if (valorConfirmado !== undefined) {
                fila.confirmado[chave] = valorConfirmado == null ? '' : String(valorConfirmado);
            } else if (fila.ultimo[chave] !== undefined) {
                fila.confirmado[chave] = fila.ultimo[chave];
            }
        } else {
            fila.erros[chave] = mensagem || 'Falha ao salvar.';
        }
        var pendente = fila.pendente[chave];
        return pendente === undefined ? null : pendente;
    }

    function temPendencia(fila) {
        return Object.keys(fila.emVoo).length > 0 || Object.keys(fila.pendente).length > 0;
    }

    function temErro(fila) {
        return Object.keys(fila.erros).length > 0;
    }

    function erroDaLinha(fila, chave) {
        return fila.erros[chave] || '';
    }

    function valorReversao(fila, chave) {
        var confirmado = fila.confirmado[chave];
        return confirmado == null ? '' : String(confirmado);
    }

    function estadoIndicador(estado, mensagem) {
        switch (estado) {
            case 'salvando':
                return {
                    texto: 'Salvando…',
                    titulo: 'Salvando nível desta linha…',
                    classe: 'text-muted',
                    mostrar: true
                };
            case 'salvo':
                return {
                    texto: '✓ Salvo',
                    titulo: 'Nível salvo',
                    classe: 'text-success',
                    mostrar: true
                };
            case 'erro':
                return {
                    texto: '⚠ ' + (mensagem || 'Erro ao salvar.'),
                    titulo: mensagem || 'Erro ao salvar esta linha.',
                    classe: 'text-danger',
                    mostrar: true
                };
            default:
                return {
                    texto: 'Salvamento automático',
                    titulo: 'As alterações de nível são salvas automaticamente.',
                    classe: 'text-muted',
                    mostrar: true
                };
        }
    }

    function payloadNivel(dados) {
        return {
            aluno_id: String(dados.alunoId == null ? '' : dados.alunoId),
            turma_id: String(dados.turmaId == null ? '' : dados.turmaId),
            turma_curso_id: String(dados.turmaCursoId == null ? '' : dados.turmaCursoId),
            nivel: dados.nivel == null ? '' : String(dados.nivel)
        };
    }

    function mensagemErro(mensagemServidor, status) {
        var texto = String(mensagemServidor || '').trim();
        if (texto) return texto;
        if (status === 400 || status === 419) {
            return 'Sessão expirada ou dados inválidos. Recarregue a página e tente novamente.';
        }
        if (status === 403) return 'Permissão negada para alterar este nível.';
        if (status === 404) return 'Aluno ou oferta não encontrado. Recarregue a página.';
        if (status) return 'Erro HTTP ' + status;
        return 'Falha de rede ao salvar. Verifique sua conexão e tente novamente.';
    }

    function chaveLinha(dados) {
        return String(dados.turmaCursoId || '') + ':' + String(dados.alunoId || '');
    }

    var api = {
        DEBOUNCE_MS: DEBOUNCE_MS,
        MOSTRAR_SALVO_MS: MOSTRAR_SALVO_MS,
        criarFila: criarFila,
        definirConfirmado: definirConfirmado,
        agendar: agendar,
        iniciar: iniciar,
        finalizar: finalizar,
        temPendencia: temPendencia,
        temErro: temErro,
        erroDaLinha: erroDaLinha,
        valorReversao: valorReversao,
        estadoIndicador: estadoIndicador,
        payloadNivel: payloadNivel,
        mensagemErro: mensagemErro,
        chaveLinha: chaveLinha
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    root.nivelAutosave = api;

    if (typeof document === 'undefined' || typeof window === 'undefined') return;

    var fila = criarFila();
    var timers = {};
    var salvoTimers = {};

    function tokenCsrf() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? (meta.getAttribute('content') || '') : '';
    }

    function wrapDaChave(chave) {
        return document.querySelector('.nivel-autosave-wrap[data-chave="' + CSS.escape(chave) + '"]');
    }

    function pintar(chave, estado, mensagem) {
        var wrap = wrapDaChave(chave);
        if (!wrap) return;
        var msg = wrap.querySelector('.nivel-autosave-msg');
        if (!msg) return;
        var info = estadoIndicador(estado, mensagem);
        msg.textContent = info.texto;
        msg.title = info.titulo;
        msg.className = 'nivel-autosave-msg ' + info.classe;
        var status = wrap.querySelector('.nivel-autosave-status');
        if (status) {
            status.setAttribute('aria-label', info.titulo || info.texto);
        }
    }

    function limparTimerSalvo(chave) {
        if (salvoTimers[chave]) {
            clearTimeout(salvoTimers[chave]);
            delete salvoTimers[chave];
        }
    }

    function lerWrap(wrap) {
        var select = wrap.querySelector('select.js-nivel-autosave');
        return {
            alunoId: wrap.getAttribute('data-aluno-id'),
            turmaId: wrap.getAttribute('data-turma-id'),
            turmaCursoId: wrap.getAttribute('data-turma-curso-id'),
            url: wrap.getAttribute('data-url'),
            nivel: select ? select.value : ''
        };
    }

    function enviar(chave) {
        var wrap = wrapDaChave(chave);
        if (!wrap) return;
        var dados = lerWrap(wrap);
        var valor = fila.ultimo[chave];
        if (valor === undefined) valor = dados.nivel;
        var payload = payloadNivel({
            alunoId: dados.alunoId,
            turmaId: dados.turmaId,
            turmaCursoId: dados.turmaCursoId,
            nivel: valor
        });

        limparTimerSalvo(chave);
        pintar(chave, 'salvando');
        iniciar(fila, chave, valor);

        fetch(dados.url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CSRFToken': tokenCsrf(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(payload)
        })
            .then(function (resposta) {
                return resposta.json().catch(function () {
                    return { ok: false, message: '' };
                }).then(function (json) {
                    return { status: resposta.status, json: json || {} };
                });
            })
            .then(function (resultado) {
                var ok = resultado.status >= 200 && resultado.status < 300 && resultado.json && resultado.json.ok === true;
                var mensagem = ok ? '' : mensagemErro(resultado.json.message, resultado.status);
                var valorServidor = resultado.json && resultado.json.nivel_valor;
                var proximo = finalizar(fila, chave, ok, mensagem, ok ? (valorServidor !== undefined ? valorServidor : valor) : undefined);
                if (ok) {
                    var select = wrap.querySelector('select.js-nivel-autosave');
                    if (select && valorServidor !== undefined && fila.pendente[chave] === undefined) {
                        select.value = String(valorServidor);
                    }
                    pintar(chave, 'salvo');
                    salvoTimers[chave] = setTimeout(function () {
                        if (!fila.emVoo[chave] && !fila.pendente[chave] && !fila.erros[chave]) pintar(chave, '');
                        delete salvoTimers[chave];
                    }, MOSTRAR_SALVO_MS);
                } else {
                    var selectErro = wrap.querySelector('select.js-nivel-autosave');
                    var reversao = valorReversao(fila, chave);
                    if (selectErro && fila.pendente[chave] === undefined) {
                        selectErro.value = reversao;
                        fila.ultimo[chave] = reversao;
                    }
                    pintar(chave, 'erro', mensagem);
                }
                if (proximo !== undefined) {
                    enviar(chave);
                }
            })
            .catch(function (erro) {
                var mensagem = mensagemErro('', 0) + (erro && erro.message ? ' (' + erro.message + ')' : '');
                var proximo = finalizar(fila, chave, false, mensagem);
                var selectErro = wrap.querySelector('select.js-nivel-autosave');
                var reversao = valorReversao(fila, chave);
                if (selectErro && proximo === undefined) {
                    selectErro.value = reversao;
                    fila.ultimo[chave] = reversao;
                }
                pintar(chave, 'erro', mensagem);
                if (proximo !== undefined) enviar(chave);
            });
    }

    function agendarEnvio(chave, valor) {
        var proximo = agendar(fila, chave, valor);
        if (timers[chave]) clearTimeout(timers[chave]);
        if (proximo !== null) {
            pintar(chave, 'salvando');
            timers[chave] = setTimeout(function () {
                delete timers[chave];
                enviar(chave);
            }, DEBOUNCE_MS);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var wraps = document.querySelectorAll('.nivel-autosave-wrap');
        if (!wraps.length) return;

        wraps.forEach(function (wrap) {
            var dados = lerWrap(wrap);
            var chave = chaveLinha(dados);
            wrap.setAttribute('data-chave', chave);
            definirConfirmado(fila, chave, dados.nivel);
            pintar(chave, '');

            var select = wrap.querySelector('select.js-nivel-autosave');
            if (!select) return;
            select.addEventListener('change', function () {
                agendarEnvio(chave, select.value);
            });
        });

        window.addEventListener('beforeunload', function (evento) {
            if (!temPendencia(fila) && !temErro(fila)) return;
            evento.preventDefault();
            evento.returnValue = '';
        });
    });
})(typeof globalThis !== 'undefined' ? globalThis : this);
