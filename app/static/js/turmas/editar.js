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

    function handleSubmit(event) {
        if (!temLancamentos || !form || !originalDias || !originalInicio || !originalFim || !limparInput) {
            return;
        }

        const novoDias = obterDiasSelecionados();
        const novoInicio = document.querySelector('input[name="data_inicio"]').value || '';
        const novoFim = document.querySelector('input[name="data_fim"]').value || '';

        const diasMudaram = novoDias !== originalDias.value;
        const inicioMudou = novoInicio !== originalInicio.value;
        const fimMudou = novoFim !== originalFim.value;

        if (diasMudaram || inicioMudou || fimMudou) {
            const confirmMsg =
                'Você alterou os dias ou as datas da turma.\n' +
                'Os lançamentos existentes de presença/falta serão apagados e precisarão ser refeitos.\n' +
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

    if (form) {
        form.addEventListener('submit', handleSubmit);
    }
})();