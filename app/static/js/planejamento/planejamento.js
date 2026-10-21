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
  if (savedTab && window.bootstrap?.Tab) {
    const trigger = document.querySelector(`[data-bs-target="${savedTab}"]`);
    if (trigger) {
      try {
        window.bootstrap.Tab.getOrCreateInstance(trigger).show();
      } catch (error) {
        console.warn('[planejamento] Não foi possível restaurar a aba salva.', error);
      }
    }
  }
  document.querySelectorAll('[data-bs-toggle="pill"]').forEach(el => {
    el.addEventListener('shown.bs.tab', e => {
      localStorage.setItem(TAB_KEY, e.target.dataset.bsTarget);
    });
  });

  /* ─────────────────────────────────────────────
     3. Busca client-side na tabela de temas
     ───────────────────────────────────────────── */
  /* Busca server-side com pequeno atraso para limitar requisições. */
  const temaSearch = document.getElementById('temaSearch');
  if (temaSearch?.form) {
    let searchTimer;
    temaSearch.addEventListener('input', () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => temaSearch.form.requestSubmit(), 450);
    });
  }

  /* ─────────────────────────────────────────────
     5. Gestão de Cursos (AJAX)
     ───────────────────────────────────────────── */
  (function initCursos() {
    const tbody = document.getElementById('cursosTbody');
    if (!tbody) return;
    const modal = document.getElementById('modalCursos');

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
      formMsg.className = `mt-2 small text-${tipo}`;
      formMsg.textContent = msg;
    }

    async function readJsonResponse(response) {
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }
      if (!response.ok) {
        throw new Error(data?.message || `Não foi possível concluir a operação (HTTP ${response.status}).`);
      }
      if (!data || typeof data !== 'object' || data.success === false) {
        throw new Error(data?.message || 'O servidor retornou uma resposta inválida.');
      }
      return data;
    }

    function buildRow(c) {
      const tr = document.createElement('tr');
      tr.dataset.id = c.id;
      tr.innerHTML = `
        <td class="ps-3 fw-semibold">${c.nome}</td>
        <td class="text-muted small">${c.descricao || '—'}</td>
        <td class="text-center small">${c.carga_horaria ? c.carga_horaria + 'h' : '—'}</td>
        <td class="text-center small" title="${c.dias_aula || 0} dias de aula no período">${c.carga_total ? c.carga_total + 'h' : '—'}</td>
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

    async function carregarCursos() {
      try {
        const response = await fetch('/cursos', { headers: { Accept: 'application/json' } });
        const cursos = await readJsonResponse(response);
        tbody.replaceChildren();
        if (!cursos.length) {
          tbody.innerHTML = `<tr id="cursoVazio">
            <td colspan="5" class="text-center text-muted py-4">
              <i class="bi bi-mortarboard d-block mb-2 opacity-25 fs-3"></i>
              Nenhum curso cadastrado para esta unidade.
            </td></tr>`;
          return;
        }
        cursos.forEach(curso => tbody.appendChild(buildRow(curso)));
      } catch (error) {
        console.warn('[planejamento] Não foi possível atualizar a lista de cursos.', error);
      }
    }

    modal?.addEventListener('show.bs.modal', carregarCursos);


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

        try {
          const res = await fetch(URL_NOVO, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
            body: JSON.stringify({
              nome,
              descricao: descInput.value.trim(),
              carga_horaria: cargaInput.value || null,
            }),
          });
          const data = await readJsonResponse(res);
          removeVazio();
          tbody.appendChild(buildRow(data));
          sincronizarSelects(data);
          nomeInput.value = '';
          descInput.value = '';
          cargaInput.value = '';
          showMsg('Curso adicionado!', 'success');
        } catch (error) {
          showMsg(error.message || 'Erro ao adicionar.');
        }
      });
    }

    /* ── Editar / Excluir (delegação) ── */
    tbody.addEventListener('click', async e => {
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

      try {
        const response = await fetch(URL_EXCLUIR(btnEx.dataset.id), {
          method: 'POST',
          headers: csrfHeaders(),
        });
        await readJsonResponse(response);
        tbody.querySelector(`tr[data-id="${btnEx.dataset.id}"]`)?.remove();
        sincronizarSelects({ id: btnEx.dataset.id }, true);
        if (!tbody.querySelector('tr[data-id]')) {
          tbody.innerHTML = `<tr id="cursoVazio">
            <td colspan="5" class="text-center text-muted py-4">
              <i class="bi bi-mortarboard d-block mb-2 opacity-25 fs-3"></i>
              Nenhum curso cadastrado para esta unidade.
            </td></tr>`;
        }
        showMsg('Curso excluído.', 'success');
      } catch (error) {
        showMsg(error.message || 'Erro ao excluir curso.');
      }
    });

    /* ── Salvar edição ── */
    if (btnSalvarEd) {
      btnSalvarEd.addEventListener('click', async () => {
        const nome = editNome.value.trim();
        if (!nome) { showMsg('Nome obrigatório.'); return; }

        try {
          const res = await fetch(URL_EDITAR(editId.value), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
            body: JSON.stringify({
              nome,
              descricao: editDesc.value.trim(),
              carga_horaria: editCarga.value || null,
            }),
          });
          const data = await readJsonResponse(res);
          const tr = tbody.querySelector(`tr[data-id="${data.id}"]`);
          if (tr) tr.replaceWith(buildRow(data));
          sincronizarSelects(data);
          painelEdit.classList.add('d-none');
          showMsg('Curso atualizado!', 'success');
        } catch (error) {
          showMsg(error.message || 'Erro ao salvar curso.');
        }
      });
    }

    /* ── Cancelar edição ── */
    if (btnCancelar) {
      btnCancelar.addEventListener('click', () => painelEdit.classList.add('d-none'));
    }
  })();

  /* Carrega e exibe os dias sem aula do período selecionado. */
  (function initCalendarioBloqueados() {
    const select = document.getElementById('calPeriodoSelect');
    const grade = document.getElementById('calGrade');
    const status = document.getElementById('calStatus');
    const exportar = document.getElementById('btnExportarCal');
    const modal = document.getElementById('modalCalendario');
    if (!select || !grade || !modal) return;

    const tipos = {
      FERIADO: ['Feriado', '#dc3545'],
      ATIVIDADE_PEDAGOGICA: ['Atividade pedagógica', '#0d6efd'],
      REUNIAO_PAIS: ['Reunião de pais', '#6f42c1'],
      ATIVIDADE_INTERNA: ['Atividade interna', '#fd7e14'],
      MANUTENCAO: ['Manutenção', '#6c757d'],
    };
    let requestId = 0;
    let diasCarregados = [];
    let tipoAtivo = null;
    const btnLimpar = document.getElementById('btnLimparSel');
    const botoesTipo = [...document.querySelectorAll('#modalCalendario .tipo-btn')];

    function showMessage(message) {
      grade.replaceChildren();
      const p = document.createElement('p');
      p.className = 'text-center text-muted py-5 mb-0';
      p.textContent = message;
      grade.appendChild(p);
    }

    function atualizarContagem() {
      if (!status) return;
      const count = tipoAtivo
        ? diasCarregados.filter(day => day.tipo === tipoAtivo).length
        : diasCarregados.length;
      status.textContent = `${count} ${count === 1 ? 'dia bloqueado' : 'dias bloqueados'}`;
    }

    function renderDays(days) {
      diasCarregados = [...days].sort((a, b) => a.data.localeCompare(b.data));
      const visiveis = tipoAtivo
        ? diasCarregados.filter(day => day.tipo === tipoAtivo)
        : diasCarregados;
      grade.replaceChildren();
      if (!diasCarregados.length) {
        showMessage('Nenhum dia bloqueado cadastrado para este período.');
        return;
      }
      if (!visiveis.length) {
        showMessage('Nenhum dia bloqueado encontrado nesta legenda.');
        return;
      }

      const list = document.createElement('div');
      list.className = 'list-group list-group-flush';
      visiveis.forEach(day => {
        const item = document.createElement('div');
        item.className = 'list-group-item d-flex align-items-start gap-3 py-3';
        const date = document.createElement('strong');
        date.className = 'text-nowrap';
        date.textContent = new Date(`${day.data}T12:00:00`).toLocaleDateString('pt-BR');
        const info = document.createElement('div');
        const badge = document.createElement('span');
        const [label, color] = tipos[day.tipo] || [day.tipo || 'Dia bloqueado', '#6c757d'];
        badge.className = 'badge me-2';
        badge.style.backgroundColor = color;
        badge.textContent = label;
        info.appendChild(badge);
        if (day.descricao) {
          const description = document.createElement('span');
          description.textContent = day.descricao;
          info.appendChild(description);
        }
        item.append(date, info);
        list.appendChild(item);
      });
      grade.appendChild(list);
    }

    async function loadPeriod() {
      const periodId = select.value;
      const currentRequest = ++requestId;
      if (!periodId) {
        diasCarregados = [];
        if (exportar) exportar.classList.add('d-none');
        showMessage('Selecione um período letivo para consultar os dias sem aula.');
        if (status) status.textContent = '';
        return;
      }
      if (status) status.textContent = 'Carregando calendário…';
      showMessage('Carregando dias bloqueados…');
      if (exportar) {
        exportar.href = `/planejamento/calendario/${encodeURIComponent(periodId)}/exportar`;
        exportar.classList.remove('d-none');
      }
      try {
        const response = await fetch(`/planejamento/calendario/${encodeURIComponent(periodId)}`, {
          headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error(`Não foi possível carregar o calendário (HTTP ${response.status}).`);
        const days = await response.json();
        if (currentRequest !== requestId) return;
        if (!Array.isArray(days)) throw new Error('O servidor retornou um calendário inválido.');
        renderDays(days);
        atualizarContagem();
      } catch (error) {
        if (currentRequest !== requestId) return;
        diasCarregados = [];
        showMessage(error.message || 'Erro ao carregar os dias bloqueados.');
        if (status) status.textContent = 'Falha ao carregar';
      }
    }

    botoesTipo.forEach(button => {
      button.setAttribute('aria-pressed', 'false');
      button.addEventListener('click', () => {
        tipoAtivo = tipoAtivo === button.dataset.tipo ? null : button.dataset.tipo;
        botoesTipo.forEach(item => {
          const ativo = item.dataset.tipo === tipoAtivo;
          item.classList.toggle('ativo', ativo);
          item.setAttribute('aria-pressed', String(ativo));
        });
        renderDays(diasCarregados);
        atualizarContagem();
      });
    });

    btnLimpar?.addEventListener('click', () => {
      tipoAtivo = null;
      botoesTipo.forEach(button => {
        button.classList.remove('ativo');
        button.setAttribute('aria-pressed', 'false');
      });
      renderDays(diasCarregados);
      atualizarContagem();
    });

    select.addEventListener('change', () => {
      tipoAtivo = null;
      botoesTipo.forEach(button => {
        button.classList.remove('ativo');
        button.setAttribute('aria-pressed', 'false');
      });
      loadPeriod();
    });
    modal.addEventListener('show.bs.modal', () => {
      if (!select.value && select.options.length > 1) select.selectedIndex = 1;
      loadPeriod();
    });
  })();
})();
