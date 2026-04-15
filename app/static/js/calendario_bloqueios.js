(function () {
    'use strict';

    console.log('%c[Calendário] Script carregado v2.1', 'color: green; font-weight: bold');

    const TIPOS = {
        FERIADO: { label: 'Feriado', cor: '#dc3545', icone: 'F' },
        ATIVIDADE_PEDAGOGICA: { label: 'At. Pedagógica', cor: '#0d6efd', icone: 'A' },
        REUNIAO_PAIS: { label: 'Reunião de Pais', cor: '#6f42c1', icone: 'R' },
        ATIVIDADE_INTERNA: { label: 'At. Interna', cor: '#fd7e14', icone: 'I' },
        MANUTENCAO: { label: 'Manutenção', cor: '#6c757d', icone: 'M' },
    };

    let periodoId = null;
    let diasData = {};
    let diaFocoDate = null;
    let periodoInicio = null;
    let periodoFim = null;

    const periodoSel = document.getElementById('calPeriodoSelect');
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
    const btnExportar = document.getElementById('btnExportarCal');
    const calStatus = document.getElementById('calStatus');

    const DIAS_SEMANA = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    const MESES_PT = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
    const hoje = new Date().toISOString().slice(0, 10);

    // ==================== SELECIONAR PERÍODO ====================
    periodoSel.addEventListener('change', async function () {
        periodoId = this.value;
        diasData = {};
        panelDia.classList.add('d-none');

        if (!periodoId) {
            resetCalendar();
            return;
        }

        const opt = this.selectedOptions[0];
        periodoInicio = opt.dataset.inicio;
        periodoFim = opt.dataset.fim;

        calGrade.innerHTML = `<div class="text-center py-5"><div class="spinner-border text-primary"></div><p class="mt-3">Carregando...</p></div>`;

        try {
            const res = await fetch(`/planejamento/calendario/${periodoId}`);
            const lista = await res.json();
            lista.forEach(d => diasData[d.data] = { tipo: d.tipo, descricao: d.descricao || '' });

            renderCalendar();
            btnSalvar.disabled = false;
            if (btnExportar) {
                btnExportar.href = `/planejamento/calendario/${periodoId}/exportar`;
                btnExportar.classList.remove('d-none');
            }
        } catch (e) {
            console.error(e);
            calGrade.innerHTML = `<div class="alert alert-danger m-3">Erro ao carregar calendário</div>`;
        }
    });

    function resetCalendar() {
        calGrade.innerHTML = `<div class="text-center text-muted py-5">
            <i class="bi bi-calendar3 fs-1 opacity-25"></i>
            <p>Selecione um período letivo...</p>
        </div>`;
        btnSalvar.disabled = true;
        if (btnExportar) btnExportar.classList.add('d-none');
    }

    // ==================== RENDER (RESPEITANDO PERÍODO) ====================
    function renderCalendar() {
        calGrade.innerHTML = '';
        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:1.2rem;';

        if (periodoInicio && periodoFim) {
            let anoI = parseInt(periodoInicio.substring(0, 4));
            let mesI = parseInt(periodoInicio.substring(5, 7));
            let anoF = parseInt(periodoFim.substring(0, 4));
            let mesF = parseInt(periodoFim.substring(5, 7));

            let ano = anoI, mes = mesI;
            while (ano < anoF || (ano === anoF && mes <= mesF)) {
                wrapper.appendChild(buildMonth(ano, mes));
                mes++;
                if (mes > 12) { mes = 1; ano++; }
            }
        } else {
            const ano = new Date().getFullYear();
            for (let m = 1; m <= 12; m++) wrapper.appendChild(buildMonth(ano, m));
        }

        calGrade.appendChild(wrapper);
    }

    function buildMonth(year, month) {
        // ... (mesmo código anterior, mantido limpo)
        const container = document.createElement('div');
        container.className = 'cal-month';

        const title = document.createElement('div');
        title.className = 'cal-month-title';
        title.textContent = `${MESES_PT[month - 1]} / ${year}`;
        container.appendChild(title);

        const header = document.createElement('div');
        header.className = 'cal-week-header';
        DIAS_SEMANA.forEach(d => {
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
            const blank = document.createElement('div');
            blank.className = 'cal-day empty';
            grid.appendChild(blank);
        }

        for (let d = 1; d <= daysInMonth; d++) {
            const ds = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const cell = document.createElement('div');
            cell.className = `cal-day ${new Date(year, month - 1, d).getDay() >= 5 ? 'weekend' : ''}`;
            cell.dataset.date = ds;

            const num = document.createElement('div');
            num.className = 'cal-day-num';
            num.textContent = d;
            cell.appendChild(num);

            if (diasData[ds]) paintCell(cell, ds);

            cell.addEventListener('click', () => onDiaClick(ds, cell));
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
        cell.appendChild(badge);
    }

    function onDiaClick(ds, cell) {
        diaFocoDate = ds;

        // Correção de timezone: força data local
        const [ano, mes, dia] = ds.split('-').map(Number);
        const dataLocal = new Date(ano, mes - 1, dia);   // mês - 1 porque JS conta de 0

        diaLabel.textContent = dataLocal.toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: 'long',
            year: 'numeric'
        });

        diaWeekday.textContent = DIAS_SEMANA[dataLocal.getDay()];
        diaTipoSel.value = diasData[ds]?.tipo || 'FERIADO';
        diaDescInput.value = diasData[ds]?.descricao || '';

        panelDia.classList.remove('d-none');
        console.log('📌 Painel aberto para data:', ds, '→ Exibido:', diaLabel.textContent);
    }

    // ==================== BOTÕES ====================
    btnConfirmar.addEventListener('click', () => {
        if (!diaFocoDate) return;
        diasData[diaFocoDate] = { tipo: diaTipoSel.value, descricao: diaDescInput.value.trim() };
        const cell = calGrade.querySelector(`[data-date="${diaFocoDate}"]`);
        if (cell) paintCell(cell, diaFocoDate);
        panelDia.classList.add('d-none');
    });

    btnRemover.addEventListener('click', () => {
        if (!diaFocoDate) return;
        delete diasData[diaFocoDate];
        const cell = calGrade.querySelector(`[data-date="${diaFocoDate}"]`);
        if (cell) {
            cell.classList.remove('selecionado');
            cell.style.removeProperty('--tipo-cor');
            cell.querySelectorAll('.cal-day-badge').forEach(b => b.remove());
        }
        panelDia.classList.add('d-none');
    });

    btnLimpar.addEventListener('click', () => {
        if (!confirm('Limpar todos os dias marcados?')) return;
        diasData = {};
        calGrade.querySelectorAll('.cal-day').forEach(c => {
            c.classList.remove('selecionado');
            c.style.removeProperty('--tipo-cor');
            c.querySelectorAll('.cal-day-badge').forEach(b => b.remove());
        });
        panelDia.classList.add('d-none');
    });

    btnSalvar.addEventListener('click', async () => {
        if (!periodoId) return;
        const dias = Object.entries(diasData).map(([data, v]) => ({
            data, tipo: v.tipo, descricao: v.descricao || ''
        }));

        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
        const payload = { periodo_id: parseInt(periodoId), dias };
        console.log('[CAL] Enviando payload:', JSON.stringify(payload));

        calStatus.textContent = 'Salvando...';
        try {
            const res = await fetch('/planejamento/calendario/salvar', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errorDetail = await res.text();
                console.error('[CAL] Erro do servidor:', errorDetail);
                calStatus.textContent = 'Erro ao salvar';
                return;
            }

            const result = await res.json();
            calStatus.textContent = result.success ? '✔ Salvo com sucesso!' : `Erro: ${result.message}`;
            setTimeout(() => calStatus.textContent = '', 3000);
        } catch (e) {
            console.error('[CAL] Falha de conexão:', e);
            calStatus.textContent = 'Falha de conexão';
        }
    });

    // Reset ao abrir modal
    document.getElementById('modalCalendario').addEventListener('show.bs.modal', () => {
        resetCalendar();
        panelDia.classList.add('d-none');
    });

})();