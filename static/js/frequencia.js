/**
 * Atualiza a URL com os parâmetros de turma, data e tema selecionados
 */
function atualizarUrl() {
    if (dadosAlterados) {
        if (!confirm("Você tem alterações não salvas. Deseja realmente mudar de página?")) {
            return; // Cancela a mudança de URL
        }
    }
    // IDs devem ser idênticos aos definidos no seu HTML
    const selectTurma = document.getElementById('select-turma');
    const selectData = document.getElementById('select-data');
    const selectTema = document.getElementById('select-tema');

    if (!selectTurma) return;

    const turmaId = selectTurma.value;
    const data = selectData ? selectData.value : '';
    const temaId = selectTema ? selectTema.value : '';

    // Inicia a construção da query string
    let params = new URLSearchParams();

    if (turmaId) params.append('turma_id', turmaId);
    if (data) params.append('data', data);
    if (temaId) params.append('tema_id', temaId);

    // Redireciona mantendo a base da URL limpa
    window.location.href = window.location.pathname + '?' + params.toString();
}

// Adiciona os ouvintes de evento assim que o DOM carregar
document.addEventListener('DOMContentLoaded', function () {
    const ids = ['select-turma', 'select-data', 'select-tema'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('change', atualizarUrl);
        }
    });
});

// Opcional: Feedback visual ao clicar nos conceitos
document.querySelectorAll('.btn-check').forEach(input => {
    input.addEventListener('change', function () {
        console.log(`Conceito ${this.value} selecionado para o aluno.`);
    });
});

let dadosAlterados = false;

// 1. Monitora qualquer mudança em inputs, selects ou textareas
document.addEventListener('change', function (e) {
    if (e.target.closest('input, select, textarea')) {
        dadosAlterados = true;
    }
});

// 2. Monitora digitação no campo de observações (input não dispara 'change' até perder o foco)
const campoObs = document.getElementById('observacoes_aula');
if (campoObs) {
    campoObs.addEventListener('input', () => dadosAlterados = true);
}

// 3. Intercepta a saída da página
window.addEventListener('beforeunload', function (e) {
    if (dadosAlterados) {
        // Cancela o evento para mostrar o alerta padrão do navegador
        e.preventDefault();
        e.returnValue = ''; // Exigido por muitos navegadores
    }
});

// 4. IMPORTANTE: Libera a saída quando o professor clicar em "Salvar"
// Procure pelo ID ou classe do seu botão de salvar
const btnSalvar = document.querySelector('.btn-success');
if (btnSalvar) {
    btnSalvar.addEventListener('click', () => {
        dadosAlterados = false; // Desativa o alerta para permitir o envio
    });
}