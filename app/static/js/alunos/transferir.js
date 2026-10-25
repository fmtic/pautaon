// static/js/alunos/transferir.js
(function () {
  'use strict';

  // ------------------------------------------------------------
  // Elementos — falha rápido se o HTML não bater
  // ------------------------------------------------------------
  const form       = document.getElementById('transferForm');
  const destino    = document.getElementById('turma_destino');
  const data       = document.getElementById('data_transferencia');
  const obs        = document.getElementById('observacoes');
  const btnAbrir   = document.getElementById('btnAbrirModal');
  const btnOk      = document.getElementById('confirmarTransferenciaBtn');
  const modalEl    = document.getElementById('confirmarTransferenciaModal');
  const modalDest  = document.getElementById('modalTurmaDestino');
  const modalObs   = document.getElementById('modalObservacoes');

  if (!form || !destino || !data || !obs || !btnAbrir || !modalEl) {
    console.error('transferir.js: elementos obrigatórios ausentes no HTML.');
    return;
  }
  if (typeof bootstrap === 'undefined') {
    console.error('transferir.js: Bootstrap JS não carregado.');
    return;
  }

  const modal = new bootstrap.Modal(modalEl);

  // ------------------------------------------------------------
  // Validação
  // ------------------------------------------------------------
  function validar() {
    if (!destino.value) {
      alert('Selecione a oferta de destino.');
      destino.focus();
      return false;
    }
    if (!data.value) {
      alert('Informe a data da transferência.');
      data.focus();
      return false;
    }
    if (!obs.value.trim()) {
      alert('As observações são obrigatórias.');
      obs.focus();
      obs.classList.add('is-invalid');
      return false;
    }
    obs.classList.remove('is-invalid');
    return true;
  }

  // ------------------------------------------------------------
  // Abrir modal
  // ------------------------------------------------------------
  btnAbrir.addEventListener('click', () => {
    if (!validar()) return;

    if (modalDest) modalDest.textContent = destino.selectedOptions[0]?.text || '';
    if (modalObs)  modalObs.textContent  = obs.value.trim();

    modal.show();
  });

  // ------------------------------------------------------------
  // Confirmar
  // ------------------------------------------------------------
  btnOk?.addEventListener('click', () => {
    modal.hide();
    HTMLFormElement.prototype.submit.call(form);
  });

  // ------------------------------------------------------------
  // Limpar erro ao digitar
  // ------------------------------------------------------------
  obs.addEventListener('input', () => {
    if (obs.value.trim()) obs.classList.remove('is-invalid');
  });
})();
