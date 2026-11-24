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
            const camposTurma = document.querySelectorAll('textarea[id^="resp_turma_"], input[type="hidden"][id^="resp_turma_"]');
            camposTurma.forEach(campo => {
                if (!campo.value.trim()) {
                    if (!pendentes.includes("Avaliação Geral da Turma")) {
                        pendentes.push("Avaliação Geral da Turma");
                    }
                }
            });

            // 2. Validar Perguntas Individuais (Alunos)
            const camposAlunos = document.querySelectorAll('textarea[id^="resp_"]:not([id^="resp_turma_"]), input[type="hidden"][id^="resp_"]:not([id^="resp_turma_"])');
            let idsAlunosIncompletos = new Set();

            camposAlunos.forEach(campo => {
                if (!campo.value.trim()) {
                    const idAluno = campo.id.split('_')[1];
                    idsAlunosIncompletos.add(idAluno);
                }
            });

            // 3. Mapear IDs para Nomes
            idsAlunosIncompletos.forEach(id => {
                const cardAluno = document.querySelector(`textarea[id^="resp_${id}_"], input[type="hidden"][id^="resp_${id}_"]`).closest('.card');
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

    // AJ22: habilita/popula os selects de nível do fechamento (inicia já
    // com a pré-seleção do servidor, se houver).
    ligarNiveisFechamento();
});

// -------------------------------------------------------------------------
// FUNÇÕES DE IMPRESSÃO, EXPORTAÇÃO E FECHAMENTO
// -------------------------------------------------------------------------

// Sincroniza cada select com seu span de impressão em tempo real
function sincronizarSpans() {
    // AJ30: "Não definido" (value="") é ausência — na impressão aparece "—",
    // o mesmo fallback do template, nunca o rótulo da option.
    const textoImpressao = sel => {
        const opcao = sel.options[sel.selectedIndex];
        const api = window.autosaveFechamento;
        return api && api.textoImpressaoSituacao
            ? api.textoImpressaoSituacao(sel.value, opcao ? opcao.text : '')
            : (sel.value ? (opcao ? opcao.text : '') : '—');
    };
    document.querySelectorAll('.situacao-select').forEach(sel => {
        const span = sel.closest('td').querySelector('.situacao-texto');
        if (span) {
            span.innerText = textoImpressao(sel);
            sel.addEventListener('change', () => { span.innerText = textoImpressao(sel); });
        }
    });

    document.querySelectorAll('.proxima-select').forEach(sel => {
        const span = sel.closest('td').querySelector('.proxima-texto');
        if (span) {
            // AJ22-B: quando nada está gravado no novo campo, a linha pode
            // ter um valor LEGADO (opcao_proxima_turma) vindo de data-legado;
            // ele aparece na impressão sem nível.
            const textoAtual = () => {
                if (sel.value) return sel.options[sel.selectedIndex]?.text || '';
                return sel.dataset.legado || '';
            };
            span.innerText = textoAtual();
            sel.addEventListener('change', () => { span.innerText = textoAtual(); });
        }
    });

    document.querySelectorAll('.nivel-select').forEach(sel => {
        const span = sel.closest('td').querySelector('.nivel-texto');
        if (span) {
            span.innerText = sel.options[sel.selectedIndex]?.text || '';
            sel.addEventListener('change', () => { span.innerText = sel.options[sel.selectedIndex].text; });
        }
    });
}

// -------------------------------------------------------------------------
// AJ22 — Nível de destino do próximo curso (fechamento)
// -------------------------------------------------------------------------
// NIVEL_DATA ({curso_id: [{id, nome, ativo}]}) é embutido pela página de
// fechamento; nas demais telas do conselho não existe e a lógica fica
// inerte.

function temDadosNivel() {
    return typeof NIVEL_DATA !== 'undefined';
}

// Reconstrói as opções do select de nível da linha conforme o CURSO
// escolhido: só níveis daquele curso; o nível já gravado inativo permanece
// visível com etiqueta "(inativo)" (F2). Curso sem níveis → select
// desabilitado com "Nível não cadastrado"; sem curso → "Não se aplica".
function atualizarNivelDaLinha(row) {
    const proxima = row.querySelector('.proxima-select');
    const nivelSel = row.querySelector('.nivel-select');
    if (!proxima || !nivelSel || !temDadosNivel()) return;

    const cursoId = proxima.value;
    const nivelAtual = nivelSel.getAttribute('data-nivel-atual') || '';

    // Trocar/limpar o curso limpa o nível.
    nivelSel.innerHTML = '<option value="">Não se aplica</option>';
    nivelSel.disabled = true;
    sincronizarSpanNivel(nivelSel);
    if (!cursoId) return;

    const niveis = (NIVEL_DATA[cursoId] || []);
    const opcoes = niveis.filter(n => n.ativo || String(n.id) === String(nivelAtual));

    if (!opcoes.length) {
        nivelSel.options[0].text = 'Nível não cadastrado';
        sincronizarSpanNivel(nivelSel);
        return;
    }

    opcoes.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n.id;
        opt.innerText = n.nome + (n.ativo ? '' : ' (inativo)');
        if (String(n.id) === String(nivelAtual)) opt.selected = true;
        nivelSel.appendChild(opt);
    });
    nivelSel.disabled = false;
    sincronizarSpanNivel(nivelSel);
}

