// ========== MÁSCARAS ==========
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
    if (telefone) telefone.addEventListener('input', () => maskTelefone(telefone));
}

// ========== STEPPER (modo preenchimento normal) ==========
let currentStep = 1;
let totalSteps = 7;

function changeStep(delta) {
    const newStep = currentStep + delta;
    if (newStep >= 1 && newStep <= totalSteps) {
        currentStep = newStep;
        updateStepDisplay();
    }
}

function goToStep(step) {
    if (step >= 1 && step <= totalSteps) {
        currentStep = step;
        updateStepDisplay();
    }
}

function updateStepDisplay() {
    document.querySelectorAll('.form-step').forEach((stepDiv, index) => {
        const isActive = index + 1 === currentStep;
        stepDiv.style.display = isActive ? 'block' : 'none';
        stepDiv.classList.toggle('active', isActive);
    });
    document.querySelectorAll('.step-item').forEach((indicator, index) => {
        const stepNum = index + 1;
        indicator.classList.toggle('active', stepNum === currentStep);
        indicator.classList.toggle('completed', stepNum < currentStep);
    });
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    if (prevBtn) prevBtn.style.display = currentStep === 1 ? 'none' : 'inline-block';
    if (nextBtn) nextBtn.style.display = currentStep === totalSteps ? 'none' : 'inline-block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

window.changeStep = changeStep;
window.goToStep = goToStep;

// ========== AUTOPREENCHIMENTO ==========
function initAutoPreenchimento() {
    const selectAluno = document.querySelector('select[name="aluno_id"]');
    if (!selectAluno) return;
    selectAluno.addEventListener('change', function () {
        const alunoId = this.value;
        if (!alunoId) { limparCampos(); return; }
        fetch(`/servico-social/aluno/${alunoId}/dados`)
            .then(r => { if (!r.ok) throw new Error('Erro'); return r.json(); })
            .then(data => { preencherCampos(data); atualizarFoto(data.foto_url); })
            .catch(err => console.error('Erro no autopreenchimento:', err));
    });
}

function preencherCampos(data) {
    const mapping = {
        'nome': 'nome', 'data_nascimento': 'data_nascimento', 'sexo': 'sexo',
        'raca_cor': 'raca_cor', 'mae': 'mae', 'pai': 'pai',
        'responsavel_nome': 'responsavel_nome', 'parentesco_responsavel': 'parentesco_responsavel',
        'endereco': 'endereco', 'telefone': 'telefone',
        'turma': 'turmas', 'escola': 'escola', 'serie': 'serie', 'turno': 'turno'
    };
    for (const [campo, chave] of Object.entries(mapping)) {
        const input = document.querySelector(`[name="${campo}"]`);
        if (!input) continue;
        if (chave === 'turmas' && Array.isArray(data[chave])) input.value = data[chave].join(', ');
        else input.value = data[chave] || '';
    }
    const sexoSelect = document.querySelector('select[name="sexo"]');
    if (sexoSelect && data.sexo) sexoSelect.value = data.sexo;
    const racaSelect = document.querySelector('select[name="raca_cor"]');
    if (racaSelect && data.raca_cor) racaSelect.value = data.raca_cor;
    if (data.turno) {
        document.querySelectorAll('input[name="turno"]').forEach(r => {
            if (r.value === data.turno) r.checked = true;
        });
    }
    if (data.data_nascimento) calcularIdadePorData(data.data_nascimento);
}

function limparCampos() {
    ['nome','data_nascimento','sexo','raca_cor','mae','pai','responsavel_nome',
     'parentesco_responsavel','endereco','telefone','turma','escola','serie','turno']
    .forEach(campo => {
        const el = document.querySelector(`[name="${campo}"]`);
        if (el) { if (el.type === 'radio') el.checked = false; else el.value = ''; }
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
    // Preenche data atual no campo de data do atendimento, se estiver vazio
    const dataInput = document.querySelector('input[name="data_atendimento"]');
    if (dataInput && !dataInput.value) {
        dataInput.value = new Date().toISOString().split('T')[0];
    }
    if (window.MODO_IMPRESSAO) {
        // --- MODO IMPRESSÃO ---
        // 1. Exibe todos os passos via CSS class — sem style inline, para não sujar o DOM
        document.body.classList.add('modo-impressao-ativo');

        // 2. Preenche campos com os dados salvos (fallback caso o Jinja2 não tenha preenchido)
        Object.keys(window.DADOS_FORMULARIO).forEach(key => {
            const field = document.querySelector(`[name="${key}"]`);
            if (!field) return;
            if (field.type === 'checkbox' || field.type === 'radio') {
                if (field.value === window.DADOS_FORMULARIO[key]) field.checked = true;
            } else {
                field.value = window.DADOS_FORMULARIO[key];
            }
        });

        // 3. Calcula idade
        if (window.DADOS_FORMULARIO.data_nascimento) {
            calcularIdadePorData(window.DADOS_FORMULARIO.data_nascimento);
        }

        // 4. Dispara impressão automaticamente
        setTimeout(() => window.print(), 800);

    } else {
        // --- MODO PREENCHIMENTO NORMAL ---
        updateStepDisplay();
        initAutoPreenchimento();
        const dataNasc = document.querySelector('input[name="data_nascimento"]');
        if (dataNasc) {
            if (dataNasc.value) calcularIdadePorData(dataNasc.value);
            dataNasc.addEventListener('change', () => calcularIdadePorData(dataNasc.value));
        }
    }
});