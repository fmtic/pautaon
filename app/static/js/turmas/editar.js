// static/js/turmas/editar.js
(function() {
    const periodosCentros = window.periodosCentrosEdit || {};
    const periodoSelect = document.querySelector('select[name="periodo_letivo_id"]');
    const centroSelect = document.getElementById('centro_custo_select');
    const centroHelp = document.getElementById('centro_edit_help');

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

    if (periodoSelect) {
        periodoSelect.addEventListener('change', atualizarCentros);
        atualizarCentros();
    }
})();