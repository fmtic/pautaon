/**
 * frequencia.js — Navegação por turma/data via GET; submit de conceitos via POST.
 * O beforeunload foi removido pois bloqueava o submit do form.
 */

function atualizarUrl() {
    const selectTurma = document.getElementById('select-turma');
    const selectData  = document.getElementById('select-data');
    const selectCurso = document.getElementById('select-turma-curso');
    if (!selectTurma) return;

    const params = new URLSearchParams();
    if (selectTurma.value) params.append('turma_id', selectTurma.value);
    if (selectData && selectData.value) params.append('data', selectData.value);
    // Onda 4 (D2): oferta escolhida na querystring; a data selecionada é
    // preservada porque o value do select-data entra sempre na URL.
    if (selectCurso && selectCurso.value) params.append('turma_curso', selectCurso.value);

    window.location.href = window.location.pathname + '?' + params.toString();
}

document.addEventListener('DOMContentLoaded', function () {
    // Turma, oferta e data disparam navegação GET
    ['select-turma', 'select-data', 'select-turma-curso'].forEach(id => {
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

    // A1: estado inicial do select de Valor/Postura. O servidor já renderiza
    // `disabled` conforme o conceito salvo; repetir aqui cobre o radio
    // restaurado pelo navegador (voltar pelo histórico / recarregar).
    document.querySelectorAll('input.btn-check[name^="aluno_"]').forEach(radio => {
        if (!radio.checked) return;
        tratarConceitoAluno(radio.name.slice('aluno_'.length), radio.value);
    });
});

/**
 * A1 — habilita o select de Valor/Postura só com conceito A/B/C/D.
 *
 * Ao desabilitar o valor é limpo: um select desabilitado não é enviado no
 * POST e o servidor grava NULL para F/J (o contrato do lançamento).
 */
function tratarConceitoAluno(alunoId, conceito) {
    const selectPostura = document.getElementById('postura_' + alunoId);
    if (!selectPostura) return;

    if (['A', 'B', 'C', 'D'].includes(conceito)) {
        selectPostura.removeAttribute('disabled');
    } else {
        selectPostura.value = '';
        selectPostura.setAttribute('disabled', 'true');
    }
}
