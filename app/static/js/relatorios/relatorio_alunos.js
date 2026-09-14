// Funções da página templates/relatorios/relatorio_alunos.html

document.addEventListener('DOMContentLoaded', function () {
    const checkboxes = document.querySelectorAll('.column-checkbox');
    const selectedCountSpan = document.getElementById('selectedCount');
    const searchInput = document.getElementById('columnSearchInput');

    // Mapeamento dos modelos de seleção rápida (Presets)
    const presets = {
        'basico': ['nome', 'cpf', 'data_nascimento', 'idade', 'sexo'],
        'saude': ['nome', 'pcd', 'tipo_deficiencia', 'alergias', 'medicamentos', 'laudo_medico'],
        'escola': ['nome', 'escolaridade', 'nome_instituicao', 'tipo_instituicao', 'status_escolar', 'turno_escolar', 'bolsista'],
        'rotas': ['nome', 'periodo_letivo', 'curso', 'turma', 'nivel_aluno', 'freq_geral', 'situacao_final']
    };

    // Atualiza o contador visual de colunas marcadas e o destaque dos cards
    function updateCounters() {
        let totalChecked = 0;
        checkboxes.forEach(cb => {
            const box = cb.closest('.field-box');
            if (cb.checked) {
                totalChecked++;
                if (box) box.classList.add('active-selection');
            } else {
                if (box) box.classList.remove('active-selection');
            }
        });
        if (selectedCountSpan) {
            selectedCountSpan.textContent = totalChecked;
        }
    }

    // Selecionar ou desmarcar todas as colunas visíveis
    window.selectAllColumns = function(status) {
        checkboxes.forEach(cb => {
            const item = cb.closest('.field-item');
            if (item && item.style.display !== 'none') {
                cb.checked = status;
            }
        });
        updateCounters();
    };

    // Alternar estado de uma categoria inteira
    window.toggleCategory = function(catId) {
        const catCheckboxes = document.querySelectorAll(`.column-checkbox[data-category="${catId}"]`);
        const allChecked = Array.from(catCheckboxes).every(cb => cb.checked);
        catCheckboxes.forEach(cb => cb.checked = !allChecked);
        updateCounters();
    };

    // Aplicar seleção pré-definida de colunas
    window.applyPreset = function(presetKey) {
        const targetCols = presets[presetKey] || [];
        checkboxes.forEach(cb => {
            cb.checked = targetCols.includes(cb.value);
        });
        updateCounters();
    };

    // Busca dinâmica de campos em tempo real
    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            const term = e.target.value.toLowerCase().trim();
            const items = document.querySelectorAll('.field-item');

            items.forEach(item => {
                const label = item.getAttribute('data-label') || '';
                if (label.includes(term)) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    // Ouvintes de evento para os checkboxes
    checkboxes.forEach(cb => cb.addEventListener('change', updateCounters));

    // Inicialização do estado visual
    updateCounters();
});