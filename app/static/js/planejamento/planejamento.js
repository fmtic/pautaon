/* ═══════════════════════════════════════════════════════════════
   PLANEJAMENTO — Comportamento da página
   Localização: static/js/planejamento/planejamento.js
   Dependências: Bootstrap 5 (tabs, modais)
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ─────────────────────────────────────────────
     1. Config (lida do #planejamentoConfig)
     ───────────────────────────────────────────── */
  const cfgEl = document.getElementById('planejamentoConfig');
  const CFG = {
    csrf: cfgEl?.dataset.csrf || '',
    urlTemaMover: cfgEl?.dataset.urlTemaMover || '/temas/__id__/mover/__dir__',
  };

  const csrfHeaders = () => ({ 'X-CSRFToken': CFG.csrf });

  const tplIdDir = (tpl, id, dir) =>
    tpl.replace('__id__', encodeURIComponent(id))
       .replace('__dir__', encodeURIComponent(dir));

  /** Formata 1 → "01", 10 → "10", 123 → "123" */
  const fmtOrdem = (n) => String(n).padStart(2, '0');

  /* ─────────────────────────────────────────────
     2. Persistência da aba ativa
     ───────────────────────────────────────────── */
  const TAB_KEY = 'planejamento.activeTab';
  const savedTab = localStorage.getItem(TAB_KEY);
  if (savedTab) {
    const trigger = document.querySelector(`[data-bs-target="${savedTab}"]`);
    if (trigger) bootstrap.Tab.getOrCreateInstance(trigger).show();
  }
  document.querySelectorAll('[data-bs-toggle="pill"]').forEach(el => {
    el.addEventListener('shown.bs.tab', e => {
      localStorage.setItem(TAB_KEY, e.target.dataset.bsTarget);
    });
  });

  /* ─────────────────────────────────────────────
     3. Busca client-side na tabela de temas
     ───────────────────────────────────────────── */
  const temaSearch = document.getElementById('temaSearch');
  if (temaSearch) {
    temaSearch.addEventListener('input', e => {
      const q = e.target.value.toLowerCase().trim();
      document.querySelectorAll('#temasTbody tr[data-tema]').forEach(tr => {
        tr.style.display = !q || tr.dataset.tema.includes(q) ? '' : 'none';
      });
    });
  }



  /* ─────────────────────────────────────────────
     5. Gestão de Cursos (AJAX)
     ───────────────────────────────────────────── */
  (function initCursos() {
    const tbody = document.getElementById('cursosTbody');
    if (!tbody) return;

    const nomeInput   = document.getElementById('cursoNomeInput');
    const descInput   = document.getElementById('cursoDescInput');
    const cargaInput  = document.getElementById('cursoCargaInput');
    const btnNovo     = document.getElementById('btnNovoCurso');
    const formMsg     = document.getElementById('cursoFormMsg');
    const painelEdit  = document.getElementById('painelEditCurso');
    const editId      = document.getElementById('editCursoId');
    const editNome    = document.getElementById('editCursoNome');
    const editDesc    = document.getElementById('editCursoDesc');
    const editCarga   = document.getElementById('editCursoCarga');
    const btnSalvarEd = document.getElementById('btnSalvarEditCurso');
    const btnCancelar = document.getElementById('btnCancelarEditCurso');

    // URLs do backend
    const URL_NOVO    = '/cursos/novo';
    const URL_EDITAR  = (id) => `/cursos/${encodeURIComponent(id)}/editar`;
    const URL_EXCLUIR = (id) => `/cursos/${encodeURIComponent(id)}/excluir`;

    function showMsg(msg, tipo = 'danger') {
      if (!formMsg) return;
      formMsg.innerHTML = `<span class="text-${tipo}">${msg}</span>`;
      setTimeout(() => (formMsg.innerHTML = ''), 3000);
    }

    function buildRow(c) {
      const tr = document.createElement('tr');
      tr.dataset.id = c.id;
      tr.innerHTML = `
        <td class="ps-3 fw-semibold">${c.nome}</td>
        <td class="text-muted small">${c.descricao || '—'}</td>
        <td class="text-center small">${c.carga_horaria ? c.carga_horaria + 'h' : '—'}</td>
        <td class="text-center">
          <button class="btn btn-sm btn-outline-primary border-0 btn-editar-curso"
            data-id="${c.id}" data-nome="${c.nome}" data-desc="${c.descricao || ''}"
            data-carga="${c.carga_horaria || ''}" title="Editar">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger border-0 btn-excluir-curso"
            data-id="${c.id}" data-nome="${c.nome}" title="Excluir">
            <i class="bi bi-trash"></i>
          </button>
        </td>`;
      return tr;
    }

    function removeVazio() {
      document.getElementById('cursoVazio')?.remove();
    }

    /** Sincroniza os <select name="curso_id"> da página */
    function sincronizarSelects(c, remover = false) {
      document.querySelectorAll('select[name="curso_id"]').forEach(sel => {
        if (remover) {
          sel.querySelector(`option[value="${c.id}"]`)?.remove();
          return;
        }
        let opt = sel.querySelector(`option[value="${c.id}"]`);
        if (opt) {
          opt.textContent = c.nome;
        } else {
          opt = document.createElement('option');
          opt.value = c.id;
          opt.textContent = c.nome;
          sel.appendChild(opt);
        }
      });
    }

    /* ── Adicionar ── */
    if (btnNovo) {
      btnNovo.addEventListener('click', async () => {
        const nome = nomeInput.value.trim();
        if (!nome) { showMsg('Informe o nome do curso.'); return; }

        const res = await fetch(URL_NOVO, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
          body: JSON.stringify({
            nome,
            descricao: descInput.value.trim(),
            carga_horaria: cargaInput.value || null,
          }),
        });
        const data = await res.json();
        if (data.success) {
          removeVazio();
          tbody.appendChild(buildRow(data));
          sincronizarSelects(data);
          nomeInput.value = '';
          descInput.value = '';
          cargaInput.value = '';
          showMsg('Curso adicionado!', 'success');
        } else {
          showMsg(data.message || 'Erro ao adicionar.');
        }
      });
    }

    /* ── Editar / Excluir (delegação) ── */
    tbody.addEventListener('click', e => {
      const btnEd = e.target.closest('.btn-editar-curso');
      if (btnEd) {
        editId.value    = btnEd.dataset.id;
        editNome.value  = btnEd.dataset.nome;
        editDesc.value  = btnEd.dataset.desc;
        editCarga.value = btnEd.dataset.carga;
        painelEdit.classList.remove('d-none');
        editNome.focus();
        return;
      }

      const btnEx = e.target.closest('.btn-excluir-curso');
      if (!btnEx) return;

      if (!confirm(`Excluir o curso "${btnEx.dataset.nome}"?`)) return;

      fetch(URL_EXCLUIR(btnEx.dataset.id), {
        method: 'POST',
        headers: csrfHeaders(),
      })
        .then(r => r.json())
        .then(data => {
          if (!data.success) return;
          tbody.querySelector(`tr[data-id="${btnEx.dataset.id}"]`)?.remove();
          sincronizarSelects({ id: btnEx.dataset.id }, true);
          if (!tbody.querySelector('tr[data-id]')) {
            tbody.innerHTML = `<tr id="cursoVazio">
              <td colspan="4" class="text-center text-muted py-4">
                <i class="bi bi-mortarboard d-block mb-2 opacity-25 fs-3"></i>
                Nenhum curso cadastrado para esta unidade.
              </td></tr>`;
          }
        })
        .catch(err => console.error('[excluir-curso]', err));
    });

    /* ── Salvar edição ── */
    if (btnSalvarEd) {
      btnSalvarEd.addEventListener('click', async () => {
        const nome = editNome.value.trim();
        if (!nome) { showMsg('Nome obrigatório.'); return; }

        const res = await fetch(URL_EDITAR(editId.value), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
          body: JSON.stringify({
            nome,
            descricao: editDesc.value.trim(),
            carga_horaria: editCarga.value || null,
          }),
        });
        const data = await res.json();
        if (data.success) {
          const tr = tbody.querySelector(`tr[data-id="${data.id}"]`);
          if (tr) tr.replaceWith(buildRow(data));
          sincronizarSelects(data);
          painelEdit.classList.add('d-none');
          showMsg('Curso atualizado!', 'success');
        } else {
          showMsg(data.message || 'Erro ao salvar.');
        }
      });
    }

    /* ── Cancelar edição ── */
    if (btnCancelar) {
      btnCancelar.addEventListener('click', () => painelEdit.classList.add('d-none'));
    }
  })();

})();