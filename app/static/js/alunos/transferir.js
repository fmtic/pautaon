// static/js/alunos/transferir.js
(function() {
    'use strict';

    const origem = document.getElementById('turma_origem');
    const destino = document.getElementById('turma_destino');

    function validarTurmas() {
        if (origem && destino && origem.value && destino.value && origem.value === destino.value) {
            alert('A turma de origem e destino devem ser diferentes!');
            destino.value = '';
        }
    }

    if (origem) origem.addEventListener('change', validarTurmas);
    if (destino) destino.addEventListener('change', validarTurmas);
})();