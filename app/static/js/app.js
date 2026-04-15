console.log("app rodando");

// Modal conselho

function abrirModalConselho(etapa) {
    const labelEtapa = document.getElementById('labelEtapa');
    const inputEtapa = document.getElementById('inputEtapa');
    const modalElement = document.getElementById('modalConselho');

    if (!labelEtapa || !inputEtapa || !modalElement) return;

    labelEtapa.innerText = etapa;
    inputEtapa.value = etapa;

    // Filtrar perguntas da etapa selecionada
    const perguntas = document.querySelectorAll('.pergunta-item');
    perguntas.forEach(item => {
        const select = item.querySelector('select');
        if (item.getAttribute('data-etapa') === etapa) {
            item.style.display = 'block';
            if (select) select.disabled = false;
        } else {
            item.style.display = 'none';
            if (select) select.disabled = true;
        }
    });

    const modal = new bootstrap.Modal(modalElement);
    modal.show();
}

// Adiciona aluno

function addAluno() {
    const div = document.getElementById('lista-alunos');
    if (div) {
        const input = document.createElement('input');
        input.name = "alunos[]";
        input.className = "form-control mb-2";
        input.placeholder = "Nome do aluno";
        div.appendChild(input);
    }
}

