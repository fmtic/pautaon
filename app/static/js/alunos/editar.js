// static/js/alunos/editar.js
(function() {
    'use strict';

    // Configuração recebida do servidor
    const config = window.alunoEditConfig || {};

    // Elementos DOM
    const stepIndicators = {
        1: document.getElementById('step-indicator-1'),
        2: document.getElementById('step-indicator-2'),
        3: document.getElementById('step-indicator-3'),
        4: document.getElementById('step-indicator-4'),
        5: document.getElementById('step-indicator-5')
    };
    const steps = {
        1: document.getElementById('step-1'),
        2: document.getElementById('step-2'),
        3: document.getElementById('step-3'),
        4: document.getElementById('step-4'),
        5: document.getElementById('step-5')
    };
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');

    let currentStep = 1;
    const totalSteps = 5;

    // Funções públicas
    window.updateStepper = updateStepper;
    window.goToStep = goToStep;
    window.nextStep = nextStep;
    window.previewImage = previewImage;
    window.toggleLaudoUpload = toggleLaudoUpload;
    window.updateFileName = updateFileName;
    window.toggleBeneficioSocial = toggleBeneficioSocial;
    window.toggleMedicacao = toggleMedicacao;

    // Função para atualizar a aparência do stepper e visibilidade dos botões
    function updateStepper() {
        for (let i = 1; i <= totalSteps; i++) {
            const indicator = stepIndicators[i];
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

        if (prevBtn) prevBtn.classList.toggle('d-none', currentStep === 1);

        if (currentStep === totalSteps) {
            if (nextBtn) nextBtn.classList.add('d-none');
            if (submitBtn) submitBtn.classList.remove('d-none');
        } else {
            if (nextBtn) nextBtn.classList.remove('d-none');
            if (submitBtn) submitBtn.classList.add('d-none');
        }
    }

    function goToStep(n) {
        if (n === currentStep) return;
        steps[currentStep].classList.remove('active');
        currentStep = n;
        steps[currentStep].classList.add('active');
        updateStepper();
        window.scrollTo(0, 0);
    }

    function nextStep(n) {
        steps[currentStep].classList.remove('active');
        currentStep += n;
        steps[currentStep].classList.add('active');
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

    // Inicialização
    document.addEventListener('DOMContentLoaded', function() {
        // Calcular idade se a função global existir
        if (typeof calcularIdade === 'function') {
            calcularIdade();
        }
        // Atualizar visualização do stepper
        updateStepper();
        // Pré-configurar visibilidade dos campos condicionais
        const beneficioSelect = document.querySelector('select[name="beneficio_social_status"]');
        if (beneficioSelect) toggleBeneficioSocial(beneficioSelect);
        const medicacaoSelect = document.querySelector('select[name="saude_medicacao"]');
        if (medicacaoSelect) toggleMedicacao(medicacaoSelect);
        const laudoCheckbox = document.getElementById('saude_laudo');
        if (laudoCheckbox) toggleLaudoUpload(laudoCheckbox);
    });
})();