// static/js/turmas/imprimir_pauta.js
(function() {
    'use strict';
    const agora = new Date().toLocaleString('pt-BR');
    const dataEmissao = document.getElementById('dataEmissao');
    const footerData = document.getElementById('footerData');
    if (dataEmissao) dataEmissao.textContent = 'Emissão: ' + agora;
    if (footerData) footerData.textContent = 'Emissão: ' + agora;
})();