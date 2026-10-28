/**
 * frequencia.js — navegação por turma/data via GET; submit de conceitos via POST.
 * O beforeunload foi removido pois bloqueava o submit do form.
 *
 * V2: com catálogo de valores ativo na unidade (`data-valor-obrigatorio="1"` no
 * form), o select de Valor/Postura fica `required` quando o conceito é A–D e o
 * submit é bloqueado com destaque enquanto houver pendência. F, J e "sem
 * conceito" desabilitam o select e nunca exigem o valor — a mesma regra (e a
 * mesma exceção) do servidor, sem duplicar validação além do necessário.
 *
 * As funções puras são exportadas para `tests/test_valor_obrigatorio_ui.py`
 * quando o arquivo roda em node; o DOM só é tocado no navegador.
 */

const CONCEITOS_PRESENCA = ['A', 'B', 'C', 'D'];

/** A–D exigem o Valor do Esportista; F, J e "sem conceito" não. */
function exigeValorEsportista(conceito) {
    return CONCEITOS_PRESENCA.includes(conceito);
}

/**
 * Há pendência de cliente? Repete a exceção do servidor: só vale com catálogo
 * ativo na unidade da turma.
 */
function valorEsportistaPendente({ conceito, valorId, catalogoAtivo }) {
    return Boolean(catalogoAtivo) && exigeValorEsportista(conceito) && !valorId;
}

function formExigeValor() {
    return Boolean(document.querySelector('form[data-valor-obrigatorio="1"]'));
}

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

/** Marca/desmarca o destaque de erro no select do aluno. */
function marcarPendencia(selectPostura, pendente) {
    if (!selectPostura) return;
    selectPostura.classList.toggle('is-invalid', Boolean(pendente));
}

function mostrarAvisoPendencia(quantidade) {
    const aviso = document.getElementById('aviso-valor-pendente');
    const texto = document.getElementById('aviso-valor-pendente-texto');
    if (!aviso || !texto) return;
    const plural = quantidade === 1 ? 'aluno' : 'alunos';
    texto.textContent =
        `Selecione o Valor/Postura do Esportista de ${quantidade} ${plural} `
        + 'com presença (A–D) antes de salvar.';
    aviso.classList.remove('d-none');
}

function esconderAvisoPendencia() {
    const aviso = document.getElementById('aviso-valor-pendente');
    if (aviso) aviso.classList.add('d-none');
}

/** Estado inicial do select de valor conforme o conceito marcado. */
function tratarConceitoAluno(alunoId, conceito) {
    const selectPostura = document.getElementById('postura_' + alunoId);
    if (!selectPostura) return;

    if (exigeValorEsportista(conceito)) {
        selectPostura.removeAttribute('disabled');
        if (formExigeValor()) selectPostura.setAttribute('required', 'required');
    } else {
        selectPostura.value = '';
        selectPostura.setAttribute('disabled', 'true');
        selectPostura.removeAttribute('required');
        marcarPendencia(selectPostura, false);
    }
}

/** Selects pendentes do form (A–D sem valor), já com o destaque aplicado. */
function validarPendencias(form) {
    const pendentes = [];
    form.querySelectorAll('select[id^="postura_"]').forEach(selectPostura => {
        const alunoId = selectPostura.id.slice('postura_'.length);
        const radio = form.querySelector(`input[name="aluno_${alunoId}"]:checked`);
        const conceito = radio ? radio.value : '';
        const pendente = valorEsportistaPendente({
            conceito,
            valorId: selectPostura.value,
            catalogoAtivo: true,
        });
        marcarPendencia(selectPostura, pendente);
        if (pendente) pendentes.push(selectPostura);
    });
    return pendentes;
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

        // A1/V2: estado inicial do select de Valor/Postura. O servidor já
        // renderiza `disabled`/`required` conforme o conceito salvo; repetir
        // aqui cobre o radio restaurado pelo navegador (voltar/recarregar).
        document.querySelectorAll('input.btn-check[name^="aluno_"]').forEach(radio => {
            if (!radio.checked) return;
            tratarConceitoAluno(radio.name.slice('aluno_'.length), radio.value);
        });

        // Limpa o destaque assim que o professor escolhe o valor.
        document.querySelectorAll('select[id^="postura_"]').forEach(selectPostura => {
            selectPostura.addEventListener('change', function () {
                marcarPendencia(this, false);
                const form = this.closest('form');
                if (form && !validarPendencias(form).length) esconderAvisoPendencia();
            });
        });

        const formPauta = document.querySelector('form[data-valor-obrigatorio="1"]');
        if (!formPauta) return;

        // Fallback do submit (a validação nativa já bloqueia antes disto).
        formPauta.addEventListener('submit', function (event) {
            const pendentes = validarPendencias(formPauta);
            if (!pendentes.length) {
                esconderAvisoPendencia();
                return;
            }
            event.preventDefault();
            mostrarAvisoPendencia(pendentes.length);
            pendentes[0].focus();
        });

        // `required` nativo: o evento `submit` nem chega a disparar.
        formPauta.addEventListener('invalid', function (event) {
            const alvo = event.target;
            if (!alvo || !alvo.id || !alvo.id.startsWith('postura_')) return;
            marcarPendencia(alvo, true);
            mostrarAvisoPendencia(validarPendencias(formPauta).length || 1);
        }, true);
    });
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CONCEITOS_PRESENCA,
        exigeValorEsportista,
        valorEsportistaPendente,
    };
}
