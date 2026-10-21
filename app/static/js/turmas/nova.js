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

    function formatarData(isoStr) {
        if (!isoStr) return '—';
        const [y, m, d] = isoStr.split('-');
        return `${d}/${m}/${y}`;
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
})();
