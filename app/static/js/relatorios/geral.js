/* Resumo - Primeira Vista — impressão (AJ28). */

(function () {
    'use strict';

    function preencherEmissao() {
        const agora = new Date().toLocaleString('pt-BR');
        const rodape = document.getElementById('print-date');
        if (rodape) {
            rodape.textContent = agora;
        }
        document.querySelectorAll('.geral-emissao').forEach((el) => {
            el.textContent = agora;
        });
    }

    function prepararImpressao() {
        preencherEmissao();
        window.print();
    }

    window.prepararImpressao = prepararImpressao;
    // Ctrl+P e o menu do navegador também precisam da emissão atualizada.
    window.addEventListener('beforeprint', preencherEmissao);

    document.addEventListener('DOMContentLoaded', preencherEmissao);
})();
