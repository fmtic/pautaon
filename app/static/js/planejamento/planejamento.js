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
    const tbodyInativos = document.getElementById('cursosInativosTbody');
    if (!tbody) return;
    const modal = document.getElementById('modalCursos');

    const nomeInput   = document.getElementById('cursoNomeInput');
    const descInput   = document.getElementById('cursoDescInput');
    const btnNovo     = document.getElementById('btnNovoCurso');
    const formMsg     = document.getElementById('cursoFormMsg');
    const painelEdit  = document.getElementById('painelEditCurso');
    const editId      = document.getElementById('editCursoId');
    const editNome    = document.getElementById('editCursoNome');
    const editDesc    = document.getElementById('editCursoDesc');
    const btnSalvarEd = document.getElementById('btnSalvarEditCurso');
    const btnCancelar = document.getElementById('btnCancelarEditCurso');

    // URLs do backend
    const URL_NOVO    = '/cursos/novo';
    const URL_INATIVOS = '/cursos/inativos';
    const URL_EDITAR  = (id) => `/cursos/${encodeURIComponent(id)}/editar`;
    const URL_INATIVAR = (id) => `/cursos/${encodeURIComponent(id)}/inativar`;
    const URL_REATIVAR = (id) => `/cursos/${encodeURIComponent(id)}/reativar`;

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
      const nome = document.createElement('td');
      nome.className = 'ps-3 fw-semibold';
      nome.textContent = c.nome;
      const descricao = document.createElement('td');
      descricao.className = 'text-muted small';
      descricao.textContent = c.descricao || '—';
      const status = document.createElement('td');
      status.className = 'text-center';
      const badge = document.createElement('span');
      badge.className = 'badge bg-success-subtle text-success-emphasis';
      badge.textContent = 'Ativo';
      status.appendChild(badge);
      const acoes = document.createElement('td');
      acoes.className = 'text-center';
      acoes.append(
        buildButton('btn-outline-primary', 'btn-editar-curso', 'Editar curso', 'pencil', c),
        buildButton('btn-outline-secondary', 'btn-inativar-curso', 'Inativar curso', 'archive', c),
      );
      tr.append(nome, descricao, status, acoes);
      return tr;
    }

    function buildInactiveRow(c) {
      const tr = document.createElement('tr');
      tr.dataset.id = c.id;
      const nome = document.createElement('td');
      nome.className = 'ps-3 fw-semibold';
      nome.textContent = c.nome;
      const descricao = document.createElement('td');
      descricao.className = 'text-muted small';
      descricao.textContent = c.descricao || '—';
      const status = document.createElement('td');
      status.className = 'text-center';
      const badge = document.createElement('span');
      badge.className = 'badge bg-secondary-subtle text-secondary-emphasis';
      badge.textContent = 'Inativo';
      status.appendChild(badge);
      const acoes = document.createElement('td');
      acoes.className = 'text-center';
      acoes.appendChild(
        buildButton('btn-outline-success', 'btn-reativar-curso', 'Reativar curso', 'arrow-counterclockwise', c),
      );
      tr.append(nome, descricao, status, acoes);
      return tr;
    }

    function buildButton(style, action, title, icon, curso) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `btn btn-sm ${style} border-0 ${action}`;
      button.title = title;
      button.dataset.id = curso.id;
      button.dataset.nome = curso.nome;
      if (action === 'btn-editar-curso') {
        button.dataset.desc = curso.descricao || '';
      }
      const iconElement = document.createElement('i');
      iconElement.className = `bi bi-${icon}`;
      button.appendChild(iconElement);
      return button;
    }

    function removeVazio() {
      document.getElementById('cursoVazio')?.remove();
    }

    async function carregarCursos() {
      try {
        const [ativosResponse, inativosResponse] = await Promise.all([
          fetch('/cursos', { headers: { Accept: 'application/json' } }),
          fetch(URL_INATIVOS, { headers: { Accept: 'application/json' } }),
        ]);
        const [cursos, cursosInativos] = await Promise.all([
          readJsonResponse(ativosResponse),
          readJsonResponse(inativosResponse),
        ]);
        tbody.replaceChildren();
        if (!cursos.length) {
          tbody.innerHTML = `<tr id="cursoVazio">
            <td colspan="4" class="text-center text-muted py-4">
              <i class="bi bi-mortarboard d-block mb-2 opacity-25 fs-3"></i>
              Nenhum curso ativo para esta unidade.
            </td></tr>`;
        } else {
          cursos.forEach(curso => tbody.appendChild(buildRow(curso)));
        }
        if (tbodyInativos) {
          tbodyInativos.replaceChildren();
          if (!cursosInativos.length) {
            tbodyInativos.innerHTML = `<tr id="cursosInativosVazio">
              <td colspan="4" class="text-center text-muted py-3">Nenhum curso inativo.</td>
            </tr>`;
          } else {
            cursosInativos.forEach(curso => tbodyInativos.appendChild(buildInactiveRow(curso)));
          }
        }
      } catch (error) {
        console.warn('[planejamento] Não foi possível atualizar a lista de cursos.', error);
        showMsg(error.message || 'Não foi possível carregar os cursos.');
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
            }),
          });
          const data = await readJsonResponse(res);
          removeVazio();
          tbody.appendChild(buildRow(data));
          sincronizarSelects(data);
          nomeInput.value = '';
          descInput.value = '';
          showMsg('Curso adicionado!', 'success');
        } catch (error) {
          showMsg(error.message || 'Erro ao adicionar.');
        }
      });
    }

    /* ── Editar / Inativar (delegação) ── */
    tbody.addEventListener('click', async e => {
      const btnEd = e.target.closest('.btn-editar-curso');
      if (btnEd) {
        editId.value    = btnEd.dataset.id;
        editNome.value  = btnEd.dataset.nome;
        editNome.dataset.nomeOriginal = btnEd.dataset.nome;
        editDesc.value  = btnEd.dataset.desc;
        painelEdit.classList.remove('d-none');
        editNome.focus();
        return;
      }

      const btnInativar = e.target.closest('.btn-inativar-curso');
      if (!btnInativar) return;

      if (!confirm(
        `Inativar o curso "${btnInativar.dataset.nome}"?\n\n` +
        'Ele deixará de aparecer para novos planejamentos e turmas. ' +
        'Os temas e o histórico existente serão preservados.'
      )) return;

      try {
        const response = await fetch(URL_INATIVAR(btnInativar.dataset.id), {
          method: 'POST',
          headers: csrfHeaders(),
        });
        const data = await readJsonResponse(response);
        const row = tbody.querySelector(`tr[data-id="${btnInativar.dataset.id}"]`);
        row?.remove();
        tbodyInativos?.appendChild(buildInactiveRow({
          id: btnInativar.dataset.id,
          nome: btnInativar.dataset.nome,
          descricao: row?.children[1]?.textContent === '—' ? '' : row?.children[1]?.textContent || '',
        }));
        sincronizarSelects({ id: btnInativar.dataset.id }, true);
        if (!tbody.querySelector('tr[data-id]')) {
          tbody.innerHTML = `<tr id="cursoVazio">
            <td colspan="4" class="text-center text-muted py-4">
              <i class="bi bi-mortarboard d-block mb-2 opacity-25 fs-3"></i>
              Nenhum curso ativo para esta unidade.
            </td></tr>`;
        }
        document.getElementById('cursosInativosVazio')?.remove();
        showMsg(data.message || 'Curso inativado. Temas e histórico preservados.', 'success');
      } catch (error) {
        showMsg(error.message || 'Erro ao inativar curso.');
      }
    });

    tbodyInativos?.addEventListener('click', async e => {
      const btnReativar = e.target.closest('.btn-reativar-curso');
      if (!btnReativar) return;
      if (!confirm(`Reativar o curso "${btnReativar.dataset.nome}" e disponibilizá-lo para novos planejamentos e turmas?`)) return;

      try {
        const response = await fetch(URL_REATIVAR(btnReativar.dataset.id), {
          method: 'POST',
          headers: csrfHeaders(),
        });
        const curso = await readJsonResponse(response);
        btnReativar.closest('tr')?.remove();
        document.getElementById('cursosInativosVazio')?.remove();
        removeVazio();
        tbody.appendChild(buildRow(curso));
        sincronizarSelects(curso);
        if (!tbodyInativos.querySelector('tr[data-id]')) {
          tbodyInativos.innerHTML = `<tr id="cursosInativosVazio">
            <td colspan="4" class="text-center text-muted py-3">Nenhum curso inativo.</td>
          </tr>`;
        }
        showMsg('Curso reativado. Os temas preservados voltaram a ficar disponíveis.', 'success');
      } catch (error) {
        showMsg(error.message || 'Erro ao reativar curso.');
      }
    });

    /* ── Salvar edição ── */
    if (btnSalvarEd) {
      btnSalvarEd.addEventListener('click', async () => {
        const nome = editNome.value.trim();
        if (!nome) { showMsg('Nome obrigatório.'); return; }
        if (
          nome !== editNome.dataset.nomeOriginal &&
          !confirm(
            'Alterar o nome do curso atualizará sua exibição em todas as turmas vinculadas, ' +
            'inclusive nas de períodos encerrados e em futuras emissões de certificados. Deseja continuar?'
          )
        ) return;

        try {
          const res = await fetch(URL_EDITAR(editId.value), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
            body: JSON.stringify({
              nome,
              descricao: editDesc.value.trim(),
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
