// static/js/turmas/editar.js
// Mapa de dias, funções de C.H. e componente "Horário diferente por dia" vivem
// no módulo compartilhado grade_horario.js (H4). Aqui ficam apenas os ajustes
// específicos da tela: centros de custo por período, a confirmação de
// limpeza de lançamentos quando a agenda (ou as datas) mudou e a confirmação
// da troca de professor da oferta.
(function () {
    const periodosCentros = window.periodosCentrosEdit || {};
    const periodoSelect = document.querySelector('select[name="periodo_letivo_id"]');
    const centroSelect = document.getElementById('centro_custo_select');
    const centroHelp = document.getElementById('centro_edit_help');
    const form = document.querySelector('form');
    const originalInicio = document.getElementById('original_data_inicio');
    const originalFim = document.getElementById('original_data_fim');
    const limparInput = document.getElementById('limpar_lancamentos');
    const temLancamentos = window.turmaTemLancamentos || false;
    const ofertasBloqueadas = window.turmaOfertasBloqueadas || false;
    const gradeOriginal = window.gradeOriginal || '';
    const inputInicio = document.querySelector('input[name="data_inicio"]');
    const inputFim = document.querySelector('input[name="data_fim"]');

    function atualizarCentros() {
        if (!centroSelect) return;
        const periodoId = periodoSelect ? periodoSelect.value : null;
        const centros = (periodoId && periodosCentros[periodoId]) ? periodosCentros[periodoId] : [];
        centroSelect.innerHTML = '';
        if (centros.length) {
            centroSelect.disabled = false;
            centros.forEach(centro => {
                const opt = document.createElement('option');
                opt.value = centro;
                opt.textContent = centro;
                centroSelect.appendChild(opt);
            });
            if (centroHelp) centroHelp.textContent = 'Centros do período selecionado.';
        } else {
            centroSelect.disabled = true;
            if (centroHelp) centroHelp.textContent = 'Nenhum centro de custo definido para o período selecionado.';
        }
    }

    /** Datas efetivas do formulário, para a estimativa de C.H. do módulo. */
    function datasAtual() {
        return [
            inputInicio ? inputInicio.value || null : null,
            inputFim ? inputFim.value || null : null,
        ];
    }

    // C.H. somente leitura (agenda bloqueada com 2+ ofertas): sem interação
    // com o componente, mas a estimativa inicial continua visível — vem de
    // window.gradeOriginal (projeção da turma) + datas do formulário.
    function exibirEstimativaSomenteLeitura() {
        const GH = window.GradeHorario;
        if (!GH) return;
        const chAula = document.getElementById('ch_aula_display');
        const chTotal = document.getElementById('ch_total_display');
        const itens = GH.deserializarGrade(gradeOriginal);
        if (!chAula || !chTotal || !itens.length) return;
        const duracoes = itens
            .map((i) => GH.duracaoDiaMinutos(i.inicio, i.fim))
            .filter((d) => d !== null);
        if (duracoes.length) {
            const uniforme = duracoes.every((d) => d === duracoes[0]);
            chAula.textContent = uniforme ? GH.formatarCH(duracoes[0]) : 'varia';
        }
        const datas = datasAtual();
        const total = GH.estimarCHMinutos(itens, datas[0], datas[1]);
        chTotal.textContent = total !== null ? `${GH.formatarCH(total)} (estimativa)` : '—';
    }

    if (form) {
        if (ofertasBloqueadas) {
            exibirEstimativaSomenteLeitura();
        } else {
            // Componente de agenda (H4): interruptor, blocos por dia,
            // pré-preenchimento e C.H. estimativa — tudo no módulo.
            GradeHorario.initGrade(form, { getDatas: datasAtual });
        }
    }

    function handleSubmit(event) {
        if (ofertasBloqueadas) {
            return;
        }
        if (!temLancamentos || !form || !originalInicio || !originalFim || !limparInput) {
            return;
        }
        if (!window.GradeHorario) {
            return;
        }

        // H4: a mudança de agenda é comparada pela grade serializada — isso
        // captura também diferenças por dia no modo personalizado.
        const novaGrade = GradeHorario.serializarGrade(
            GradeHorario.montarItensGrade(form)
        );
        const agendaMudou = novaGrade !== gradeOriginal;
        const novoInicio = inputInicio ? inputInicio.value || '' : '';
        const novoFim = inputFim ? inputFim.value || '' : '';
        const inicioMudou = novoInicio !== originalInicio.value;
        const fimMudou = novoFim !== originalFim.value;

        if (agendaMudou || inicioMudou || fimMudou) {
            const confirmMsg =
                'Você alterou os dias, as datas ou o horário da turma.\n' +
                'Isso irá limpar os lançamentos existentes e recalcular a carga horária deste curso nesta turma.\n' +
                'Deseja continuar?';
            if (!confirm(confirmMsg)) {
                event.preventDefault();
                return;
            }
            limparInput.value = '1';
        }
    }

    if (periodoSelect) {
        periodoSelect.addEventListener('change', atualizarCentros);
        atualizarCentros();
    }

    if (form) {
        form.addEventListener('submit', handleSubmit);
    }

    // E2/G1: a oferta é a fonte do professor. Trocar o professor de uma oferta
    // com lançamentos gravados exige confirmação (mesmo padrão da limpeza de
    // lançamentos acima); o servidor repete a checagem com precisão.
    const confirmarTrocaInput = document.getElementById('confirmar_troca_professor');
    const professorSelect = document.querySelector('select[name="professor_id"]');

    function handleTrocaProfessor(event) {
        if (!form || !confirmarTrocaInput || !professorSelect) return;
        if (ofertasBloqueadas || !temLancamentos) return;
        if (professorSelect.value === (professorSelect.dataset.professorOriginal || '')) return;
        if (!professorSelect.value) return;  // esvaziar: recusado pelo servidor
        const confirmMsg =
            'Você trocou o professor responsável desta oferta.\n' +
            'Os lançamentos já feitos continuam atribuídos a quem os lançou.\n' +
            'Deseja continuar?';
        if (!confirm(confirmMsg)) {
            event.preventDefault();
            return;
        }
        confirmarTrocaInput.value = '1';
    }

    if (professorSelect && confirmarTrocaInput) {
        // Volta a exigir confirmação a cada nova escolha não confirmada.
        professorSelect.addEventListener('change', () => {
            confirmarTrocaInput.value = '0';
        });
        form.addEventListener('submit', handleTrocaProfessor);
    }
})();
