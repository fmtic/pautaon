/* ═══════════════════════════════════════════════════════════════
   CONSELHOS DE CLASSE — CRUD AJAX dentro do form de Período Letivo
   Localização: static/js/periodos/conselhos.js
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ─── Config ───────────────────────────────────── */
  const periodoIdEl = document.getElementById('conselhoPeriodoId');
  if (!periodoIdEl) return;                       // modo "novo": nada a fazer

  const PERIODO_ID = periodoIdEl.value;
  const CSRF = document.querySelector('#periodoForm input[name="csrf_token"]')?.value || '';

  const URL_NOVO    = `/periodos/${PERIODO_ID}/conselhos/novo`;
  const URL_EDITAR  = (id) => `/conselhos-periodo/${encodeURIComponent(id)}/editar`;
  const URL_EXCLUIR = (id) => `/conselhos-periodo/${encodeURIComponent(id)}/excluir`;

  /* ─── Elementos ────────────────────────────────── */
  const tbody       = document.getElementById('conselhosTbody');
  const btnNovo     = document.getElementById('btnNovoConselho');
  const modalEl     = document.getElementById('modalConselho');
  const modalTitle  = document.getElementById('modalConselhoTitle');
  const inputId     = document.getElementById('conselhoId');
  const inputNome   = document.getElementById('conselhoNome');
  const inputEtapa  = document.getElementById('conselhoEtapa');
  const inputInicio = document.getElementById('conselhoInicio');
  const inputFim    = document.getElementById('conselhoFim');
  const inputObs    = document.getElementById('conselhoObs');
  const btnSalvar   = document.getElementById('btnSalvarConselho');
  const formMsg     = document.getElementById('conselhoFormMsg');

  const modal = modalEl ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;

  /* ─── Helpers ──────────────────────────────────── */
  const fmtBR = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-');
    return `${d}/${m}/${y}`;
  };

  const diasEntre = (ini, fim) => {
    const a = new Date(ini + 'T00:00:00');
    const b = new Date(fim + 'T00:00:00');
    return Math.round((b - a) / 86400000) + 1;
  };

  function showMsg(msg, tipo = 'danger') {
    if (!formMsg) return;
    formMsg.innerHTML = `<span class="text-${tipo}">${msg}</span>`;
    setTimeout(() => (formMsg.innerHTML = ''), 3500);
  }

  function limparModal() {
    inputId.value = '';
    inputNome.value = '';
    inputEtapa.value = '';
    inputInicio.value = '';
    inputFim.value = '';
    inputObs.value = '';
    formMsg.innerHTML = '';
  }

  function removeVazio() {
    document.getElementById('conselhosVazio')?.remove();
  }

  function escapeAttr(s) {
    return String(s ?? '').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  function buildRow(c) {
    const tr = document.createElement('tr');
    tr.dataset.id = c.id;
    const dur = diasEntre(c.data_inicio, c.data_fim);

    tr.innerHTML = `
      <td class="ps-3 fw-semibold">
        ${c.nome}
        ${c.etapa
          ? `<span class="badge bg-secondary-subtle text-secondary-emphasis border ms-2" style="font-size:.65rem;">${c.etapa}</span>`
          : ''}
        ${c.observacao
          ? `<i class="bi bi-info-circle text-muted ms-1" title="${escapeAttr(c.observacao)}"></i>`
          : ''}
      </td>
      <td>${c.data_inicio_br || fmtBR(c.data_inicio)}</td>
      <td>${c.data_fim_br || fmtBR(c.data_fim)}</td>
      <td class="text-muted small">${dur} dia${dur !== 1 ? 's' : ''}</td>
      <td class="text-end pe-3">
        <button class="btn btn-sm btn-outline-primary border-0 btn-editar-conselho"
          data-id="${c.id}"
          data-nome="${escapeAttr(c.nome)}"
          data-etapa="${escapeAttr(c.etapa || '')}"
          data-inicio="${c.data_inicio}"
          data-fim="${c.data_fim}"
          data-obs="${escapeAttr(c.observacao || '')}"
          title="Editar"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-danger border-0 btn-excluir-conselho"
          data-id="${c.id}" data-nome="${escapeAttr(c.nome)}"
          title="Excluir"><i class="bi bi-trash"></i></button>
      </td>`;
    return tr;
  }

  /* ─── Abrir modal para NOVO ────────────────────── */
  if (btnNovo) {
    btnNovo.addEventListener('click', () => {
      limparModal();
      modalTitle.innerHTML = '<i class="bi bi-calendar-check me-2"></i>Novo Conselho de Classe';
      modal.show();
      setTimeout(() => inputNome.focus(), 300);
    });
  }

  /* ─── Delegar edição e exclusão ────────────────── */
  if (tbody) {
    tbody.addEventListener('click', (e) => {
      /* Editar */
      const btnEd = e.target.closest('.btn-editar-conselho');
      if (btnEd) {
        limparModal();
        inputId.value     = btnEd.dataset.id;
        inputNome.value   = btnEd.dataset.nome;
        inputEtapa.value  = btnEd.dataset.etapa || '';
        inputInicio.value = btnEd.dataset.inicio || '';
        inputFim.value    = btnEd.dataset.fim || '';
        inputObs.value    = btnEd.dataset.obs || '';
        modalTitle.innerHTML = '<i class="bi bi-pencil-square me-2"></i>Editar Conselho de Classe';
        modal.show();
        return;
      }

      /* Excluir */
      const btnEx = e.target.closest('.btn-excluir-conselho');
      if (!btnEx) return;
      if (!confirm(`Excluir o conselho "${btnEx.dataset.nome}"?`)) return;

      fetch(URL_EXCLUIR(btnEx.dataset.id), {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF },
      })
        .then(r => r.json())
        .then(data => {
          if (!data.success) return;
          tbody.querySelector(`tr[data-id="${btnEx.dataset.id}"]`)?.remove();
          if (!tbody.querySelector('tr[data-id]')) {
            tbody.innerHTML = `<tr id="conselhosVazio">
              <td colspan="5" class="text-center text-muted py-4">
                <i class="bi bi-calendar-x d-block mb-2 opacity-25 fs-3"></i>
                Nenhum conselho cadastrado. Clique em <strong>Novo Conselho</strong> para começar.
              </td></tr>`;
          }
        })
        .catch(err => console.error('[excluir-conselho]', err));
    });
  }

  /* ─── Salvar (novo ou edição) ──────────────────── */
  if (btnSalvar) {
    btnSalvar.addEventListener('click', async () => {
      const id = inputId.value;
      const payload = {
        nome: inputNome.value.trim(),
        etapa: inputEtapa.value || null,
        data_inicio: inputInicio.value,
        data_fim: inputFim.value,
        observacao: inputObs.value.trim() || null,
      };

      if (!payload.nome)                 { showMsg('Informe o nome do conselho.'); return; }
      if (!payload.data_inicio || !payload.data_fim) {
        showMsg('Informe as datas de início e fim.'); return;
      }
      if (payload.data_fim < payload.data_inicio) {
        showMsg('A data final não pode ser anterior à inicial.'); return;
      }

      btnSalvar.disabled = true;
      try {
        const url = id ? URL_EDITAR(id) : URL_NOVO;
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
          body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!data.success) {
          showMsg(data.message || 'Erro ao salvar.');
          return;
        }

        removeVazio();
        const linhaExistente = tbody.querySelector(`tr[data-id="${data.id}"]`);
        if (linhaExistente) {
          linhaExistente.replaceWith(buildRow(data));
        } else {
          tbody.appendChild(buildRow(data));
        }

        // Animação suave de destaque na linha salva
        const linhaNova = tbody.querySelector(`tr[data-id="${data.id}"]`);
        if (linhaNova) {
          linhaNova.style.transition = 'background-color .6s';
          linhaNova.style.backgroundColor = '#fff3cd';
          setTimeout(() => (linhaNova.style.backgroundColor = ''), 700);
        }

        modal.hide();
      } catch (err) {
        console.error('[salvar-conselho]', err);
        showMsg('Falha de rede. Tente novamente.');
      } finally {
        btnSalvar.disabled = false;
      }
    });
  }

})();