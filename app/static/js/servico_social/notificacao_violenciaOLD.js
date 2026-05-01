// Máscara de telefone
function maskTelefone(input) {
    let value = input.value.replace(/\D/g, '');
    if (value.length > 10) {
        value = value.replace(/^(\d{2})(\d{5})(\d{4})/, '($1) $2-$3');
    } else if (value.length > 6) {
        value = value.replace(/^(\d{2})(\d{4})(\d{0,4})/, '($1) $2-$3');
    } else if (value.length > 2) {
        value = value.replace(/^(\d{2})(\d{0,5})/, '($1) $2');
    }
    input.value = value;
}

function aplicarMascaras() {
    const telefone = document.querySelector('input[name="telefone"]');
    if (telefone) {
        telefone.addEventListener('input', () => maskTelefone(telefone));
    }
}

// ========== STEPS (navegação) ==========
let currentStep = 1;
const totalSteps = 7;

function updateStepDisplay() {
    window.scrollTo({top: 0, behavior: 'smooth'});
    for (let i = 1; i <= totalSteps; i++) {
        const stepDiv = document.getElementById(`step-${i}`);
        if (stepDiv) stepDiv.classList.toggle('active', i === currentStep);
        
        const stepIndicator = document.querySelector(`.step-item[data-step="${i}"]`);
        if (stepIndicator) {
            stepIndicator.classList.toggle('active', i === currentStep);
            // Marca como completed se o step já foi visitado e não é o atual
            const isCompleted = (i < currentStep);
            stepIndicator.classList.toggle('completed', isCompleted);
        }
    }
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    if (prevBtn) prevBtn.style.display = currentStep === 1 ? 'none' : 'inline-block';
    if (nextBtn) nextBtn.style.display = currentStep === totalSteps ? 'none' : 'inline-block';
}

function changeStep(delta) {
    let newStep = currentStep + delta;
    if (newStep < 1) newStep = 1;
    if (newStep > totalSteps) newStep = totalSteps;
    currentStep = newStep;
    updateStepDisplay();
}

window.changeStep = changeStep;
window.goToStep = function(step) {
    if (step >= 1 && step <= totalSteps) {
        currentStep = step;
        updateStepDisplay();
    }
};

// ========== AUTO PREENCHIMENTO ==========
function initAutoPreenchimento() {
    const selectAluno = document.querySelector('select[name="aluno_id"]');
    if (!selectAluno) return;

    selectAluno.addEventListener('change', function() {
        const alunoId = this.value;
        if (!alunoId) {
            limparCampos();
            return;
        }

        fetch(`/servico-social/aluno/${alunoId}/dados`)
            .then(response => {
                if (!response.ok) throw new Error('Erro ao buscar dados');
                return response.json();
            })
            .then(data => {
                preencherCampos(data);
                atualizarFoto(data.foto_url);
            })
            .catch(error => console.error('Erro no autopreenchimento:', error));
    });
}

function preencherCampos(data) {
    const mapping = {
        'nome': 'nome',
        'data_nascimento': 'data_nascimento',
        'sexo': 'sexo',
        'raca_cor': 'raca_cor',
        'mae': 'mae',
        'pai': 'pai',
        'responsavel_nome': 'responsavel_nome',
        'parentesco_responsavel': 'parentesco_responsavel',
        'endereco': 'endereco',
        'telefone': 'telefone',
        'turma': 'turmas',
        'escola': 'escola',
        'serie': 'serie',
        'turno': 'turno'
    };

    for (const [campo, chave] of Object.entries(mapping)) {
        const input = document.querySelector(`[name="${campo}"]`);
        if (input) {
            if (chave === 'turmas' && Array.isArray(data[chave])) {
                input.value = data[chave].join(', ');
            } else {
                input.value = data[chave] || '';
            }
        }
    }

    const sexoSelect = document.querySelector('select[name="sexo"]');
    if (sexoSelect && data.sexo) sexoSelect.value = data.sexo;

    const racaSelect = document.querySelector('select[name="raca_cor"]');
    if (racaSelect && data.raca_cor) racaSelect.value = data.raca_cor;

    if (data.turno) {
        const radiosTurno = document.querySelectorAll('input[name="turno"]');
        radiosTurno.forEach(radio => {
            if (radio.value === data.turno) radio.checked = true;
        });
    }

    const deficienciaInput = document.querySelector('input[name="deficiencia_outros"]');
    if (deficienciaInput && data.deficiencia) deficienciaInput.value = data.deficiencia;

    const dataNasc = document.querySelector('input[name="data_nascimento"]');
    if (dataNasc && dataNasc.value) calcularIdadePorData(dataNasc.value);
}

function limparCampos() {
    const campos = [
        'nome', 'data_nascimento', 'sexo', 'raca_cor', 'mae', 'pai',
        'responsavel_nome', 'parentesco_responsavel', 'endereco', 'telefone',
        'turma', 'escola', 'serie', 'turno'
    ];
    campos.forEach(campo => {
        const el = document.querySelector(`[name="${campo}"]`);
        if (el) {
            if (el.type === 'radio') el.checked = false;
            else el.value = '';
        }
    });
    const fotoImg = document.getElementById('foto_aluno');
    if (fotoImg) fotoImg.src = '/static/img/default.png';
}

function atualizarFoto(url) {
    const fotoImg = document.getElementById('foto_aluno');
    if (fotoImg && url) fotoImg.src = url;
}

function calcularIdadePorData(dataNasc) {
    const hoje = new Date();
    const nasc = new Date(dataNasc);
    let idade = hoje.getFullYear() - nasc.getFullYear();
    const mesDiff = hoje.getMonth() - nasc.getMonth();
    if (mesDiff < 0 || (mesDiff === 0 && hoje.getDate() < nasc.getDate())) idade--;
    const idadeInput = document.getElementById('idade_aluno');
    if (idadeInput) idadeInput.value = idade > 0 ? idade : '';
}

// ========== INICIALIZAÇÃO ==========
document.addEventListener('DOMContentLoaded', () => {
    aplicarMascaras();
    initAutoPreenchimento();
    updateStepDisplay(); // Inicializa o stepper

    // Calcula idade se data já estiver preenchida (edição)
    const dataNasc = document.querySelector('input[name="data_nascimento"]');
    if (dataNasc && dataNasc.value) calcularIdadePorData(dataNasc.value);
    
    // Atualiza idade quando data for alterada manualmente
    if (dataNasc) {
        dataNasc.addEventListener('change', () => calcularIdadePorData(dataNasc.value));
    }
});