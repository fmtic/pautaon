console.log("app rodando");

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

