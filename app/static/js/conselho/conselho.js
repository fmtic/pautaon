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

// Carrega o modal de edição a partir do botão clicado.
// Os dados vêm de atributos data-* (autoescapados pelo Jinja no template), o que
// evita a quebra do onclick quando texto/opções contêm aspas e garante os valores
// reais dos enums (etapa/tipo) que alimentam os <select> do formulário.
function editarPergunta(btn) {
    // Pede confirmação antes de abrir a edição
    if (!confirm("Deseja editar as informações desta pergunta?")) {
        return; // Cancela a ação se o usuário clicar em "Não/Cancelar"
    }

    const d = btn.dataset;

    document.getElementById('modalTitulo').innerText = "Editar Pergunta";
    document.getElementById('pergunta_id').value = d.id;
    document.getElementById('pergunta_etapa').value = d.etapa;
    document.getElementById('pergunta_tipo').value = d.tipo;
    document.getElementById('pergunta_texto').value = d.texto;

    // Limpa o container e reconstrói os campos
    const container = document.getElementById('container-opcoes');
    container.innerHTML = "";

    if (d.opcoes && d.opcoes.trim() !== "") {
        const lista = d.opcoes.split(' | '); // Usaremos | como separador interno
        lista.forEach(opt => adicionarCampoResposta(opt));
    }

    bootstrap.Modal.getOrCreateInstance(document.getElementById('modalPergunta')).show();
}

/**
 * Adiciona um novo campo de resposta dinâmica ao modal
 */
function adicionarCampoResposta(valor = "") {
    const container = document.getElementById('container-opcoes');

    // Wrapper do grupo de input
    const div = document.createElement('div');
    div.className = 'input-group mb-2 animate__animated animate__fadeIn';

    // Input criado via propriedade .value (e não interpolado no HTML), para que
    // aspas dentro da opção não quebrem o markup nem gerem campos indevidos.
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control campo-opcao';
    input.placeholder = 'Ex: Sim, Não, Às vezes...';
    input.value = valor;

    // Botão de remover a própria opção
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline-danger';
    btn.type = 'button';
    btn.title = 'Remover Opção';
    btn.innerHTML = '<i class="bi bi-trash3"></i>';
    btn.addEventListener('click', () => div.remove());

    div.appendChild(input);
    div.appendChild(btn);
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

// Token CSRF exposto pelo base.html (mesma fonte dos demais fetch do projeto).
// Sem ele o POST JSON do fechamento leva 400 do CSRFProtect.
function tokenCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? (meta.getAttribute('content') || '') : '';
}

// Salvar fechamento via AJAX
function salvarFechamento() {
    // D5.2: a tabela do fechamento é #tabelaFechamento (o seletor antigo
    // #tabelaDados não existia na tela e o POST saía vazio) e o salvamento é
    // POR OFERTA — a oferta em uso vem de data-oferta-id na própria tabela.
    const tabela = document.getElementById('tabelaFechamento');
    if (!tabela) return;

    const ofertaId = tabela.getAttribute('data-oferta-id');
    if (!ofertaId) {
        alert("Selecione o curso (oferta) antes de salvar o fechamento.");
        return;
    }

    const rows = tabela.querySelectorAll('tbody tr');
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
            "X-CSRFToken": tokenCsrf(),
        },
        body: JSON.stringify({ oferta_id: parseInt(ofertaId, 10), dados: dadosParaSalvar })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(response.status === 400
                ? "Sessão expirada ou token de segurança inválido. Recarregue a página e tente novamente."
                : "Erro HTTP " + response.status);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert("✅ Fechamento salvo com sucesso!");
        } else {
            alert("❌ Erro ao salvar: " + data.message);
        }
    })
    .catch(error => {
        console.error("Erro:", error);
        alert("Erro ao salvar o fechamento: " + error.message);
    });
}