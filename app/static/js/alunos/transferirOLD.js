// static/js/alunos/transferir.js

(function() {
    'use strict';

    const form = document.getElementById('transferForm');
    const destinoSelect = document.getElementById('turma_destino');
    const observacoes = document.getElementById('observacoes');
    const btnAbrirModal = document.getElementById('btnAbrirModal');
    const confirmarBtn = document.getElementById('confirmarTransferenciaBtn');
    const modalElement = document.getElementById('confirmarTransferenciaModal');

    if (!modalElement) {
        console.error('Modal não encontrado!');
        return;
    }

    let modal;
    if (typeof bootstrap !== 'undefined') {
        modal = new bootstrap.Modal(modalElement);
    } else {
        console.error('Bootstrap JS não carregado');
        return;
    }

    // Preenche os campos do modal
    function preencherModal() {
        const destinoOption = destinoSelect.options[destinoSelect.selectedIndex];
        const nomeDestino = destinoOption ? destinoOption.text : '';
        const obs = observacoes.value.trim();

        const modalDestino = document.getElementById('modalTurmaDestino');
        const modalObs = document.getElementById('modalObservacoes');

        if (modalDestino) modalDestino.textContent = nomeDestino;
        if (modalObs) modalObs.textContent = obs;
    }

    // Abrir modal com validação
    if (btnAbrirModal) {
        btnAbrirModal.addEventListener('click', function() {
            // Valida destino
            if (!destinoSelect.value) {
                alert('Selecione a turma de destino.');
                destinoSelect.focus();
                return;
            }
            // Valida observações
            const obsValue = observacoes.value.trim();
            if (obsValue === '') {
                alert('As observações são obrigatórias.');
                observacoes.focus();
                observacoes.classList.add('is-invalid');
                return;
            } else {
                observacoes.classList.remove('is-invalid');
            }
            preencherModal();
            modal.show();
        });
    }

    // Confirmar transferência
    if (confirmarBtn) {
        confirmarBtn.addEventListener('click', function() {
            modal.hide();
            form.submit();
        });
    }

    // Remover classe de erro ao digitar
    if (observacoes) {
        observacoes.addEventListener('input', function() {
            if (this.value.trim() !== '') this.classList.remove('is-invalid');
        });
    }
})();