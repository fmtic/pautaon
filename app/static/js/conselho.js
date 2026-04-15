function adicionarCampoResposta(valor = "") {
    const container = document.getElementById('container-opcoes');
    const div = document.createElement('div');
    div.className = 'input-group mb-2';
    div.innerHTML = `
        <input type="text" class="form-control campo-opcao" value="${valor}" placeholder="Digite uma resposta possível">
        <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.remove()">
            <i class="bi bi-x"></i>
        </button>
    `;
    container.appendChild(div);
}

// Atualizamos a função de editar para carregar os campos dinamicamente
function editarPergunta(id, etapa, tipo, texto, opcoes) {
    document.getElementById('modalTitulo').innerText = "Editar Pergunta";
    document.getElementById('pergunta_id').value = id;
    document.getElementById('pergunta_etapa').value = etapa;
    document.getElementById('pergunta_tipo').value = tipo;
    document.getElementById('pergunta_texto').value = texto;

    // Limpa o container e reconstrói os campos
    const container = document.getElementById('container-opcoes');
    container.innerHTML = "";

    if (opcoes && opcoes.trim() !== "") {
        const lista = opcoes.split(' | '); // Usaremos | como separador interno
        lista.forEach(opt => adicionarCampoResposta(opt));
    }

    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalPergunta')).show();
}

// Antes de enviar, juntamos todos os inputs em uma string só
document.querySelector('form').onsubmit = function () {
    const inputs = document.querySelectorAll('.campo-opcao');
    const valores = Array.from(inputs).map(i => i.value).filter(v => v.trim() !== "");
    document.getElementById('pergunta_opcoes_final').value = valores.join('|');
};

/**
 * Adiciona um novo campo de resposta dinâmica ao modal
 */
function adicionarCampoResposta(valor = "") {
    const container = document.getElementById('container-opcoes');

    // Cria o wrapper do grupo de input
    const div = document.createElement('div');
    div.className = 'input-group mb-2 animate__animated animate__fadeIn'; // Adicionei uma animação simples

    div.innerHTML = `
        <input type="text" class="form-control campo-opcao" value="${valor}" placeholder="Ex: Sim, Não, Às vezes...">
        <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.remove()">
            <i class="bi bi-trash"></i>
        </button>
    `;

    container.appendChild(div);
}

// Este script percorre todos os campos de texto antes do envio. Se encontrar algum vazio, ele avisa qual aluno está incompleto
document.querySelector('form').onsubmit = function (e) {
    let completo = true;
    let nomesIncompletos = [];

    // Verifica cada card de aluno
    document.querySelectorAll('.card').forEach(card => {
        const nomeAluno = card.querySelector('h6')?.innerText;
        if (!nomeAluno) return;

        const campos = card.querySelectorAll('textarea');
        let alunoPreenchido = true;

        campos.forEach(campo => {
            if (campo.value.trim() === "") {
                alunoPreenchido = false;
                completo = false;
            }
        });

        if (!alunoPreenchido) {
            nomesIncompletos.push(nomeAluno);
        }
    });

    if (!completo) {
        e.preventDefault(); // Impede o envio
        alert("Atenção! Os seguintes alunos ainda possuem perguntas sem resposta:\n\n" + nomesIncompletos.join("\n"));
    }
};

// Aguarda o carregamento do DOM para evitar erros de seleção
document.addEventListener('DOMContentLoaded', function () {
    const formConselho = document.querySelector('form[action*="salvar_conselho"]');

    if (formConselho) {
        formConselho.onsubmit = function (e) {
            let pendentes = [];

            // 1. Validar Perguntas da Turma (Geral)
            const camposTurma = document.querySelectorAll('textarea[id^="resp_turma_"]');
            camposTurma.forEach(campo => {
                if (!campo.value.trim()) {
                    if (!pendentes.includes("Avaliação Geral da Turma")) {
                        pendentes.push("Avaliação Geral da Turma");
                    }
                }
            });

            // 2. Validar Perguntas Individuais (Alunos)
            // Buscamos todos os campos que começam com 'resp_' mas não são 'resp_turma'
            const camposAlunos = document.querySelectorAll('textarea[id^="resp_"]:not([id^="resp_turma_"])');

            // Usamos um Set para identificar quais IDs de alunos estão incompletos
            let idsAlunosIncompletos = new Set();

            camposAlunos.forEach(campo => {
                if (!campo.value.trim()) {
                    // O ID do aluno é a segunda parte: resp_IDALUNO_IDPERGUNTA
                    const idAluno = campo.id.split('_')[1];
                    idsAlunosIncompletos.add(idAluno);
                }
            });

            // 3. Mapear IDs para Nomes (Busca o nome dentro do card correspondente)
            idsAlunosIncompletos.forEach(id => {
                // Procuramos o elemento que contém o nome do aluno específico
                // No HTML, o card-header tem o nome. Vamos buscar pelo contexto.
                const campoExemplo = document.getElementById(`resp_${id}_${Object.keys(campo)[0]}` || `[id^="resp_${id}_"]`);
                const cardAluno = document.querySelector(`textarea[id^="resp_${id}_"]`).closest('.card');
                const nomeExibicao = cardAluno.querySelector('h6').innerText;

                pendentes.push(nomeExibicao);
            });

            // 4. Bloqueio e Alerta
            if (pendentes.length > 0) {
                e.preventDefault(); // Impede o envio para o servidor

                // Formata a mensagem de alerta
                let mensagem = "Atenção: O conselho não pode ser salvo porque os seguintes itens estão incompletos:\n\n";
                pendentes.forEach(item => {
                    mensagem += "• " + item + "\n";
                });

                alert(mensagem);

                // Opcional: Rola a tela até o primeiro item pendente
                const primeiroPendente = document.querySelector('textarea:placeholder-shown') || document.querySelector('textarea');
                primeiroPendente.focus();
            }
        };
    }
});

