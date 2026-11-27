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

    var MAX_TENTATIVAS = 3;

    function criarFila() {
        return {
            emVoo: {}, pendente: {}, erros: {}, ultimo: {}, confirmado: {},
            tentativas: {}, divergencia: {}
        };
    }

    function definirConfirmado(fila, chave, valor) {
        fila.confirmado[chave] = normalizarValor(valor);
        if (!(chave in fila.ultimo)) fila.ultimo[chave] = fila.confirmado[chave];
    }

    function agendar(fila, chave, valor) {
        var normalizado = normalizarValor(valor);
        fila.ultimo[chave] = normalizado;
        // Nova intenção do usuário zera a contagem de divergências anteriores.
        delete fila.tentativas[chave];
        delete fila.divergencia[chave];
        if (fila.emVoo[chave]) {
            fila.pendente[chave] = normalizado;
            return null;
        }
        if (normalizarValor(fila.confirmado[chave]) === normalizado && !fila.erros[chave]) {
            delete fila.pendente[chave];
            return null;
        }
        return normalizado;
    }

    function iniciar(fila, chave, valor) {
        fila.emVoo[chave] = normalizarValor(valor == null ? (fila.ultimo[chave] || '') : valor);
        delete fila.pendente[chave];
    }

    function normalizarValor(valor) {
        if (valor == null) return '';
        return String(valor).trim();
    }

    function finalizar(fila, chave, sucesso, mensagem, valorConfirmado) {
        delete fila.emVoo[chave];
        if (sucesso) {
            delete fila.erros[chave];
            // O confirmado só avança quando o chamador fornecer explicitamente
            // o valor devolvido pelo servidor (evita confirmar com "ultimo"
            // divergente durante uma correção/canonicalização).
            if (valorConfirmado !== undefined) {
                fila.confirmado[chave] = normalizarValor(valorConfirmado);
                var pendenteAtual = fila.pendente[chave];
                if (pendenteAtual === undefined || normalizarValor(pendenteAtual) === normalizarValor(fila.confirmado[chave])) {
                    fila.ultimo[chave] = fila.confirmado[chave];
                }
            }
        } else {
            fila.erros[chave] = mensagem || 'Falha ao salvar.';
            fila.tentativas[chave] = (fila.tentativas[chave] || 0) + 1;
        }
        var pendente = fila.pendente[chave];
        if (pendente === undefined) return null;
        if (normalizarValor(pendente) === normalizarValor(fila.confirmado[chave])) {
            delete fila.pendente[chave];
            fila.ultimo[chave] = fila.confirmado[chave];
            return null;
        }
        return pendente;
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
        return confirmado == null ? '' : normalizarValor(confirmado);
    }

    function podeTentarNovamente(fila, chave) {
        return (fila.tentativas[chave] || 0) < MAX_TENTATIVAS;
    }

    function deveReenfileirar(fila, chave, valorServidor) {
        var confirmado = normalizarValor(fila.confirmado[chave]);
        var servidor = normalizarValor(valorServidor);
        var ultimo = normalizarValor(fila.ultimo[chave]);
        if (servidor !== confirmado) return false;
        return ultimo !== confirmado;
    }

    // Analisa uma resposta bem-sucedida sem reenviar por divergência de formato:
    // - 'confirmado': servidor confirmou (ou canonicalizou) o valor enviado;
    // - 'reenviar': o usuário mudou depois do envio, ou uma tentativa anterior
    //   de divergência ainda não foi honrada pelo servidor.
    function analisarSucesso(fila, chave, valorEnviado, valorServidor) {
        var enviado = normalizarValor(valorEnviado);
        var servidor = normalizarValor(valorServidor);
        var ultimo = normalizarValor(fila.ultimo[chave]);
        if (ultimo !== enviado) return 'reenviar';
        if (servidor !== enviado && fila.divergencia[chave]) return 'reenviar';
        return 'confirmado';
    }

    function marcarDivergencia(fila, chave) {
        fila.divergencia[chave] = true;
        fila.tentativas[chave] = (fila.tentativas[chave] || 0) + 1;
        return podeTentarNovamente(fila, chave);
    }

    function limparDivergencia(fila, chave) {
        delete fila.divergencia[chave];
        delete fila.tentativas[chave];
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
            nivel: normalizarValor(dados.nivel)
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
        MAX_TENTATIVAS: MAX_TENTATIVAS,
        normalizarValor: normalizarValor,
        criarFila: criarFila,
        definirConfirmado: definirConfirmado,
        agendar: agendar,
        iniciar: iniciar,
        finalizar: finalizar,
        temPendencia: temPendencia,
        temErro: temErro,
        erroDaLinha: erroDaLinha,
        valorReversao: valorReversao,
        podeTentarNovamente: podeTentarNovamente,
        deveReenfileirar: deveReenfileirar,
        analisarSucesso: analisarSucesso,
        marcarDivergencia: marcarDivergencia,
        limparDivergencia: limparDivergencia,
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

    function valorParaSelect(select, valor) {
        var normalizado = normalizarValor(valor);
        if (!select) return normalizado;
        for (var i = 0; i < select.options.length; i += 1) {
            if (normalizarValor(select.options[i].value) === normalizado) {
                return select.options[i].value;
            }
        }
        return normalizado;
    }

    function aplicarConfirmadoNoSelect(chave, valorServidor) {
        var wrap = wrapDaChave(chave);
        if (!wrap) return;
        var select = wrap.querySelector('select.js-nivel-autosave');
        if (!select) return;
        var valor = valorParaSelect(select, valorServidor);
        if (normalizarValor(select.value) !== normalizarValor(valor)) {
            select.value = valor;
        }
    }

    function enviar(chave) {
        var wrap = wrapDaChave(chave);
        if (!wrap) return;
        var dados = lerWrap(wrap);
        var valor = fila.ultimo[chave];
        if (valor === undefined) valor = normalizarValor(dados.nivel);
        valor = normalizarValor(valor);
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
                var valorServidor = resultado.json && resultado.json.nivel_valor !== undefined
                    ? resultado.json.nivel_valor
                    : (resultado.json && resultado.json.nivel_nome !== undefined ? resultado.json.nivel_nome : valor);
                var confirmadoAnterior = valorReversao(fila, chave);
                // Não passa valorConfirmado aqui: a confirmação só é promovida
                // depois de analisar se o usuário mudou durante o envio.
                var proximo = finalizar(fila, chave, ok, mensagem, undefined);
                if (ok) {
                    var analise = analisarSucesso(fila, chave, valor, valorServidor);
                    // Usuário voltou ao valor já confirmado durante o envio:
                    // nada mais a enviar.
                    if (analise === 'reenviar' && proximo === null
                        && normalizarValor(fila.ultimo[chave]) === normalizarValor(confirmadoAnterior)) {
                        analise = 'confirmado';
                        valorServidor = confirmadoAnterior;
                    }
                    if (analise === 'reenviar') {
                        if (!marcarDivergencia(fila, chave)) {
                            fila.erros[chave] = 'Divergência persistente do nível confirmado.';
                            fila.confirmado[chave] = confirmadoAnterior;
                            fila.ultimo[chave] = confirmadoAnterior;
                            delete fila.pendente[chave];
                            aplicarConfirmadoNoSelect(chave, confirmadoAnterior);
                            pintar(chave, 'erro', 'O servidor não confirmou a alteração de nível após várias tentativas. O valor foi revertido.');
                            return;
                        }
                        enviar(chave);
                        return;
                    }
                    // Servidor confirmou (inclusive canonicalizando acento/caixa):
                    // promove o valor devolvido e alinha o select sem disparar change.
                    limparDivergencia(fila, chave);
                    fila.confirmado[chave] = normalizarValor(valorServidor);
                    fila.ultimo[chave] = normalizarValor(fila.confirmado[chave]);
                    delete fila.pendente[chave];
                    aplicarConfirmadoNoSelect(chave, fila.confirmado[chave]);
                    pintar(chave, 'salvo');
                    salvoTimers[chave] = setTimeout(function () {
                        if (!fila.emVoo[chave] && !fila.pendente[chave] && !fila.erros[chave]) pintar(chave, '');
                        delete salvoTimers[chave];
                    }, MOSTRAR_SALVO_MS);
                    return;
                }
                // Erro não dispara nova tentativa automática: só uma nova
                // alteração do usuário agenda reenvio (com contador zerado).
                if (fila.pendente[chave] === undefined) {
                    fila.ultimo[chave] = valorReversao(fila, chave);
                    aplicarConfirmadoNoSelect(chave, fila.confirmado[chave]);
                }
                delete fila.pendente[chave];
                pintar(chave, 'erro', mensagem);
                return;
            })
            .catch(function (erro) {
                var mensagem = mensagemErro('', 0) + (erro && erro.message ? ' (' + erro.message + ')' : '');
                finalizar(fila, chave, false, mensagem);
                if (!podeTentarNovamente(fila, chave)) {
                    fila.ultimo[chave] = valorReversao(fila, chave);
                    delete fila.pendente[chave];
                    aplicarConfirmadoNoSelect(chave, fila.confirmado[chave]);
                    pintar(chave, 'erro', 'Não foi possível salvar o nível após várias tentativas. O valor foi revertido.');
                    return;
                }
                if (fila.pendente[chave] === undefined) {
                    fila.ultimo[chave] = valorReversao(fila, chave);
                    aplicarConfirmadoNoSelect(chave, fila.confirmado[chave]);
                }
                // Falha de rede não gera retry automático; nova alteração do
                // usuário limpa o contador e agenda uma nova tentativa.
                delete fila.pendente[chave];
                pintar(chave, 'erro', mensagem);
            });
    }

    function agendarEnvio(chave, valor) {
        var proximo = agendar(fila, chave, valor);
        if (timers[chave]) clearTimeout(timers[chave]);
        if (proximo !== null) {
            pintar(chave, 'salvando');
            timers[chave] = setTimeout(function () {
                delete timers[chave];
                if (fila.emVoo[chave]) return;
                if (normalizarValor(fila.ultimo[chave]) === normalizarValor(fila.confirmado[chave])) return;
                enviar(chave);
            }, DEBOUNCE_MS);
        } else if (!fila.emVoo[chave] && normalizarValor(fila.ultimo[chave]) === normalizarValor(fila.confirmado[chave]) && !fila.erros[chave]) {
            pintar(chave, '');
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
