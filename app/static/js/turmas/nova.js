// static/js/turmas/nova.js
// Mapa de dias e cálculo de C.H. estimativa vivem no módulo compartilhado
// grade_horario.js (H4). A tela de nova turma atual só coleta nome/período —
// a agenda nasce na oferta inicial (Cursos da Turma) — então o componente
// abaixo é defensivo: liga-se apenas se algum campo de agenda existir.
(function () {
    const periodosDatas = window.periodosDatas || {};
    const periodoSelect = document.querySelector('select[name="periodo_letivo_id"]');

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

    /**
     * Datas efetivas do curso: personalizadas (toggle ligado) ou as do
     * período letivo selecionado — [inicio, fim] em "YYYY-MM-DD" ou null.
     */
    function datasAtual() {
        if (toggleDatas && toggleDatas.checked && inputInicio && inputFim) {
            return [inputInicio.value || null, inputFim.value || null];
        }
        const periodoId = periodoSelect ? periodoSelect.value : null;
        if (periodoId && periodosDatas[periodoId]) {
            return [periodosDatas[periodoId].inicio, periodosDatas[periodoId].fim];
        }
        return [null, null];
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
        recalculaCH();
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
        recalculaCH();
    }

    // C.H. estimativa: delegada ao módulo compartilhado (H4). Sem campos de
    // agenda na tela, initGrade é no-op e recalculaCH não faz nada.
    let grade = null;
    function recalculaCH() {
        if (grade) grade.recalculaCH();
    }

    const form = document.querySelector('form');
    if (window.GradeHorario && form) {
        grade = GradeHorario.initGrade(form, { getDatas: datasAtual });
    }

    if (periodoSelect) {
        periodoSelect.addEventListener('change', () => {
            atualizarPeriodoInfo();
        });
        atualizarPeriodoInfo();
    }

    if (toggleDatas) {
        toggleDatas.addEventListener('change', toggleDatasVisivel);
    }
})();
