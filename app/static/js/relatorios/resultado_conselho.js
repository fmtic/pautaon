/* Resultado do Conselho — filtros, CSV e impressão (AJ26). */

(function () {
    'use strict';

    function normalizar(texto) {
        return (texto || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLocaleLowerCase('pt-BR');
    }

    function preencherEmissao() {
        const agora = new Date().toLocaleString('pt-BR');
        const rodape = document.getElementById('print-date');
        if (rodape) {
            rodape.textContent = agora;
        }
        document.querySelectorAll('.resultado-emissao').forEach((el) => {
            el.textContent = agora;
        });
    }

    function prepararImpressao() {
        preencherEmissao();
        window.print();
    }

    function textoCelula(celula) {
        const copia = celula.cloneNode(true);
        copia.querySelectorAll('br').forEach((quebra) => {
            quebra.replaceWith(document.createTextNode(' — '));
        });
        return (copia.textContent || '').replace(/\s+/g, ' ').trim();
    }

    function valorCSV(valor) {
        return '"' + String(valor).replace(/"/g, '""') + '"';
    }

    function exportarCSV() {
        const tabela = document.getElementById('tabelaResultado');
        if (!tabela) {
            return;
        }
        // AJ27: a ordem das colunas do CSV vem do DOM da tabela, já na ordem
        // definida para tela e impressão (sem lista duplicada de cabeçalhos).
        const linhas = Array.from(tabela.querySelectorAll('tr'));
        const csv = linhas
            .map((tr) =>
                Array.from(tr.querySelectorAll('th, td'))
                    .map((celula) => valorCSV(textoCelula(celula)))
                    .join(';')
            )
            .join('\r\n');

        const blob = new Blob(['\uFEFF' + csv], {
            type: 'text/csv;charset=utf-8;',
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'resultado_conselho_' + new Date().toISOString().slice(0, 10) + '.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    window.prepararImpressao = prepararImpressao;
    window.exportarCSV = exportarCSV;
    // Ctrl+P/menu do navegador também precisa da data de emissão atual.
    window.addEventListener('beforeprint', preencherEmissao);

    document.addEventListener('DOMContentLoaded', function () {
        preencherEmissao();

        const periodo = document.getElementById('periodo_letivo_id');
        const todas = document.getElementById('turmas_all');
        const busca = document.getElementById('buscaTurmas');
        const lista = document.getElementById('listaTurmas');
        const marcarTodas = document.getElementById('marcarTodasTurmas');
        const limpar = document.getElementById('limparTurmas');
        if (!lista) {
            return;
        }

        const itens = Array.from(lista.querySelectorAll('.turma-checkbox-item'));
        const checkboxes = itens
            .map((item) => item.querySelector('input[type="checkbox"][name="turmas"]'))
            .filter(Boolean);

        function aplicarBusca() {
            const termo = normalizar(busca ? busca.value : '');
            itens.forEach((item) => {
                const texto = normalizar(item.dataset.busca || item.textContent);
                item.hidden = Boolean(termo) && texto.indexOf(termo) === -1;
            });
        }

        function sincronizarTodas() {
            const desabilitar = Boolean(todas && todas.checked);
            checkboxes.forEach((box) => {
                box.disabled = desabilitar;
            });
            if (lista) {
                lista.classList.toggle('turmas-desabilitadas', desabilitar);
            }
        }

        if (todas) {
            todas.addEventListener('change', sincronizarTodas);
        }
        if (busca) {
            busca.addEventListener('input', aplicarBusca);
        }
        if (marcarTodas) {
            marcarTodas.addEventListener('click', function () {
                if (todas) {
                    todas.checked = false;
                }
                checkboxes.forEach((box) => {
                    const item = box.closest('.turma-checkbox-item');
                    if (!item || !item.hidden) {
                        box.disabled = false;
                        box.checked = true;
                    }
                });
                sincronizarTodas();
            });
        }
        if (limpar) {
            limpar.addEventListener('click', function () {
                checkboxes.forEach((box) => {
                    box.checked = false;
                });
            });
        }

        // Trocar o período recarrega a lista no servidor: IDs de turmas de
        // outro período não podem sobreviver na query string.
        if (periodo) {
            periodo.addEventListener('change', function () {
                if (!periodo.value) {
                    return;
                }
                const url = new URL(window.location.href);
                url.searchParams.set('periodo_letivo_id', periodo.value);
                url.searchParams.delete('turmas');
                url.searchParams.delete('turmas_all');
                url.searchParams.delete('oferta_sel');
                window.location.assign(url.toString());
            });
        }

        sincronizarTodas();
        aplicarBusca();
    });
})();
