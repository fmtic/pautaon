// ================================================
// aluno_form.js - Todas as funcionalidades do formulário de Novo Aluno
// ================================================

document.addEventListener('DOMContentLoaded', function () {

    // ==================== MÁSCARAS ====================

    // Máscara CPF
    document.querySelectorAll('.mask-cpf').forEach(input => {
        input.addEventListener('input', function (e) {
            let v = e.target.value.replace(/\D/g, '');
            if (v.length > 11) v = v.substring(0, 11);
            v = v.replace(/(\d{3})(\d)/, '$1.$2');
            v = v.replace(/(\d{3})(\d)/, '$1.$2');
            v = v.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
            e.target.value = v;
        });
    });

    // Máscara CEP + Busca automática
    document.querySelectorAll('.mask-cep').forEach(input => {
        input.addEventListener('input', function (e) {
            let v = e.target.value.replace(/\D/g, '');
            if (v.length > 8) v = v.substring(0, 8);
            v = v.replace(/(\d{5})(\d)/, '$1-$2');
            e.target.value = v;
        });

        input.addEventListener('blur', function (e) {
            const cep = e.target.value.replace(/\D/g, '');
            if (cep.length === 8) buscarEndereco(cep);
        });
    });

    // Máscara Telefone
    document.querySelectorAll('.mask-phone').forEach(input => {
        input.addEventListener('input', function (e) {
            let v = e.target.value.replace(/\D/g, '');
            if (v.length > 11) v = v.substring(0, 11);

            if (v.length > 10) {
                v = v.replace(/^(\d{2})(\d{5})(\d{4})$/, '($1) $2-$3');
            } else if (v.length > 5) {
                v = v.replace(/^(\d{2})(\d{4})(\d{0,4})$/, '($1) $2-$3');
            } else if (v.length > 2) {
                v = v.replace(/^(\d{2})(\d{0,5})$/, '($1) $2');
            }
            e.target.value = v;
        });
    });

    // ==================== LÓGICA RESPONSÁVEL LEGAL ====================
    const respTipo = document.getElementById('responsavel_tipo');
    const respNome = document.getElementById('responsavel_nome');
    const respCpf = document.getElementById('responsavel_cpf');

    const nomeMae = document.getElementById('nome_mae');
    const cpfMae = document.getElementById('cpf_mae');
    const nomePai = document.getElementById('nome_pai');
    const cpfPai = document.getElementById('cpf_pai');

    function syncResponsavel() {
        if (!respTipo || !respNome) return;
        const tipo = respTipo.value;

        if (tipo === 'Mãe' && nomeMae) {
            respNome.value = nomeMae.value || '';
            if (respCpf && cpfMae) respCpf.value = cpfMae.value || '';
            respNome.readOnly = true;
            if (respCpf) respCpf.readOnly = true;
        } else if (tipo === 'Pai' && nomePai) {
            respNome.value = nomePai.value || '';
            if (respCpf && cpfPai) respCpf.value = cpfPai.value || '';
            respNome.readOnly = true;
            if (respCpf) respCpf.readOnly = true;
        } else {
            respNome.readOnly = false;
            if (respCpf) respCpf.readOnly = false;
        }
    }

    if (respTipo) {
        respTipo.addEventListener('change', syncResponsavel);
        [nomeMae, cpfMae, nomePai, cpfPai].forEach(el => {
            if (el) el.addEventListener('input', () => {
                if (respTipo.value === 'Mãe' || respTipo.value === 'Pai') {
                    syncResponsavel();
                }
            });
        });
    }

    // ==================== VALIDAÇÃO VISUAL DE CPF (opcional) ====================
    function validarCPF(cpf) {
        cpf = cpf.replace(/\D/g, '');
        if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
        // ... (lógica completa mantida)
        let add = 0;
        for (let i = 0; i < 9; i++) add += parseInt(cpf.charAt(i)) * (10 - i);
        let rev = 11 - (add % 11);
        if (rev === 10 || rev === 11) rev = 0;
        if (rev !== parseInt(cpf.charAt(9))) return false;

        add = 0;
        for (let i = 0; i < 10; i++) add += parseInt(cpf.charAt(i)) * (11 - i);
        rev = 11 - (add % 11);
        if (rev === 10 || rev === 11) rev = 0;
        if (rev !== parseInt(cpf.charAt(10))) return false;

        return true;
    }

    document.querySelectorAll('.validate-cpf').forEach(input => {
        input.addEventListener('blur', function () {
            if (this.value && !validarCPF(this.value)) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
    });

    // ==================== IBGE - NATURALIDADE ====================
    const ufSelect = document.getElementById('natural_uf');
    const cidadeSelect = document.getElementById('natural_cidade');

    // Função para carregar UFs
    async function carregarUFs() {
        if (!ufSelect) return;
        try {
            const res = await fetch('https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome');
            const ufs = await res.json();
            ufs.forEach(uf => {
                const opt = new Option(uf.nome, uf.sigla);
                ufSelect.appendChild(opt);
            });

            // Após carregar as UFs, aplica o valor salvo (se existir)
            const ufSelecionada = ufSelect.getAttribute('data-selected');
            if (ufSelecionada) {
                ufSelect.value = ufSelecionada;
                // Dispara o evento 'change' para carregar as cidades correspondentes
                ufSelect.dispatchEvent(new Event('change', { bubbles: true }));
            }
        } catch (e) {
            console.error('Erro ao carregar UFs:', e);
        }
    }

    // Função para carregar cidades com base na UF
    async function carregarCidades(ufSigla) {
        if (!cidadeSelect || !ufSigla) return;
        cidadeSelect.innerHTML = '<option value="">Carregando...</option>';
        try {
            const res = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${ufSigla}/municipios?orderBy=nome`);
            const cidades = await res.json();
            cidadeSelect.innerHTML = '<option value="">Selecione a Cidade</option>';
            cidades.forEach(c => {
                cidadeSelect.appendChild(new Option(c.nome, c.nome));
            });

            // Após carregar as cidades, aplica o valor salvo (se existir)
            const cidadeSalva = cidadeSelect.getAttribute('data-selected');
            if (cidadeSalva && cidadeSalva !== "") {
                cidadeSelect.value = cidadeSalva;
            }
        } catch (e) {
            console.error('Erro ao carregar cidades:', e);
        }
    }

    // Inicialização
    if (ufSelect) {
        // Carrega as UFs (já fará a seleção e carregará cidades se houver data-selected)
        carregarUFs();
        // Adiciona o listener para quando o usuário mudar manualmente
        ufSelect.addEventListener('change', e => carregarCidades(e.target.value));
    }

    // ==================== STEPPER - Navegação Livre ====================
    let currentStep = 1;
    const totalSteps = 5;

    window.updateStepper = function () {
        for (let i = 1; i <= totalSteps; i++) {
            const indicator = document.getElementById(`step-indicator-${i}`);
            if (!indicator) continue;

            if (i < currentStep) {
                indicator.classList.remove("active");
                indicator.classList.add("completed");
                indicator.innerHTML = '<i class="bi bi-check"></i>';
            } else if (i === currentStep) {
                indicator.classList.remove("completed");
                indicator.classList.add("active");
                indicator.innerHTML = i;
            } else {
                indicator.classList.remove("active", "completed");
                indicator.innerHTML = i;
            }
        }

        document.getElementById("prevBtn").classList.toggle("d-none", currentStep === 1);

        const nextBtn = document.getElementById("nextBtn");
        const submitBtn = document.getElementById("submitBtn");

        if (currentStep === totalSteps) {
            nextBtn.classList.add("d-none");
            submitBtn.classList.remove("d-none");
        } else {
            nextBtn.classList.remove("d-none");
            submitBtn.classList.add("d-none");
        }
    };

    window.goToStep = function (n) {
        if (n === currentStep) return;
        document.getElementById(`step-${currentStep}`).classList.remove("active");
        currentStep = n;
        document.getElementById(`step-${currentStep}`).classList.add("active");
        window.updateStepper();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // ✅ Navegação livre (sem validação)
    window.nextStep = function (n) {
        document.getElementById(`step-${currentStep}`).classList.remove("active");
        currentStep += n;

        if (currentStep > totalSteps) currentStep = totalSteps;
        if (currentStep < 1) currentStep = 1;

        document.getElementById(`step-${currentStep}`).classList.add("active");
        window.updateStepper();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // ==================== OUTRAS FUNÇÕES ====================
    window.previewImage = function (input) {
        const preview = document.getElementById("img-preview");
        const icon = document.getElementById("placeholder-icon");
        if (input.files && input.files[0]) {
            const reader = new FileReader();
            reader.onload = e => {
                preview.src = e.target.result;
                preview.classList.remove("d-none");
                icon.classList.add("d-none");
            };
            reader.readAsDataURL(input.files[0]);
        }
    };

    window.toggleLaudoUpload = function (checkbox) {
        const container = document.getElementById("laudo_upload_container");
        if (container) container.classList.toggle("d-none", !checkbox.checked);
    };

    window.updateFileName = function (id, input) {
        const label = document.getElementById(`name_${id}`);
        if (!label || !input.files[0]) return;

        const file = input.files[0];
        if (file.size > 2 * 1024 * 1024) {
            alert("Arquivo muito grande! Máximo permitido: 2MB.");
            input.value = "";
            label.innerText = "Clique para selecionar";
            return;
        }

        label.innerText = file.name.length > 28 ? file.name.substring(0, 25) + "..." : file.name;
        label.classList.add("text-primary", "fw-bold");
    };

    // Inicializa o stepper
    window.updateStepper();
});

// ==================== WEBCAM ====================
let webcamStream = null;
let modalInstance = null;

window.abrirWebcam = async function () {
    const video = document.getElementById('webcamVideo');
    const modalEl = document.getElementById('webcamModal');

    if (!video || !modalEl) {
        alert("A janela da câmera não está disponível nesta página.");
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("Este navegador não permite acessar a câmera.");
        return;
    }

    if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
        alert("Não foi possível abrir a janela da câmera.");
        return;
    }

    if (!modalInstance) {
        modalInstance = new bootstrap.Modal(modalEl, { backdrop: 'static' });
    }

    try {
        window.fecharWebcam();
        webcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: "user" }
        });
        video.srcObject = webcamStream;
        modalInstance.show();
    } catch (err) {
        console.error(err);
        alert("Não foi possível acessar a câmera.");
    }
};

window.fecharWebcam = function () {
    const video = document.getElementById('webcamVideo');

    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
        webcamStream = null;
    }

    if (video) video.srcObject = null;
    if (modalInstance) modalInstance.hide();
};

window.capturarFoto = function () {
    const video = document.getElementById('webcamVideo');
    const canvas = document.getElementById('webcamCanvas');

    if (!video || !canvas) {
        alert("Não foi possível localizar a câmera para capturar a foto.");
        return;
    }

    if (!webcamStream || video.readyState < 2) {
        alert("A câmera ainda não está pronta para capturar a foto.");
        return;
    }

    const ctx = canvas.getContext('2d');

    ctx.save();
    ctx.scale(-1, 1);
    ctx.drawImage(video, -canvas.width, 0, canvas.width, canvas.height);
    ctx.restore();

    canvas.toBlob(blob => {
        if (!blob) {
            alert("Não foi possível gerar a foto da webcam.");
            return;
        }

        const file = new File([blob], "foto_webcam.jpg", { type: "image/jpeg" });
        const dt = new DataTransfer();
        dt.items.add(file);

        const input = document.getElementById('inputFotoManual');
        if (input) {
            input.files = dt.files;
            input.dispatchEvent(new Event('change'));
            if (typeof window.previewImage === 'function') {
                window.previewImage(input);
            }
        }
        window.fecharWebcam();
    }, 'image/jpeg', 0.92);
};

// ==================== BUSCA CEP ====================
window.buscarEndereco = function (cep) {
    const ruaInput = document.getElementById('rua');
    if (ruaInput) ruaInput.placeholder = "Buscando...";

    fetch(`https://viacep.com.br/ws/${cep}/json/`)
        .then(r => r.json())
        .then(data => {
            if (!data.erro) {
                document.getElementById('rua').value = data.logradouro || '';
                document.getElementById('bairro').value = data.bairro || '';
                document.getElementById('cidade').value = data.localidade || '';
                document.getElementById('uf').value = data.uf || '';
            } else {
                alert("CEP não encontrado.");
            }
        })
        .catch(() => console.error("Erro ao buscar CEP"))
        .finally(() => {
            if (ruaInput) ruaInput.placeholder = "";
        });
};

let currentStep = 1;
const totalSteps = 5;

function updateStepper() {
    for (let i = 1; i <= totalSteps; i++) {
        const indicator = document.getElementById(`step-indicator-${i}`);
        if (i < currentStep) {
            indicator.classList.remove("active");
            indicator.classList.add("completed");
            indicator.innerHTML = '<i class="bi bi-check"></i>';
        } else if (i === currentStep) {
            indicator.classList.remove("completed");
            indicator.classList.add("active");
            indicator.innerHTML = i;
        } else {
            indicator.classList.remove("active", "completed");
            indicator.innerHTML = i;
        }
    }

    // Mostrar/Ocultar botões
    document
        .getElementById("prevBtn")
        .classList.toggle("d-none", currentStep === 1);

    if (currentStep === totalSteps) {
        document.getElementById("nextBtn").classList.add("d-none");
        document.getElementById("submitBtn").classList.remove("d-none");
    } else {
        document.getElementById("nextBtn").classList.remove("d-none");
        document.getElementById("submitBtn").classList.add("d-none");
    }
}

function goToStep(n) {
    if (n === currentStep) return;
    document.getElementById(`step-${currentStep}`).classList.remove("active");
    currentStep = n;
    document.getElementById(`step-${currentStep}`).classList.add("active");
    updateStepper();
    window.scrollTo(0, 0);
}

function nextStep(n) {
    // Validação removida a pedido do usuário
    // if (n === 1 && !validateStep()) return;

    document.getElementById(`step-${currentStep}`).classList.remove("active");
    currentStep += n;
    document.getElementById(`step-${currentStep}`).classList.add("active");
    updateStepper();
    window.scrollTo(0, 0);
}

function validateStep() {
    const activeStep = document.getElementById(`step-${currentStep}`);
    const inputs = activeStep.querySelectorAll(
        "input[required], select[required]",
    );
    let valid = true;
    inputs.forEach((input) => {
        if (!input.value) {
            input.classList.add("is-invalid");
            valid = false;
        } else {
            input.classList.remove("is-invalid");
        }
    });
    return valid;
}

function previewImage(input) {
    const preview = document.getElementById("img-preview");
    const icon = document.getElementById("placeholder-icon");
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function (e) {
            preview.src = e.target.result;
            preview.classList.remove("d-none");
            icon.classList.add("d-none");
        };
        reader.readAsDataURL(input.files[0]);
    }
}

function toggleLaudoUpload(checkbox) {
    const container = document.getElementById("laudo_upload_container");
    container.classList.toggle("d-none", !checkbox.checked);
}

function updateFileName(id, input) {
    const label = document.getElementById(`name_${id}`);
    if (input.files[0]) {
        const file = input.files[0];
        if (file.size > 2 * 1024 * 1024) {
            alert("Arquivo muito grande! Máximo 2MB.");
            input.value = "";
            label.innerText = "Clique para selecionar";
            return;
        }
        label.innerText = file.name;
        label.classList.remove("text-muted");
        label.classList.add("text-primary", "fw-bold");
    }
}
