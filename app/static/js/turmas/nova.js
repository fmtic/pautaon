// static/js/turmas/nova.js
(function() {
    const periodosCentros = window.periodosCentros || {};
    const periodosDatas = window.periodosDatas || {};
    const periodoSelect = document.querySelector('select[name="periodo_letivo_id"]');
    const centroSelect = document.getElementById('centro_custo_select');
    const centroHelp = document.getElementById('centro_custo_help');

    // Toggle de datas personalizadas do curso.
    const toggleDatas = document.getElementById('toggle_datas_curso');
    const datasCustomArea = document.getElementById('datas_custom_area');
    const periodoInfo = document.getElementById('datas_periodo_info');
    const labelInicio = document.getElementById('periodo_data_inicio');
    const labelFim = document.getElementById('periodo_data_fim');
    const inputInicio = document.getElementById('data_inicio_custom');
    const inputFim = document.getElementById('data_fim_custom');

    // Elementos de exibição de carga horária.
    const inputHoraInicio = document.getElementById('hora_inicio');
    const inputHoraFim = document.getElementById('hora_fim');
    const chAulaDisplay = document.getElementById('ch_aula_display');
    const chTotalDisplay = document.getElementById('ch_total_display');

    function formatarData(isoStr) {
        if (!isoStr) return '—';
        const [y, m, d] = isoStr.split('-');
        return `${d}/${m}/${y}`;
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
     *
     * @param {string} dataInicio - "YYYY-MM-DD"
     * @param {string} dataFim    - "YYYY-MM-DD"
     * @param {number[]} diasPermitidos - índices JS (0=Dom, 1=Seg, ..., 6=Sáb)
     * @returns {number}
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
     * Lê os valores atuais dos campos de hora, dias e datas do formulário.
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

        // Datas: usa datas personalizadas se o toggle estiver ativo, senão usa o período.
        let dataInicio = null;
        let dataFim = null;
        const periodoId = periodoSelect ? periodoSelect.value : null;
        if (toggleDatas && toggleDatas.checked) {
            dataInicio = inputInicio ? inputInicio.value : null;
            dataFim = inputFim ? inputFim.value : null;
        } else if (periodoId && periodosDatas[periodoId]) {
            dataInicio = periodosDatas[periodoId].inicio;
            dataFim = periodosDatas[periodoId].fim;
        }

        // C.H. Total.
        if (chAula && dataInicio && dataFim && diasPermitidos.length > 0) {
            const dias = contarDiasAula(dataInicio, dataFim, diasPermitidos);
            chTotalDisplay.textContent = dias > 0 ? formatarCH(chAula * dias) : '—';
        } else {
            chTotalDisplay.textContent = '—';
        }
    }

    // Exibe o intervalo do período selecionado e restringe os inputs manuais
    // para que nenhuma data caia fora dos limites do período letivo.
    function atualizarPeriodoInfo() {
        const periodoId = periodoSelect ? periodoSelect.value : null;
        const datas = periodosDatas[periodoId];
        if (datas) {
            labelInicio.textContent = formatarData(datas.inicio);
            labelFim.textContent = formatarData(datas.fim);
            if (inputInicio) {
                inputInicio.min = datas.inicio;
                inputInicio.max = datas.fim;
            }
            if (inputFim) {
                inputFim.min = datas.inicio;
                inputFim.max = datas.fim;
            }
        } else {
            labelInicio.textContent = '—';
            labelFim.textContent = '—';
            if (inputInicio) { inputInicio.removeAttribute('min'); inputInicio.removeAttribute('max'); }
            if (inputFim) { inputFim.removeAttribute('min'); inputFim.removeAttribute('max'); }
        }
        recalcularCH();
    }

    function atualizarCentros() {
        const periodoId = periodoSelect ? periodoSelect.value : null;
        const centros = (periodoId && periodosCentros[periodoId]) ? periodosCentros[periodoId] : [];
        centroSelect.innerHTML = '';
        if (centros.length) {
            centroSelect.disabled = false;
            centroSelect.innerHTML = '<option value="">-- Selecione um Centro de Custo --</option>';
            centros.forEach(centro => {
                const opt = document.createElement('option');
                opt.value = centro;
                opt.textContent = centro;
                centroSelect.appendChild(opt);
            });
            if (centroHelp) centroHelp.textContent = 'Selecione o centro de custo disponível para o período escolhido.';
        } else {
            centroSelect.disabled = true;
            centroSelect.innerHTML = '<option value="">-- Nenhum centro disponível --</option>';
            if (centroHelp) centroHelp.textContent = 'Selecione um período letivo com centros de custo definidos.';
        }
    }

    // Mostra os inputs manuais apenas quando o toggle está marcado; caso
    // contrário, mantém o texto informativo com as datas do período.
    function toggleDatasVisivel() {
        if (!toggleDatas || !datasCustomArea || !periodoInfo) return;
        if (toggleDatas.checked) {
            datasCustomArea.classList.remove('d-none');
            periodoInfo.classList.add('d-none');
        } else {
            datasCustomArea.classList.add('d-none');
            periodoInfo.classList.remove('d-none');
            if (inputInicio) inputInicio.value = '';
            if (inputFim) inputFim.value = '';
        }
        recalcularCH();
    }

    if (periodoSelect) {
        periodoSelect.addEventListener('change', () => {
            atualizarCentros();
            atualizarPeriodoInfo();
        });
        atualizarCentros();
        atualizarPeriodoInfo();
    }

    if (toggleDatas) {
        toggleDatas.addEventListener('change', toggleDatasVisivel);
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
})();
