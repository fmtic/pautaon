// static/js/periodos/form.js
(function() {
    'use strict';

    const form = document.getElementById('periodoForm');
    const checks = document.querySelectorAll('.centro-custo-check');
    const msgValidacao = document.getElementById('cc_validation_msg');

    function validarCentros() {
        if (!checks.length) return true; // sem checkboxes, não valida
        const algumMarcado = Array.from(checks).some(c => c.checked);
        if (msgValidacao) msgValidacao.style.display = algumMarcado ? 'none' : 'block';
        return algumMarcado;
    }

    if (form && checks.length > 0) {
        form.addEventListener('submit', function(e) {
            if (!validarCentros()) {
                e.preventDefault();
            }
        });

        checks.forEach(c => c.addEventListener('change', () => {
            if (msgValidacao) {
                const algumMarcado = Array.from(checks).some(cb => cb.checked);
                msgValidacao.style.display = algumMarcado ? 'none' : 'block';
            }
        }));
    }
})();