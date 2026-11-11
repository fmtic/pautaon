/**
 * frequencia.js — navegação por turma/data via GET; submit de conceitos via POST.
 * O beforeunload foi removido pois bloqueava o submit do form.
 *
 * AJ16-B: os valores/posturas do esportista são da AULA (um conjunto único,
 * como os temas), não de cada aluno. Com catálogo ativo na unidade
 * (`data-valor-obrigatorio="1"` no form), o envio é bloqueado enquanto houver
 * ao menos um conceito A–D marcado e nenhum valor selecionado. F/J e "sem
 * conceito" não exigem valor — a mesma regra do servidor.
 *
 * As funções puras são exportadas para `tests/test_valor_obrigatorio_ui.py`
 * quando o arquivo roda em node; o DOM só é tocado no navegador.
 */

const CONCEITOS_PRESENCA = ['A', 'B', 'C', 'D'];

/** Algum conceito A–D entre os informados? */
function aulaTemPresenca(conceitos) {
    return Array.from(conceitos || []).some(
        conceito => CONCEITOS_PRESENCA.includes(conceito)
    );
}

/** Há pendência de cliente? Só vale com catálogo ativo na unidade da turma. */
function valorAulaPendente({ conceitos, valorIds, catalogoAtivo }) {
    return Boolean(catalogoAtivo)
        && aulaTemPresenca(conceitos)
        && (!valorIds || valorIds.length === 0);
}

/**
 * Radios de conceito dos alunos que podem ser lançados.
 * `:not(:disabled)` cobre tanto o aluno pos-entrada (desabilitado e sem `name`)
 * quanto o transferido/readonly; o seletor é a fonte ÚNICA usada pelo resumo e
 * pelos listeners deste arquivo.
 */
function radiosAlunoHabilitados(form) {
    return Array.from(
        form.querySelectorAll('input.btn-check[name^="aluno_"]:not(:disabled)')
    );
}

function conceitosMarcados(form) {
    return radiosAlunoHabilitados(form)
        .filter(radio => radio.checked)
        .map(radio => radio.value);
}

function valoresMarcados(form) {
    return Array.from(
        form.querySelectorAll('input[name="valor_ids"]:checked')
    ).map(input => input.value);
}

function marcarPendencia(grupo, pendente) {
    if (!grupo) return;
    grupo.classList.toggle('border-danger', Boolean(pendente));
}

function mostrarAvisoPendencia() {
    const aviso = document.getElementById('aviso-valor-pendente');
    const texto = document.getElementById('aviso-valor-pendente-texto');
    if (!aviso || !texto) return;
    texto.textContent =
        'Selecione ao menos um valor trabalhado na aula antes de salvar.';
    aviso.classList.remove('d-none');
}

function esconderAvisoPendencia() {
    const aviso = document.getElementById('aviso-valor-pendente');
    if (aviso) aviso.classList.add('d-none');
}

/** Grupo de valores pendente (A–D sem nenhum valor), já com o destaque. */
function validarPendencias(form) {
    const grupo = form.querySelector('#select-valor-aula');
    const pendente = valorAulaPendente({
        conceitos: conceitosMarcados(form),
        valorIds: valoresMarcados(form),
        catalogoAtivo: true,
    });
    marcarPendencia(grupo, pendente);
    return pendente ? [grupo] : [];
}

function atualizarUrl() {
    const selectTurma = document.getElementById('select-turma');
    const selectData = document.getElementById('select-data');
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

if (typeof document !== 'undefined') {
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

        const formPauta = document.querySelector('form[data-valor-obrigatorio="1"]');
        if (!formPauta) return;

        // Limpa o destaque assim que o professor marca um valor.
        formPauta.querySelectorAll('input[name="valor_ids"]').forEach(input => {
            input.addEventListener('change', function () {
                const grupo = formPauta.querySelector('#select-valor-aula');
                marcarPendencia(grupo, false);
                if (!validarPendencias(formPauta).length) esconderAvisoPendencia();
            });
        });

        // Reavalia ao trocar um conceito (o conjunto de A–D pode mudar).
        radiosAlunoHabilitados(formPauta).forEach(radio => {
            radio.addEventListener('change', function () {
                if (!validarPendencias(formPauta).length) esconderAvisoPendencia();
            });
        });

        formPauta.addEventListener('submit', function (event) {
            const pendentes = validarPendencias(formPauta);
            if (!pendentes.length) {
                esconderAvisoPendencia();
                return;
            }
            event.preventDefault();
            mostrarAvisoPendencia();
            pendentes[0].scrollIntoView({ block: 'center' });
        });
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CONCEITOS_PRESENCA,
        aulaTemPresenca,
        valorAulaPendente,
        radiosAlunoHabilitados,
        conceitosMarcados,
    };
}
