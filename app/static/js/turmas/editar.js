// static/js/turmas/editar.js
(function() {
    const periodosCentros = window.periodosCentrosEdit || {};
    const periodoSelect = document.querySelector('select[name="periodo_letivo_id"]');
    const centroSelect = document.getElementById('centro_custo_select');
    const centroHelp = document.getElementById('centro_edit_help');
    const form = document.querySelector('form');
    const originalDias = document.getElementById('original_dias_semana');
    const originalInicio = document.getElementById('original_data_inicio');
    const originalFim = document.getElementById('original_data_fim');
    const limparInput = document.getElementById('limpar_lancamentos');
    const temLancamentos = window.turmaTemLancamentos || false;

    // Elementos de exibição de carga horária.
    const inputHoraInicio = document.getElementById('hora_inicio');
    const inputHoraFim = document.getElementById('hora_fim');
    const chAulaDisplay = document.getElementById('ch_aula_display');
    const chTotalDisplay = document.getElementById('ch_total_display');
    const inputInicio = document.querySelector('input[name="data_inicio"]');
    const inputFim = document.querySelector('input[name="data_fim"]');

    function atualizarCentros() {
        const periodoId = periodoSelect ? periodoSelect.value : null;
        const centros = (periodoId && periodosCentros[periodoId]) ? periodosCentros[periodoId] : [];
        centroSelect.innerHTML = '';
        if (centros.length) {
            centroSelect.disabled = false;
            centros.forEach(centro => {
                const opt = document.createElement('option');
                opt.value = centro;
                opt.textContent = centro;
                centroSelect.appendChild(opt);
            });
            if (centroHelp) centroHelp.textContent = 'Centros do período selecionado.';
        } else {
            centroSelect.disabled = true;
            if (centroHelp) centroHelp.textContent = 'Nenhum centro de custo definido para o período selecionado.';
        }
    }

    function obterDiasSelecionados() {
        return Array.from(document.querySelectorAll('input[name="dias_semana"]:checked'))
            .map(el => el.value)
            .join(', ');
    }

    /**
     * Converte uma string de horário "HH:MM" em minutos totais.
     * Retorna null se o valor for inválido ou vazio.
     */
    function horaParaMinutos(horaStr) {
        if (!horaStr) return null;
        const partes = horaStr.split(':');
        if (partes.length < 2) return null;
        const h = parseInt(partes[0], 10);
        const m = parseInt(partes[1], 10);
        if (isNaN(h) || isNaN(m)) return null;
        return h * 60 + m;
    }

    /**
     * Formata minutos inteiros em string legível de carga horária.
     * Ex.: 60 → "1h" | 90 → "1h30min" | 0 → "—" | null → "—"
     */
    function formatarCH(minutos) {
        if (!minutos || minutos <= 0) return '—';
        const h = Math.floor(minutos / 60);
        const m = minutos % 60;
        if (m === 0) return `${h}h`;
        return `${h}h${String(m).padStart(2, '0')}min`;
    }

    /**
     * Conta quantos dias de aula existem entre dataInicio e dataFim (inclusive)
     * para os dias da semana selecionados. Não desconta dias bloqueados (estimativa).
     */
    function contarDiasAula(dataInicio, dataFim, diasPermitidos) {
        if (!dataInicio || !dataFim || diasPermitidos.length === 0) return 0;
        const inicio = new Date(dataInicio + 'T00:00:00');
        const fim = new Date(dataFim + 'T00:00:00');
        if (isNaN(inicio) || isNaN(fim) || fim < inicio) return 0;
        let count = 0;
        const atual = new Date(inicio);
        while (atual <= fim) {
            if (diasPermitidos.includes(atual.getDay())) count++;
            atual.setDate(atual.getDate() + 1);
        }
        return count;
    }

    /**
     * Mapeamento dos valores dos checkboxes (em português) para getDay() do JS.
     * JS: 0=Domingo, 1=Segunda, 2=Terça, 3=Quarta, 4=Quinta, 5=Sexta, 6=Sábado
     */
    const MAP_DIAS = {
        'Segunda': 1, 'Terça': 2, 'Quarta': 3,
        'Quinta': 4, 'Sexta': 5, 'Sábado': 6,
    };

    /**
     * Recalcula e exibe a C.H. por Aula e a C.H. Total Estimada.
     */
    function recalcularCH() {
        if (!chAulaDisplay || !chTotalDisplay) return;

        // C.H. por Aula.
        const minInicio = horaParaMinutos(inputHoraInicio ? inputHoraInicio.value : null);
        const minFim = horaParaMinutos(inputHoraFim ? inputHoraFim.value : null);
        const chAula = (minInicio !== null && minFim !== null && minFim > minInicio)
            ? minFim - minInicio
            : null;
        chAulaDisplay.textContent = formatarCH(chAula);

        // Dias efetivos.
        const diasCheckboxes = document.querySelectorAll('input[name="dias_semana"]:checked');
        const diasPermitidos = Array.from(diasCheckboxes).map(el => MAP_DIAS[el.value]).filter(d => d !== undefined);

        // Datas.
        const dataInicio = inputInicio ? inputInicio.value : null;
        const dataFim = inputFim ? inputFim.value : null;

        // C.H. Total.
        if (chAula && dataInicio && dataFim && diasPermitidos.length > 0) {
            const dias = contarDiasAula(dataInicio, dataFim, diasPermitidos);
            chTotalDisplay.textContent = dias > 0 ? formatarCH(chAula * dias) : '—';
        } else {
            chTotalDisplay.textContent = '—';
        }
    }

    function handleSubmit(event) {
        if (!temLancamentos || !form || !originalDias || !originalInicio || !originalFim || !limparInput) {
            return;
        }

        const novoDias = obterDiasSelecionados();
        const novoInicio = document.querySelector('input[name="data_inicio"]').value || '';
        const novoFim = document.querySelector('input[name="data_fim"]').value || '';
        const novoHoraInicio = inputHoraInicio ? inputHoraInicio.value : '';
        const novoHoraFim = inputHoraFim ? inputHoraFim.value : '';

        const diasMudaram = novoDias !== originalDias.value;
        const inicioMudou = novoInicio !== originalInicio.value;
        const fimMudou = novoFim !== originalFim.value;
        const horaInicioMudou = novoHoraInicio !== (inputHoraInicio ? inputHoraInicio.defaultValue : '');
        const horaFimMudou = novoHoraFim !== (inputHoraFim ? inputHoraFim.defaultValue : '');

        if (diasMudaram || inicioMudou || fimMudou || horaInicioMudou || horaFimMudou) {
            const confirmMsg =
                'Você alterou os dias, as datas ou o horário da turma.\n' +
                'Isso irá limpar os lançamentos existentes e recalcular a carga horária deste curso nesta turma.\n' +
                'Deseja continuar?';
            if (!confirm(confirmMsg)) {
                event.preventDefault();
                return;
            }
            limparInput.value = '1';
        }
    }

    if (periodoSelect) {
        periodoSelect.addEventListener('change', atualizarCentros);
        atualizarCentros();
    }

    // Recalcula C.H. ao mudar qualquer campo relevante.
    if (inputHoraInicio) inputHoraInicio.addEventListener('change', recalcularCH);
    if (inputHoraFim) inputHoraFim.addEventListener('change', recalcularCH);
    if (inputInicio) inputInicio.addEventListener('change', recalcularCH);
    if (inputFim) inputFim.addEventListener('change', recalcularCH);
    document.querySelectorAll('input[name="dias_semana"]').forEach(el => {
        el.addEventListener('change', recalcularCH);
    });

    // Cálculo inicial ao carregar a página.
    recalcularCH();

    if (form) {
        form.addEventListener('submit', handleSubmit);
    }
})();