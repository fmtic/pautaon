/**
 * Função para confirmar a exclusão de uma pergunta
 * Pode ser chamada no HTML do botão form: onsubmit="return confirmarExclusao(event)"
 */
function confirmarExclusao(event) {
    if (!confirm("⚠️ Tem certeza que deseja excluir esta pergunta? Esta ação não poderá ser desfeita.")) {
        if (event) event.preventDefault();
        return false;
    }
    return true;
}

// Atualizamos a função de editar para pedir confirmação e carregar os campos dinamicamente
function editarPergunta(id, etapa, tipo, texto, opcoes) {
    // Pede confirmação antes de abrir a edição
    if (!confirm("Deseja editar as informações desta pergunta?")) {
        return; // Cancela a ação se o usuário clicar em "Não/Cancelar"
    }

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
        <button class="btn btn-outline-danger" type="button" onclick="this.parentElement.remove()" title="Remover Opção">
            <i class="bi bi-trash3"></i>
        </button>
    `;

    container.appendChild(div);
}

// Limpar o formulário quando clicar em "Nova Pergunta"
function limparFormulario() {
    document.getElementById('modalTitulo').innerText = "Nova Pergunta";
    document.getElementById('pergunta_id').value = "";
    document.getElementById('pergunta_texto').value = "";
    document.getElementById('container-opcoes').innerHTML = "";
}

// -------------------------------------------------------------------------
// EVENTOS DOM CONTENT LOADED (Garante que o HTML carregou antes de aplicar)
// -------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function () {

    // 1. LÓGICA DO MODAL DE PERGUNTAS (Juntar opções)
    const formPergunta = document.querySelector('#modalPergunta form');
    if (formPergunta) {
        formPergunta.onsubmit = function (e) {
            // Captura todos os inputs de texto das opções
            const inputs = this.querySelectorAll('.campo-opcao');

            // Transforma em array, limpa espaços e remove campos vazios
            const valores = Array.from(inputs)
                .map(i => i.value.trim())
                .filter(v => v !== "");

            // Junta tudo com o separador " | " (espaço + pipe + espaço)
            const campoHidden = document.getElementById('pergunta_opcoes_final');
            if (campoHidden) {
                campoHidden.value = valores.join(' | ');
            }
        };
    }

    // 2. LÓGICA DE SALVAR CONSELHO (Validação de campos vazios)
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
            const camposAlunos = document.querySelectorAll('textarea[id^="resp_"]:not([id^="resp_turma_"])');
            let idsAlunosIncompletos = new Set();

            camposAlunos.forEach(campo => {
                if (!campo.value.trim()) {
                    const idAluno = campo.id.split('_')[1];
                    idsAlunosIncompletos.add(idAluno);
                }
            });

            // 3. Mapear IDs para Nomes
            idsAlunosIncompletos.forEach(id => {
                const cardAluno = document.querySelector(`textarea[id^="resp_${id}_"]`).closest('.card');
                if (cardAluno) {
                    const nomeExibicao = cardAluno.querySelector('h6').innerText;
                    pendentes.push(nomeExibicao);
                }
            });

            // 4. Bloqueio e Alerta
            if (pendentes.length > 0) {
                e.preventDefault(); // Impede o envio
                let mensagem = "Atenção: O conselho não pode ser salvo porque os seguintes itens estão incompletos:\n\n";
                pendentes.forEach(item => { mensagem += "• " + item + "\n"; });
                alert(mensagem);

                // Rola a tela até o primeiro item pendente
                const primeiroPendente = document.querySelector('textarea:placeholder-shown') || document.querySelector('textarea');
                if(primeiroPendente) primeiroPendente.focus();
            }
        };
    }

    // Inicializa a sincronização de spans se estiver na tela de impressão
    sincronizarSpans();
});

// -------------------------------------------------------------------------
// FUNÇÕES DE IMPRESSÃO, EXPORTAÇÃO E FECHAMENTO
// -------------------------------------------------------------------------

// Sincroniza cada select com seu span de impressão em tempo real
function sincronizarSpans() {
    document.querySelectorAll('.situacao-select').forEach(sel => {
        const span = sel.closest('td').querySelector('.situacao-texto');
        if (span) {
            span.innerText = sel.options[sel.selectedIndex].text;
            sel.addEventListener('change', () => { span.innerText = sel.options[sel.selectedIndex].text; });
        }
    });

    document.querySelectorAll('.proxima-select').forEach(sel => {
        const span = sel.closest('td').querySelector('.proxima-texto');
        if (span) {
            span.innerText = sel.options[sel.selectedIndex]?.text || '';
            sel.addEventListener('change', () => { span.innerText = sel.options[sel.selectedIndex].text; });
        }
    });
}

// Função chamada pelo botão Imprimir
function prepararImpressao() {
    sincronizarSpans(); 
    window.print();
}

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

        if (alunoId && selects.length >= 2) {
            const situacao = selects[0].value;
            const proximaTurmaId = selects[1].value;

            dadosParaSalvar.push({
                aluno_id: alunoId,
                situacao: situacao,
                proxima_turma_id: proximaTurmaId || null
            });
        }
    });

    fetch(window.location.pathname + "/salvar", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
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