function sincronizarSpanNivel(nivelSel) {
    const span = nivelSel.closest('td').querySelector('.nivel-texto');
    if (span) span.innerText = nivelSel.options[nivelSel.selectedIndex]?.text || '';
}

function ligarNiveisFechamento() {
    const tabela = document.getElementById('tabelaFechamento');
    if (!tabela || !temDadosNivel()) return;
    tabela.querySelectorAll('tbody tr').forEach(row => {
        const proxima = row.querySelector('.proxima-select');
        if (proxima) {
            proxima.addEventListener('change', () => atualizarNivelDaLinha(row));
        }
        // Respeita a pré-seleção vinda do servidor (edição de fechamento).
        atualizarNivelDaLinha(row);
    });
}

// Função chamada pelo botão Imprimir
function prepararImpressao() {
    sincronizarSpans();
    window.print();
}

// AJ23: Ctrl+P / menu do navegador não passa pelo botão. O beforeprint
// reaplica os spans com o valor ATUAL dos selects (inclusive escolhas ainda
// não salvas), sem consultar o legado quando há uma seleção vigente.
window.addEventListener('beforeprint', sincronizarSpans);

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

// AJ30: confirmação do encerramento do conselho. A contagem de alunos sem
// situação final vem do servidor (uma consulta em lote, sem N+1) e é exibida
// ANTES do POST; o gestor pode encerrar mesmo assim.
function confirmarEncerramento(event, pendentes) {
    const total = Number(pendentes) || 0;
    const mensagem = total > 0
        ? total + ' aluno(s) sem situação final definida. Deseja encerrar o conselho mesmo assim?'
        : 'Deseja encerrar o conselho desta oferta?';
    if (!confirm(mensagem)) {
        if (event) event.preventDefault();
        return false;
    }
    return true;
}


// -------------------------------------------------------------------------
// FUNÇÕES DE IMPRESSÃO, EXPORTAÇÃO E FECHAMENTO
// -------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', function() {
    const alunos = document.querySelectorAll('.aluno-card');
    if (alunos.length === 0) return;
    
    let currentIndex = 0;
    const total = alunos.length;

    // AJ21: o resumo abre "Editar" com #aluno-<id>. Seleciona o card do
    // aluno na paginação em vez de deixar sempre o primeiro visível.
    const alunoAncora = (window.location.hash || '').match(/^#aluno-(\d+)$/);
    if (alunoAncora) {
        const indiceAncora = Array.from(alunos).findIndex(
            card => card.dataset.alunoId === alunoAncora[1]
        );
        if (indiceAncora >= 0) currentIndex = indiceAncora;
    }
    
    const btnPrev = document.getElementById('btnPrev');
    const btnNext = document.getElementById('btnNext');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressPercent = document.getElementById('progressPercent');

    function updateView() {
        // Mostra apenas o card do aluno atual
        alunos.forEach((card, index) => {
            card.style.display = index === currentIndex ? 'block' : 'none';
        });
        
        // Atualiza a exibição dos botões
        if (btnPrev) btnPrev.style.display = currentIndex === 0 ? 'none' : 'inline-block';
        if (btnNext) btnNext.style.display = currentIndex === total - 1 ? 'none' : 'inline-block';
        
        // Atualiza a barra de progresso
        const percent = ((currentIndex + 1) / total) * 100;
        if (progressBar) {
            progressBar.style.width = percent + '%';
            progressBar.setAttribute('aria-valuenow', percent);
        }
        if (progressText) {
            progressText.innerText = `Aluno ${currentIndex + 1} de ${total}`;
        }
        if (progressPercent) {
            progressPercent.innerText = Math.round(percent) + '%';
        }
    }

    // Função de navegação exposta para o HTML
    window.mudarAluno = function(direction) {
        currentIndex += direction;
        if (currentIndex < 0) currentIndex = 0;
        if (currentIndex >= total) currentIndex = total - 1;
        
        updateView();
        
        // Rola a tela suavemente para a barra de progresso no topo da página
        const container = document.getElementById('progressContainer');
        if (container) {
            container.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    updateView(); // Inicializa o layout
});