function calcularIdade() {
    const dataInput = document.getElementById('data_nascimento');
    const campoIdade = document.getElementById('idade');

    if (!dataInput || !campoIdade || !dataInput.value) {
        if (campoIdade) {
            campoIdade.value = "";
            campoIdade.style.backgroundColor = "";
        }
        return;
    }

    const hoje = new Date();
    const nascimento = new Date(dataInput.value);
    let idade = hoje.getFullYear() - nascimento.getFullYear();
    const m = hoje.getMonth() - nascimento.getMonth();

    if (m < 0 || (m === 0 && hoje.getDate() < nascimento.getDate())) {
        idade--;
    }

    campoIdade.value = idade + " anos";

    // Lógica de cores (Ajustada para tons que funcionam com letra preta)
    if (idade < 14) {
        campoIdade.style.setProperty('background-color', '#ffcccc', 'important'); // Vermelho claro
        campoIdade.style.setProperty('border-color', '#f5c2c7', 'important');
    } else if (idade < 18) {
        campoIdade.style.setProperty('background-color', '#fff3cd', 'important'); // Amarelo claro
        campoIdade.style.setProperty('border-color', '#ffecb5', 'important');
    } else {
        campoIdade.style.setProperty('background-color', '#cfe2ff', 'important'); // Azul claro (Sucesso!)
        campoIdade.style.setProperty('border-color', '#b6d4fe', 'important');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const inputData = document.getElementById('data_nascimento');
    if (inputData) {
        // Calcula ao mudar a data
        inputData.addEventListener('change', calcularIdade);
        // Calcula ao carregar (para casos de edição)
        calcularIdade();
    }
});