// Máscaras e Funcionalidades para o formulário de Alunos
document.addEventListener('DOMContentLoaded', function () {
    // Máscara de CPF: 000.000.000-00
    const cpfInputs = document.querySelectorAll('.mask-cpf');
    cpfInputs.forEach(input => {
        input.addEventListener('input', e => {
            let v = e.target.value.replace(/\D/g, '');
            if (v.length > 11) v = v.substring(0, 11);
            v = v.replace(/(\d{3})(\d)/, '$1.$2');
            v = v.replace(/(\d{3})(\d)/, '$1.$2');
            v = v.replace(/(\d{3})(\d{1,2})$/, '$1-$2');
            e.target.value = v;
        });
    });

    // Máscara de CEP: 00000-000
    const cepInputs = document.querySelectorAll('.mask-cep');
    cepInputs.forEach(input => {
        input.addEventListener('input', e => {
            let v = e.target.value.replace(/\D/g, '');
            if (v.length > 8) v = v.substring(0, 8);
            v = v.replace(/(\d{5})(\d)/, '$1-$2');
            e.target.value = v;
        });

        // Buscar endereço ao completar o CEP
        input.addEventListener('blur', e => {
            const cep = e.target.value.replace(/\D/g, '');
            if (cep.length === 8) {
                buscarEndereco(cep);
            }
        });
    });

    // Máscara de Telefone: (00) 0 0000-0000
    const phoneInputs = document.querySelectorAll('.mask-phone');
    phoneInputs.forEach(input => {
        input.addEventListener('input', e => {
            let v = e.target.value.replace(/\D/g, '');
            if (v.length > 11) v = v.substring(0, 11);
            if (v.length > 10) {
                v = v.replace(/^(\d{2})(\d{5})(\d{4})$/, '($1) $2-$3');
            } else if (v.length > 5) {
                v = v.replace(/^(\d{2})(\d{4})(\d{0,4})$/, '($1) $2-$3');
            } else if (v.length > 2) {
                v = v.replace(/^(\d{2})(\d{0,5})$/, '($1) $2');
            } else if (v.length > 0) {
                v = v.replace(/^(\d{0,2})$/, '($1');
            }
            e.target.value = v;
        });
    });

    // Lógica de Auto-preenchimento do Responsável Legal
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
            respNome.value = nomeMae.value;
            if (respCpf && cpfMae) respCpf.value = cpfMae.value;
            respNome.readOnly = true;
            if (respCpf) respCpf.readOnly = true;
        } else if (tipo === 'Pai' && nomePai) {
            respNome.value = nomePai.value;
            if (respCpf && cpfPai) respCpf.value = cpfPai.value;
            respNome.readOnly = true;
            if (respCpf) respCpf.readOnly = true;
        } else {
            respNome.readOnly = false;
            if (respCpf) respCpf.readOnly = false;
        }
    }

    // Validação de CPF
    function validarCPF(cpf) {
        cpf = cpf.replace(/[^\d]+/g, '');
        if (cpf == '') return false;
        if (cpf.length != 11 || 
            cpf == "00000000000" || cpf == "11111111111" || cpf == "22222222222" || 
            cpf == "33333333333" || cpf == "44444444444" || cpf == "55555555555" || 
            cpf == "66666666666" || cpf == "77777777777" || cpf == "88888888888" || 
            cpf == "99999999999") return false;
        
        let add = 0;
        for (let i = 0; i < 9; i++) add += parseInt(cpf.charAt(i)) * (10 - i);
        let rev = 11 - (add % 11);
        if (rev == 10 || rev == 11) rev = 0;
        if (rev != parseInt(cpf.charAt(9))) return false;
        
        add = 0;
        for (let i = 0; i < 10; i++) add += parseInt(cpf.charAt(i)) * (11 - i);
        rev = 11 - (add % 11);
        if (rev == 10 || rev == 11) rev = 0;
        if (rev != parseInt(cpf.charAt(10))) return false;
        
        return true;
    }

    const cpfValidators = document.querySelectorAll('.validate-cpf');
    cpfValidators.forEach(input => {
        input.addEventListener('blur', e => {
            const val = e.target.value;
            if (val && !validarCPF(val)) {
                e.target.classList.add('is-invalid');
            } else {
                e.target.classList.remove('is-invalid');
            }
        });
    });

    // IBGE API: Naturalidade
    const ufSelect = document.getElementById('natural_uf');
    const cidadeSelect = document.getElementById('natural_cidade');

    async function carregarUFs() {
        if (!ufSelect) return;
        try {
            const response = await fetch('https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome');
            const ufs = await response.json();
            const selectedUf = ufSelect.getAttribute('data-selected');
            
            ufs.forEach(uf => {
                const option = document.createElement('option');
                option.value = uf.sigla;
                option.textContent = uf.nome;
                if (uf.sigla === selectedUf) option.selected = true;
                ufSelect.appendChild(option);
            });

            if (selectedUf) carregarCidades(selectedUf);
        } catch (error) {
            console.error('Erro ao carregar UFs:', error);
        }
    }

    async function carregarCidades(ufSigla) {
        if (!cidadeSelect) return;
        cidadeSelect.innerHTML = '<option value="">Carregando...</option>';
        try {
            const response = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/estados/${ufSigla}/municipios?orderBy=nome`);
            const cidades = await response.json();
            const selectedCidade = cidadeSelect.getAttribute('data-selected');
            
            cidadeSelect.innerHTML = '<option value="">Selecione a Cidade</option>';
            cidades.forEach(cidade => {
                const option = document.createElement('option');
                option.value = cidade.nome;
                option.textContent = cidade.nome;
                if (cidade.nome === selectedCidade) option.selected = true;
                cidadeSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Erro ao carregar cidades:', error);
            cidadeSelect.innerHTML = '<option value="">Erro ao carregar</option>';
        }
    }

    if (ufSelect) {
        carregarUFs();
        ufSelect.addEventListener('change', e => carregarCidades(e.target.value));
    }

    // Re-adicionando a sincronização do responsável
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
});

// --- Lógica de Webcam ---
let webcamStream = null;
let btcModalInstance = null;

async function abrirWebcam() {
    const video = document.getElementById('webcamVideo');
    const modalEl = document.getElementById('webcamModal');
    
    if (!btcModalInstance && typeof bootstrap !== 'undefined') {
        btcModalInstance = new bootstrap.Modal(modalEl);
    }

    try {
        webcamStream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480, facingMode: "user" }, 
            audio: false 
        });
        video.srcObject = webcamStream;
        if (btcModalInstance) btcModalInstance.show();
    } catch (err) {
        console.error("Erro ao acessar webcam:", err);
        alert("Não foi possível acessar a câmera. Verifique as permissões do seu navegador.");
    }
}

function fecharWebcam() {
    if (webcamStream) {
        webcamStream.getTracks().forEach(track => track.stop());
    }
    if (btcModalInstance) btcModalInstance.hide();
}

function capturarFoto() {
    const video = document.getElementById('webcamVideo');
    const canvas = document.getElementById('webcamCanvas');
    const context = canvas.getContext('2d');
    
    // Inverter o contexto do canvas para bater com o mirror do vídeo
    context.save();
    context.scale(-1, 1);
    context.drawImage(video, -canvas.width, 0, canvas.width, canvas.height);
    context.restore();
    
    // Converter canvas para Blob (formato JPEG)
    canvas.toBlob((blob) => {
        const file = new File([blob], "captura_webcam.jpg", { type: "image/jpeg" });
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        
        const inputFoto = document.getElementById('inputFotoManual');
        if (inputFoto) {
            inputFoto.files = dataTransfer.files;
            inputFoto.dispatchEvent(new Event('change'));
        }
        
        fecharWebcam();
    }, 'image/jpeg', 0.95);
}

// Função para buscar endereço via CEP (ViaCEP)
function buscarEndereco(cep) {
    if (!cep) return;

    // Feedback visual opcional
    const ruaInput = document.getElementById('rua');
    if (ruaInput) ruaInput.placeholder = "Buscando...";

    fetch(`https://viacep.com.br/ws/${cep}/json/`)
        .then(response => response.json())
        .then(data => {
            if (!data.erro) {
                if (document.getElementById('rua')) document.getElementById('rua').value = data.logradouro;
                if (document.getElementById('bairro')) document.getElementById('bairro').value = data.bairro;
                if (document.getElementById('cidade')) document.getElementById('cidade').value = data.localidade;
                if (document.getElementById('uf')) document.getElementById('uf').value = data.uf;
            } else {
                alert("CEP não encontrado.");
            }
        })
        .catch(error => {
            console.error('Erro ao buscar CEP:', error);
        })
        .finally(() => {
            if (ruaInput) ruaInput.placeholder = "";
        });
}
