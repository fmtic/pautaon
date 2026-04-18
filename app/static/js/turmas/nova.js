// static/js/turmas/nova.js
(function() {
    const periodosCentros = window.periodosCentros || {};
    const periodoSelect = document.querySelector('select[name="periodo_letivo_id"]');
    const centroSelect = document.getElementById('centro_custo_select');
    const centroHelp = document.getElementById('centro_custo_help');

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

    if (periodoSelect) {
        periodoSelect.addEventListener('change', atualizarCentros);
        atualizarCentros();
    }
})();