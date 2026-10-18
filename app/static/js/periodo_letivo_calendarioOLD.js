// Informa os dias em que não haverá aula, seja por feriado, reunião de pais,
// atividade pedagógica ou interna, manutenção, etc.

(function() {
  'use strict';

  // Obtém a configuração injetada pelo template
  const config = window.calendarioConfig || {};
  const READONLY = config.readonly === true;
  const PERIODO_ID = config.periodoId;
  const PERIODO_INICIO = config.dataInicio;
  const PERIODO_FIM = config.dataFim;
  const DIAS_INICIAIS = config.dias || [];
  const TURMAS = config.turmas || [];
  const EXCECOES_INICIAIS = config.excecoes || {};

  const TIPOS = {
    FERIADO: { label: 'Feriado', cor: '#dc3545', icone: 'F' },
    ATIVIDADE_PEDAGOGICA: { label: 'At. Pedagógica', cor: '#0d6efd', icone: 'A' },
    REUNIAO_PAIS: { label: 'Reunião de Pais', cor: '#6f42c1', icone: 'R' },
    ATIVIDADE_INTERNA: { label: 'At. Interna', cor: '#fd7e14', icone: 'I' },
    MANUTENCAO: { label: 'Manutenção', cor: '#6c757d', icone: 'M' },
  };

  const MESES_PT = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
  const DIAS_SEM = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

  // Estado local
  let diasData = {};
  let tipoAtivo = 'FERIADO';
  let diaFoco = null;
  let diasExcecoes = { ...EXCECOES_INICIAIS };

  // Elementos DOM
  const calGrade = document.getElementById('calGrade');
  const panelDia = document.getElementById('panelDia');
  const diaLabel = document.getElementById('diaLabel');
  const diaWeekday = document.getElementById('diaWeekday');
  const diaTipoSel = document.getElementById('diaTipoSel');
  const diaDescInput = document.getElementById('diaDescInput');
  const btnConfirmar = document.getElementById('btnConfirmarDia');
  const btnRemover = document.getElementById('btnRemoverDia');
  const btnSalvar = document.getElementById('btnSalvarCal');
  const btnLimpar = document.getElementById('btnLimparSel');
  const turmasExcecao = document.getElementById('turmasExcecao');
  const turmasExcecaoList = document.getElementById('turmasExcecaoList');
  const turmasExcecaoStatus = document.getElementById('turmasExcecaoStatus');
  const calStatus = document.getElementById('calStatus');
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';

  // Inicializa os dados com os dias recebidos do backend
  DIAS_INICIAIS.forEach(d => {
    diasData[d.data] = { tipo: d.tipo, descricao: d.descricao };
  });

  // ── Seletor de tipo ──
  document.querySelectorAll('.tipo-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tipo-btn').forEach(b => b.classList.remove('ativo'));
      btn.classList.add('ativo');
      tipoAtivo = btn.dataset.tipo;
    });
  });
  document.querySelector('.tipo-btn')?.classList.add('ativo');

  // ── Renderização do calendário ──
  function renderCalendar() {
    calGrade.innerHTML = '';
    const [anoI, mesI] = PERIODO_INICIO.split('-').map(Number);
    const [anoF, mesF] = PERIODO_FIM.split('-').map(Number);
    let ano = anoI, mes = mesI;
    while (ano < anoF || (ano === anoF && mes <= mesF)) {
      calGrade.appendChild(buildMonth(ano, mes));
      mes++;
      if (mes > 12) {
        mes = 1;
        ano++;
      }
    }
  }

  function shouldShowTurmasExcecao(ds) {
    return !!TURMAS.length && (!!diasData[ds] || (diasExcecoes[ds] && diasExcecoes[ds].length));
  }

  function renderTurmasExcecao(ds) {
    if (!turmasExcecao || !turmasExcecaoList) {
      return;
    }
    const selected = new Set((diasExcecoes[ds] || []).map(Number));
    turmasExcecaoList.innerHTML = '';

    if (!TURMAS.length) {
      turmasExcecaoList.innerHTML = '<div class="col-12 text-muted small">Nenhuma turma disponível para exceção neste período.</div>';
      turmasExcecao.classList.toggle('d-none', true);
      return;
    }

    TURMAS.forEach(turma => {
      const isChecked = selected.has(Number(turma.id));
      const item = document.createElement('div');
      item.className = 'col-12 col-md-6 col-lg-4';
      item.innerHTML = `
        <div class="form-check">
          <input class="form-check-input" type="checkbox" value="${turma.id}" id="turma-excecao-${turma.id}" ${isChecked ? 'checked' : ''}>
          <label class="form-check-label" for="turma-excecao-${turma.id}">${turma.nome}</label>
        </div>
      `;
      turmasExcecaoList.appendChild(item);
      const checkbox = item.querySelector('input[type="checkbox"]');
      checkbox?.addEventListener('change', updateTurmasExcecaoStatus);
    });

    turmasExcecao.classList.toggle('d-none', !shouldShowTurmasExcecao(ds));
    turmasExcecaoStatus.textContent = selected.size;
  }

  function getSelectedTurmas() {
    const checked = [];
    turmasExcecaoList.querySelectorAll('input[type="checkbox"]:checked').forEach(input => {
      const turmaId = Number(input.value);
      if (!Number.isNaN(turmaId)) {
        checked.push(turmaId);
      }
    });
    return checked;
  }

  function updateTurmasExcecaoStatus() {
    if (!turmasExcecaoStatus) {
      return;
    }
    turmasExcecaoStatus.textContent = getSelectedTurmas().length;
  }

  function buildMonth(year, month) {
    const container = document.createElement('div');
    container.className = 'cal-month';

    const title = document.createElement('div');
    title.className = 'cal-month-title';
    title.textContent = `${MESES_PT[month - 1]} / ${year}`;
    container.appendChild(title);

    const header = document.createElement('div');
    header.className = 'cal-week-header';
    DIAS_SEM.forEach(d => {
      const s = document.createElement('span');
      s.textContent = d;
      header.appendChild(s);
    });
    container.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'cal-days';

    const firstDay = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();

    for (let i = 0; i < firstDay; i++) {
      const b = document.createElement('div');
      b.className = 'cal-day empty';
      grid.appendChild(b);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const ds = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const wday = new Date(year, month - 1, d).getDay();
      const cell = document.createElement('div');
      // Corrigido: fim de semana são sábado (6) e domingo (0)
      cell.className = `cal-day${(wday === 0 || wday === 6) ? ' weekend' : ''}`;
      cell.dataset.date = ds;

      const num = document.createElement('div');
      num.className = 'cal-day-num';
      num.textContent = d;
      cell.appendChild(num);

      if (diasData[ds]) paintCell(cell, ds);

      if (!READONLY) cell.addEventListener('click', () => onDiaClick(ds, cell));
      grid.appendChild(cell);
    }
    container.appendChild(grid);
    return container;
  }

  function paintCell(cell, ds) {
    const info = diasData[ds];
    const tipo = TIPOS[info.tipo] || { cor: '#6c757d', icone: '?' };
    cell.style.setProperty('--tipo-cor', tipo.cor);
    cell.classList.add('selecionado');
    cell.querySelectorAll('.cal-day-badge').forEach(b => b.remove());
    const badge = document.createElement('div');
    badge.className = 'cal-day-badge';
    badge.style.background = tipo.cor;
    badge.textContent = tipo.icone;
    badge.title = info.descricao || tipo.label;
    cell.appendChild(badge);
  }

  function onDiaClick(ds, cell) {
    diaFoco = ds;
    const [ano, mes, dia] = ds.split('-').map(Number);
    const dataLocal = new Date(ano, mes - 1, dia);
    diaLabel.textContent = dataLocal.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' });
    diaWeekday.textContent = DIAS_SEM[dataLocal.getDay()];
    diaTipoSel.value = diasData[ds]?.tipo || tipoAtivo;
    diaDescInput.value = diasData[ds]?.descricao || '';
    renderTurmasExcecao(ds);
    panelDia.classList.remove('d-none');
  }

  // ── Função auxiliar para exibir mensagem no topo (flutuante) ──
  function showFloatingMessage(message, type = 'success') {
    const container = document.getElementById('alertContainer');
    if (!container) {
      // Fallback: usa o calStatus no rodapé
      if (calStatus) {
        calStatus.textContent = message;
        setTimeout(() => { if (calStatus) calStatus.textContent = ''; }, 3000);
      }
      return;
    }
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show small py-2 px-3 shadow`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
      ${message}
      <button type="button" class="btn-close btn-sm" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    container.appendChild(alertDiv);
    setTimeout(() => {
      alertDiv.classList.remove('show');
      setTimeout(() => alertDiv.remove(), 300);
    }, 4000);
  }

  // ── Eventos dos botões ──
  btnConfirmar?.addEventListener('click', () => {
    if (!diaFoco) return;
    diasData[diaFoco] = {
      tipo: diaTipoSel.value,
      descricao: diaDescInput.value.trim()
    };
    const selectedTurmas = getSelectedTurmas();
    if (selectedTurmas.length) {
      diasExcecoes[diaFoco] = selectedTurmas;
    } else {
      delete diasExcecoes[diaFoco];
    }
    const cell = calGrade.querySelector(`[data-date="${diaFoco}"]`);
    if (cell) paintCell(cell, diaFoco);
    panelDia.classList.add('d-none');
  });

  btnRemover?.addEventListener('click', () => {
    if (!diaFoco) return;
    delete diasData[diaFoco];
    delete diasExcecoes[diaFoco];
    const cell = calGrade.querySelector(`[data-date="${diaFoco}"]`);
    if (cell) {
      cell.classList.remove('selecionado');
      cell.style.removeProperty('--tipo-cor');
      cell.querySelectorAll('.cal-day-badge').forEach(b => b.remove());
    }
    panelDia.classList.add('d-none');
  });

  btnLimpar?.addEventListener('click', () => {
    if (!confirm('Limpar todos os dias marcados?')) return;
    diasData = {};
    diasExcecoes = {};
    calGrade.querySelectorAll('.cal-day').forEach(c => {
      c.classList.remove('selecionado');
      c.style.removeProperty('--tipo-cor');
      c.querySelectorAll('.cal-day-badge').forEach(b => b.remove());
    });
    panelDia.classList.add('d-none');
  });

  btnSalvar?.addEventListener('click', async () => {
    const dias = Object.entries(diasData).map(([data, v]) => ({
      data,
      tipo: v.tipo,
      descricao: v.descricao || ''
    }));
    showFloatingMessage('Salvando...', 'info');
    try {
      const res = await fetch('/planejamento/calendario/salvar', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ periodo_id: PERIODO_ID, dias, excecoes: diasExcecoes })
      });
      if (!res.ok) {
        showFloatingMessage('Erro ao salvar.', 'danger');
        return;
      }
      const data = await res.json();
      if (data.success) {
        showFloatingMessage('✔ Salvo com sucesso!', 'success');
      } else {
        showFloatingMessage(`Erro: ${data.message}`, 'danger');
      }
    } catch (e) {
      showFloatingMessage('Falha de conexão.', 'danger');
    }
  });

  renderCalendar();
})();