// Garante que o script rode apenas após o HTML carregar
document.addEventListener('DOMContentLoaded', function () {

    // Selecionamos especificamente o formulário dentro do modal de perguntas
    const formPergunta = document.querySelector('#modalPergunta form');

    if (formPergunta) {
        formPergunta.onsubmit = function (e) {
            // 1. Captura todos os inputs de texto das opções
            const inputs = this.querySelectorAll('.campo-opcao');

            // 2. Transforma em array, limpa espaços e remove campos vazios
            const valores = Array.from(inputs)
                .map(i => i.value.trim())
                .filter(v => v !== "");

            // 3. Junta tudo com o separador " | " (espaço + pipe + espaço)
            // Isso é vital para o .split(' | ') que você usa no HTML
            const campoHidden = document.getElementById('pergunta_opcoes_final');

            if (campoHidden) {
                campoHidden.value = valores.join(' | ');
                console.log("Salvando opções:", campoHidden.value);
            }
        };
    }
});

// Sincroniza cada select com seu span de impressão em tempo real
function sincronizarSpans() {
    document.querySelectorAll('.situacao-select').forEach(sel => {
        const span = sel.closest('td').querySelector('.situacao-texto');
        span.innerText = sel.options[sel.selectedIndex].text;
        sel.addEventListener('change', () => {
            span.innerText = sel.options[sel.selectedIndex].text;
        });
    });

    document.querySelectorAll('.proxima-select').forEach(sel => {
        const span = sel.closest('td').querySelector('.proxima-texto');
        span.innerText = sel.options[sel.selectedIndex]?.text || '';
        sel.addEventListener('change', () => {
            span.innerText = sel.options[sel.selectedIndex].text;
        });
    });
}

// Função chamada pelo botão Imprimir
function prepararImpressao() {
    sincronizarSpans(); // garante que os spans estão atualizados
    window.print();
}

// Inicializa ao carregar — dentro do DOMContentLoaded para garantir que os selects existem
document.addEventListener('DOMContentLoaded', function () {
    sincronizarSpans();
});

// Função para exportar a tabela para CSV (Excel)
function exportTableToCSV(filename) {
    var csv = [];
    var rows = document.querySelectorAll("#tabelaFechamento tr");

    for (var i = 0; i < rows.length; i++) {
        var row = [], cols = rows[i].querySelectorAll("td, th");

        for (var j = 0; j < cols.length; j++) {
            let text = "";
            let select = cols[j].querySelector('select');

            if (select) {
                text = select.options[select.selectedIndex].text;
            } else {
                text = cols[j].innerText;
            }

            // Limpeza para não quebrar o CSV
            text = text.replace(/(\r\n|\n|\r)/gm, " ").replace(/,/g, ".");
            row.push('"' + text.trim() + '"');
        }
        csv.push(row.join(","));
    }

    // Download com BOM para Excel aceitar acentos
    var csvFile = new Blob(["\ufeff" + csv.join("\n")], { type: "text/csv;charset=utf-8;" });
    var downloadLink = document.createElement("a");
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.click();
}

// Salvar fechamento via AJAX
function salvarFechamento() {
    const rows = document.querySelectorAll("#tabelaDados tbody tr");
    const dadosParaSalvar = [];

    rows.forEach(row => {
        const alunoId = row.getAttribute('data-aluno-id');
        const selects = row.querySelectorAll('select');

        const situacao = selects[0].value;
        const proximaTurmaId = selects[1].value;

        if (alunoId) {
            dadosParaSalvar.push({
                aluno_id: alunoId,
                situacao: situacao,
                proxima_turma_id: proximaTurmaId || null
            });
        }
    });

    // Envia para a rota do Flask
    fetch(window.location.pathname + "/salvar", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            // Se usar CSRF protection, descomente a linha abaixo:
            // "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content
        },
        body: JSON.stringify({ dados: dadosParaSalvar })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("✅ Fechamento salvo com sucesso!");
            } else {
                alert("❌ Erro ao salvar: " + data.message);
            }
        })
        .catch(error => {
            console.error("Erro:", error);
            alert("Erro na conexão com o servidor.");
        });
}