/**
 * frequencia.js — Navegação por turma/data via GET; submit de conceitos via POST.
 * O beforeunload foi removido pois bloqueava o submit do form.
 */

function atualizarUrl() {
    const selectTurma = document.getElementById('select-turma');
    const selectData  = document.getElementById('select-data');
    if (!selectTurma) return;

    const params = new URLSearchParams();
    if (selectTurma.value) params.append('turma_id', selectTurma.value);
    if (selectData && selectData.value) params.append('data', selectData.value);

    window.location.href = window.location.pathname + '?' + params.toString();
}

document.addEventListener('DOMContentLoaded', function () {
    // Turma e data disparam navegação GET
    ['select-turma', 'select-data'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', atualizarUrl);
    });

    // Sincroniza o input hidden com o valor atual do select de data
    const selectData = document.getElementById('select-data');
    const hiddenData = document.querySelector('input[name="data_hidden"]');
    if (selectData && hiddenData) {
        if (selectData.value) hiddenData.value = selectData.value;
        selectData.addEventListener('change', function () {
            hiddenData.value = this.value;
        });
    }
});
