// static/js/alunos/novo.js
(function() {
    'use strict';

    let currentStep = 1;
    const stepIds = Array.from(document.querySelectorAll('.form-step'))
        .map(step => Number(step.id.replace('step-', '')))
        .filter(Number.isInteger)
        .sort((a, b) => a - b);
    const lastStepId = stepIds[stepIds.length - 1] || 1;

    // Funções globais
    window.updateStepper = updateStepper;
    window.goToStep = goToStep;
    window.nextStep = nextStep;
    window.previewImage = previewImage;
    window.toggleLaudoUpload = toggleLaudoUpload;
    window.updateFileName = updateFileName;
    window.toggleBeneficioSocial = toggleBeneficioSocial;
    window.toggleMedicacao = toggleMedicacao;

    function updateStepper() {
        for (let i = 1; i <= 5; i++) {
            const indicator = document.getElementById(`step-indicator-${i}`);
            if (!indicator) continue;

            const hasStep = stepIds.includes(i);
            indicator.classList.toggle('d-none', !hasStep);
            if (!hasStep) continue;

            if (i < currentStep) {
                indicator.classList.remove('active');
                indicator.classList.add('completed');
                indicator.innerHTML = '<i class="bi bi-check"></i>';
            } else if (i === currentStep) {
                indicator.classList.remove('completed');
                indicator.classList.add('active');
                indicator.innerHTML = i;
            } else {
                indicator.classList.remove('active', 'completed');
                indicator.innerHTML = i;
            }
        }
        document.getElementById('prevBtn')?.classList.toggle('d-none', currentStep === 1);
        if (currentStep === lastStepId) {
            document.getElementById('nextBtn')?.classList.add('d-none');
            document.getElementById('submitBtn')?.classList.remove('d-none');
        } else {
            document.getElementById('nextBtn')?.classList.remove('d-none');
            document.getElementById('submitBtn')?.classList.add('d-none');
        }
    }

    function goToStep(n) {
        if (n === currentStep || !stepIds.includes(n)) return;

        document.getElementById(`step-${currentStep}`)?.classList.remove('active');
        currentStep = n;
        document.getElementById(`step-${currentStep}`)?.classList.add('active');
        updateStepper();
        window.scrollTo(0, 0);
    }

    function nextStep(n) {
        const currentIndex = stepIds.indexOf(currentStep);
        const nextIndex = currentIndex + n;
        const nextStepId = stepIds[nextIndex];

        if (!nextStepId) return;

        document.getElementById(`step-${currentStep}`)?.classList.remove('active');
        currentStep = nextStepId;
        document.getElementById(`step-${currentStep}`)?.classList.add('active');
        updateStepper();
        window.scrollTo(0, 0);
    }

    function previewImage(input) {
        const preview = document.getElementById('img-preview');
        const icon = document.getElementById('placeholder-icon');
        if (input.files && input.files[0]) {
            const reader = new FileReader();
            reader.onload = function(e) {
                preview.src = e.target.result;
                preview.classList.remove('d-none');
                if (icon) icon.classList.add('d-none');
            };
            reader.readAsDataURL(input.files[0]);
        }
    }

    function toggleLaudoUpload(checkbox) {
        const container = document.getElementById('laudo_upload_container');
        if (container) container.classList.toggle('d-none', !checkbox.checked);
    }

    function updateFileName(id, input) {
        const label = document.getElementById(`name_${id}`);
        if (input.files && input.files[0]) {
            const file = input.files[0];
            if (file.size > 2 * 1024 * 1024) {
                alert("Arquivo muito grande! Máximo 2MB.");
                input.value = "";
                if (label) label.innerText = "Clique para selecionar";
                return;
            }
            if (label) {
                label.innerText = file.name;
                label.classList.remove('text-muted');
                label.classList.add('text-primary', 'fw-bold');
            }
        }
    }

    function toggleBeneficioSocial(select) {
        const div = document.getElementById('beneficio_social_div');
        if (div) div.classList.toggle('d-none', select.value !== 'Sim');
    }

    function toggleMedicacao(select) {
        const div = document.getElementById('medicacao_nome_div');
        if (div) div.classList.toggle('d-none', select.value !== 'Sim');
    }

    document.addEventListener('DOMContentLoaded', function() {
        updateStepper();
        // Inicializa os toggles
        const beneficioSelect = document.querySelector('select[name="beneficio_social_status"]');
        if (beneficioSelect) toggleBeneficioSocial(beneficioSelect);
        const medicacaoSelect = document.querySelector('select[name="saude_medicacao"]');
        if (medicacaoSelect) toggleMedicacao(medicacaoSelect);
        const laudoCheckbox = document.getElementById('saude_laudo');
        if (laudoCheckbox) toggleLaudoUpload(laudoCheckbox);
    });
})();
