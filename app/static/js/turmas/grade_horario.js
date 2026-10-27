// static/js/turmas/grade_horario.js
// Módulo compartilhado da agenda por dia (H4c). Usado por nova.js, editar.js e
// pela tela de Cursos da Turma (ofertas.html) — substitui os três mapas de dia
// que existiam duplicados. Regras do contrato:
//   - dias: Segunda–Sábado = índices Python date.weekday() (0–5); SEM domingo;
//   - Date.getDay() do JS (0=domingo) converte por (getDay()+6)%7;
//   - modo padrão replica o par hora_inicio/hora_fim nos dias marcados;
//   - modo personalizado ("Horário por dia") usa um par por dia;
//   - a C.H. aqui é ESTIMATIVA (desconta dias bloqueados nem feriados); o
//     valor autoritativo é o do servidor (definir_grade/cargas do H3c).
//   - H4c: interruptor habilitado só com 2+ dias; voltar a 1 dia volta ao padrão
//     automaticamente; par padrão visível mas esmaecido no modo personalizado.
//   - H4d: regras de estado extraídas em funções puras (estadoLinha,
//     parPadraoAposVolta, valorEspelhado) para teste em node — refactor sem
//     mudança de comportamento.
(function (global) {
    'use strict';

    // Nomes na ordem do weekday Python (0=Segunda ... 5=Sábado).
    const DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];

    /** Date.getDay() (0=Dom) → weekday Python (0=Seg .. 5=Sáb). */
    function getDayParaWeekday(jsDay) {
        return (jsDay + 6) % 7;
    }

    /** Nome do dia no contrato (0–5); null para domingo/desconhecido. */
    function weekdayParaNome(w) {
        return w >= 0 && w <= 5 ? DIAS_SEMANA[w] : null;
    }

    function weekdayValido(w) {
        return Number.isInteger(w) && w >= 0 && w <= 5;
    }

    /**
     * Converte "HH:MM" em minutos desde 00:00. Valor vazio/inválido → null.
     */
    function horaParaMinutos(horaStr) {
        if (!horaStr) return null;
        const partes = String(horaStr).split(':');
        if (partes.length < 2) return null;
        const h = parseInt(partes[0], 10);
        const m = parseInt(partes[1], 10);
        if (isNaN(h) || isNaN(m)) return null;
        return h * 60 + m;
    }

    /**
     * Duração (minutos) de um dia de aula; fim deve ser maior que o início.
     * Função pura — par "HH:MM" (ou minutos) → número ou null.
     */
    function duracaoDiaMinutos(inicio, fim) {
        const minInicio = typeof inicio === 'number' ? inicio : horaParaMinutos(inicio);
        const minFim = typeof fim === 'number' ? fim : horaParaMinutos(fim);
        if (minInicio === null || minFim === null || minFim <= minInicio) return null;
        return minFim - minInicio;
    }

    /**
     * Quantas vezes o weekday `w` (0=Seg) ocorre entre dataInicio e dataFim
     * (datas "YYYY-MM-DD", inclusive). Função pura; datas inválidas → 0.
     */
    function ocorrenciasWeekday(dataInicio, dataFim, w) {
        if (!dataInicio || !dataFim || !weekdayValido(w)) return 0;
        const inicio = new Date(dataInicio + 'T00:00:00');
        const fim = new Date(dataFim + 'T00:00:00');
        if (isNaN(inicio) || isNaN(fim) || fim < inicio) return 0;
        let count = 0;
        const atual = new Date(inicio);
        while (atual <= fim) {
            if (getDayParaWeekday(atual.getDay()) === w) count++;
            atual.setDate(atual.getDate() + 1);
        }
        return count;
    }

    /**
     * Soma a C.H. estimada (minutos): para cada item da grade, a duração
     * daquele dia multiplicada pelas ocorrências daquele weekday no período.
     * `itens`: [{dia, inicio, fim}] (strings "HH:MM"). Função pura.
     */
    function estimarCHMinutos(itens, dataInicio, dataFim) {
        if (!itens || !itens.length) return null;
        let total = 0;
        let valido = false;
        for (const item of itens) {
            const dur = duracaoDiaMinutos(item.inicio, item.fim);
            if (dur === null) continue;
            const ocorre = ocorrenciasWeekday(dataInicio, dataFim, item.dia);
            if (!ocorre) continue;
            total += dur * ocorre;
            valido = true;
        }
        return valido ? total : null;
    }

    /**
     * Formata minutos como carga horária legível.
     * Ex.: 60 → "1h" | 90 → "1h30min" | 0/null → "—"
     */
    function formatarCH(minutos) {
        if (!minutos || minutos <= 0) return '—';
        const h = Math.floor(minutos / 60);
        const m = minutos % 60;
        if (m === 0) return `${h}h`;
        return `${h}h${String(m).padStart(2, '0')}min`;
    }

    /**
     * Lê o weekday (0–5) de um checkbox de dia: atributo data-weekday (H4) ou,
     * em payloads legados, o valor-nome ("Segunda", "qua." ...). Sem domingo.
     */
    function weekdayDoCheckbox(el) {
        const attr = el.getAttribute('data-weekday');
        if (attr !== null && attr !== '') {
            const w = parseInt(attr, 10);
            return weekdayValido(w) ? w : null;
        }
        const idx = nomeParaWeekday(el.value);
        return idx;
    }

    function nomeParaWeekday(nome) {
        const norm = String(nome || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .slice(0, 3);
        const mapa = { seg: 0, ter: 1, qua: 2, qui: 3, sex: 4, sab: 5 };
        return Object.prototype.hasOwnProperty.call(mapa, norm) ? mapa[norm] : null;
    }

    /**
     * H4c: Função pura - verifica se o interruptor pode ser habilitado (2+ dias).
     */
    function podeHabilitarPorDia(diasMarcados) {
        return Array.isArray(diasMarcados) && diasMarcados.length >= 2;
    }

    /**
     * H4d (extração pura do estado renderizado por `atualizaVisivel`, mesmo
     * comportamento): linha de um dia no componente.
     * - esmaecida: dia desmarcado, ou marcado no modo padrão ("igual ao padrão");
     * - campos desabilitados: fora do modo personalizado ou dia desmarcado
     *   (desabilitado ⇒ navegador não envia o campo).
     */
    function estadoLinha(marcado, personalizado) {
        return {
            esmaecida: !marcado || (!personalizado && marcado),
            camposDesabilitados: !personalizado || !marcado,
        };
    }

    /**
     * H4d (extração pura da transição de `atualizaVisivel`, mesmo
     * comportamento): par padrão depois de voltar ao padrão automaticamente.
     * `diasMarcados` com 1 dia → o par desse dia vira o padrão (campo vazio
     * mantém o valor atual do padrão); 0 dias → mantém o último par padrão.
     * `paresPorDia` = {weekday: {inicio, fim}}; `parAtual` = {inicio, fim}.
     */
    function parPadraoAposVolta(diasMarcados, paresPorDia, parAtual) {
        const atual = {
            inicio: (parAtual && parAtual.inicio) || '',
            fim: (parAtual && parAtual.fim) || '',
        };
        if (!Array.isArray(diasMarcados) || diasMarcados.length !== 1) return atual;
        const par = (paresPorDia || {})[diasMarcados[0]] || {};
        return { inicio: par.inicio || atual.inicio, fim: par.fim || atual.fim };
    }

    /**
     * H4d (extração pura de `espelhaPadrao`, mesmo comportamento): valor de um
     * campo por dia no espelhamento — dia marcado no modo padrão recebe o valor
     * do padrão; desmarcado ou em modo personalizado mantém o valor do dia.
     */
    function valorEspelhado(marcado, personalizado, valorPadrao, valorDia) {
        if (personalizado || !marcado) return valorDia;
        return valorPadrao;
    }

    /**
     * Monta a grade a partir de um <form> (mesma lógica do parsing do
     * servidor): modo padrão replica o par padrão; modo personalizado usa o
     * par de cada dia marcado. Devolve [{dia, inicio, fim}] ordenado.
     */
    function montarItensGrade(form) {
        const marcados = [];
        form.querySelectorAll('input[name="dias_semana"]').forEach((el) => {
            if (!el.checked) return;
            const w = weekdayDoCheckbox(el);
            if (w !== null && marcados.indexOf(w) === -1) marcados.push(w);
        });
        marcados.sort((a, b) => a - b);

        const porDiaInput = form.querySelector('input[name="horario_por_dia"]');
        const porDia = !!(porDiaInput && porDiaInput.checked);
        const padraoIni = form.querySelector('input[name="hora_inicio"]');
        const padraoFim = form.querySelector('input[name="hora_fim"]');

        return marcados.map((w) => {
            let inicio = padraoIni ? padraoIni.value : '';
            let fim = padraoFim ? padraoFim.value : '';
            if (porDia) {
                const iniEl = form.querySelector(`input[name="hora_inicio_${w}"]`);
                const fimEl = form.querySelector(`input[name="hora_fim_${w}"]`);
                if (iniEl && iniEl.value) inicio = iniEl.value;
                if (fimEl && fimEl.value) fim = fimEl.value;
            }
            return { dia: w, inicio, fim };
        });
    }

    /**
     * Serializa a grade para comparação "mudou vs. original" (editar.js).
     * Pares incompletos/inválidos entram como texto vazio — a comparação é
     * estrutural, não de validade.
     */
    function serializarGrade(itens) {
        return (itens || [])
            .map((i) => `${i.dia}:${i.inicio || ''}-${i.fim || ''}`)
            .join('|');
    }

    /**
     * Inverso de serializarGrade: "0:08:00-11:00|2:08:00-11:00" (formato do
     * servidor, window.gradeOriginal) → [{dia, inicio, fim}]. Partes
     * malformadas são descartadas. Função pura.
     */
    function deserializarGrade(serial) {
        return String(serial || '')
            .split('|')
            .filter(Boolean)
            .map((parte) => {
                const m = parte.match(/^(\d+):(\d{2}:\d{2})-(\d{2}:\d{2})$/);
                if (!m) return null;
                return { dia: parseInt(m[1], 10), inicio: m[2], fim: m[3] };
            })
            .filter((i) => i !== null);
    }

    // ------------------------------------------------------------------
    // Componente de formulário (DOM)
    // ------------------------------------------------------------------

    /**
     * Inicia o componente de agenda em um <form>:
     *  - interruptor "Horário por dia" ([data-grade-switch]);
     *  - linhas por dia ([data-grade-dia]) com hora_inicio_<w>/hora_fim_<w>;
     *  - par padrão ([data-grade-padrao]) com hora_inicio/hora_fim;
     *  - regra de 2+ dias para habilitar o interruptor;
     *  - volta automática ao padrão ao desmarcar até 1 dia;
     *  - pré-preenchimento dos dias marcados com o par padrão;
     *  - confirmação ao desligar quando há valores diferentes do padrão;
     *  - C.H. estimativa (#ch_aula_display/#ch_total_display se existirem).
     *
     * `opcoes.getDatas` devolve [inicio, fim] em "YYYY-MM-DD" (ou [null,null]).
     * `opcoes.bloqueado` pula toda a interação (agenda readonly de 2+ ofertas).
     */
    function initGrade(form, opcoes) {
        if (!form) return;
        opcoes = opcoes || {};
        if (opcoes.bloqueado) return;

        const switchInput = form.querySelector('[data-grade-switch]');
        const padraoIni = form.querySelector('input[name="hora_inicio"]');
        const padraoFim = form.querySelector('input[name="hora_fim"]');
        const padraoBlocos = Array.from(form.querySelectorAll('[data-grade-padrao]'));
        const blocos = Array.from(form.querySelectorAll('[data-grade-dia]'));
        const switchHelp = switchInput ? form.querySelector(`#${switchInput.id}_switch_help`) : null;

        const diasMarcados = () =>
            Array.from(form.querySelectorAll('input[name="dias_semana"]'))
                .filter((el) => el.checked)
                .map(weekdayDoCheckbox)
                .filter((w) => w !== null);

        function blocoDe(w) {
            return blocos.find((b) => parseInt(b.getAttribute('data-grade-dia'), 10) === w) || null;
        }

        function preenchePadrao() {
            if (!switchInput || !switchInput.checked) return;
            diasMarcados().forEach((w) => {
                const bloco = blocoDe(w);
                if (!bloco) return;
                const ini = bloco.querySelector(`input[name="hora_inicio_${w}"]`);
                const fim = bloco.querySelector(`input[name="hora_fim_${w}"]`);
                if (ini && !ini.value && padraoIni && padraoIni.value) ini.value = padraoIni.value;
                if (fim && !fim.value && padraoFim && padraoFim.value) fim.value = padraoFim.value;
            });
        }

        function espelhaPadrao() {
            // No modo padrão, espelha o par padrão nos campos por dia (marcados)
            if (switchInput && switchInput.checked) return;
            const marcados = diasMarcados();
            blocos.forEach((bloco) => {
                const w = parseInt(bloco.getAttribute('data-grade-dia'), 10);
                const marcado = marcados.indexOf(w) !== -1;
                const ini = bloco.querySelector(`input[name="hora_inicio_${w}"]`);
                const fim = bloco.querySelector(`input[name="hora_fim_${w}"]`);
                // H4d: valorEspelhado é a regra pura (mesmo efeito de antes —
                // dia desmarcado recebe o próprio valor de volta, no-op).
                if (ini && padraoIni) ini.value = valorEspelhado(marcado, false, padraoIni.value, ini.value);
                if (fim && padraoFim) fim.value = valorEspelhado(marcado, false, padraoFim.value, fim.value);
            });
        }

        function temDiferencaPorDia() {
            // Algum dia marcado cujo par difere do par padrão preenchido?
            if (!padraoIni || !padraoFim) return false;
            return diasMarcados().some((w) => {
                const bloco = blocoDe(w);
                if (!bloco) return false;
                const ini = bloco.querySelector(`input[name="hora_inicio_${w}"]`);
                const fim = bloco.querySelector(`input[name="hora_fim_${w}"]`);
                const temValor = (ini && ini.value) || (fim && fim.value);
                if (!temValor) return false;
                return (ini && ini.value) !== padraoIni.value || (fim && fim.value) !== padraoFim.value;
            });
        }

        function atualizaVisivel() {
            const on = !!(switchInput && switchInput.checked);
            const marcados = diasMarcados();
            const nMarcados = marcados.length;

            // Habilita/desabilita o interruptor conforme número de dias (H4c)
            if (switchInput) {
                const podeHabilitar = podeHabilitarPorDia(marcados);
                switchInput.disabled = !podeHabilitar;
                if (switchHelp) {
                    switchHelp.textContent = podeHabilitar
                        ? 'Definir horários diferentes para cada dia marcado.'
                        : 'Marque 2 ou mais dias para definir horários diferentes.';
                }
                // H4c: voltar automaticamente ao padrão ao desmarcar até 1 dia
                if (on && !podeHabilitar) {
                    switchInput.checked = false;
                    // O par do dia restante vira o par padrão (0 dias mantém o
                    // último par) — regra pura em parPadraoAposVolta (H4d).
                    if (nMarcados === 1) {
                        const w = marcados[0];
                        const bloco = blocoDe(w);
                        if (bloco) {
                            const ini = bloco.querySelector(`input[name="hora_inicio_${w}"]`);
                            const fim = bloco.querySelector(`input[name="hora_fim_${w}"]`);
                            const novo = parPadraoAposVolta(
                                marcados,
                                { [w]: { inicio: ini ? ini.value : '', fim: fim ? fim.value : '' } },
                                { inicio: padraoIni ? padraoIni.value : '', fim: padraoFim ? padraoFim.value : '' },
                            );
                            if (padraoIni && novo.inicio) padraoIni.value = novo.inicio;
                            if (padraoFim && novo.fim) padraoFim.value = novo.fim;
                        }
                    }
                }
            }

            // Par padrão: visível mas esmaecido/desabilitado no modo personalizado
            padraoBlocos.forEach((bloco) => {
                bloco.classList.toggle('opacity-50', on);
                bloco.querySelectorAll('input').forEach((i) => {
                    i.disabled = on;
                });
            });

            // Linhas por dia: estado conforme modo e marcação (regra pura H4d)
            blocos.forEach((bloco) => {
                const w = parseInt(bloco.getAttribute('data-grade-dia'), 10);
                const marcado = marcados.indexOf(w) !== -1;
                const linha = estadoLinha(marcado, on);
                bloco.classList.toggle('opacity-50', linha.esmaecida);
                bloco.querySelectorAll('input').forEach((i) => {
                    i.disabled = linha.camposDesabilitados;
                });
            });
        }

        function recalculaCH() {
            const chAula = form.querySelector('#ch_aula_display');
            const chTotal = form.querySelector('#ch_total_display');
            if (!chAula && !chTotal) return;
            const itens = montarItensGrade(form);
            let minutosAula = null;
            let aulaUnica = true;
            let duracoes = [];
            itens.forEach((i) => {
                const dur = duracaoDiaMinutos(i.inicio, i.fim);
                if (dur !== null) {
                    duracoes.push(dur);
                    if (minutosAula === null) minutosAula = dur;
                }
            });
            if (duracoes.length) {
                aulaUnica = duracoes.every((d) => d === duracoes[0]);
                minutosAula = aulaUnica ? duracoes[0] : null;
            }
            if (chAula) {
                chAula.textContent = minutosAula !== null ? formatarCH(minutosAula) : (duracoes.length ? 'varia' : '—');
            }
            if (chTotal) {
                let ini = null;
                let fim = null;
                if (opcoes.getDatas) {
                    const datas = opcoes.getDatas() || [];
                    ini = datas[0];
                    fim = datas[1];
                }
                const total = estimarCHMinutos(itens, ini, fim);
                chTotal.textContent = total !== null ? `${formatarCH(total)} (estimativa)` : '—';
            }
        }

        if (switchInput) {
            switchInput.addEventListener('change', () => {
                if (!switchInput.checked && temDiferencaPorDia()) {
                    // Voltar ao padrão perde as diferenças por dia — confirmar.
                    const ok = global.confirm(
                        'Ao desligar "Horário por dia" os dias voltam para o ' +
                        'horário padrão e as diferenças digitadas são perdidas.\nContinuar?'
                    );
                    if (!ok) {
                        switchInput.checked = true;
                        return;
                    }
                }
                if (switchInput.checked) {
                    // Ao ligar, pré-preenche os pares por dia com o par padrão
                    preenchePadrao();
                }
                atualizaVisivel();
                recalculaCH();
            });
        }

        const alvos = Array.from(
            form.querySelectorAll('input[name="dias_semana"], input[name="hora_inicio"], input[name="hora_fim"]')
        );
        blocos.forEach((b) => b.querySelectorAll('input').forEach((i) => alvos.push(i)));
        alvos.forEach((el) => {
            el.addEventListener('change', () => {
                espelhaPadrao();
                atualizaVisivel();
                recalculaCH();
            });
            el.addEventListener('input', recalculaCH);
        });

        // Estado inicial já preenchido (pré-render do servidor) → estimativa
        // visível assim que a página carrega, como nas telas antigas.
        espelhaPadrao();
        atualizaVisivel();
        recalculaCH();

        // API mínima para o arquivo da página (editar.js reutiliza).
        return { recalculaCH, atualizaVisivel, montarItens: () => montarItensGrade(form) };
    }

    const GradeHorario = {
        DIAS_SEMANA,
        getDayParaWeekday,
        weekdayParaNome,
        weekdayValido,
        weekdayDoCheckbox,
        nomeParaWeekday,
        horaParaMinutos,
        duracaoDiaMinutos,
        ocorrenciasWeekday,
        estimarCHMinutos,
        formatarCH,
        podeHabilitarPorDia,
        estadoLinha,
        parPadraoAposVolta,
        valorEspelhado,
        montarItensGrade,
        serializarGrade,
        deserializarGrade,
        initGrade,
    };

    global.GradeHorario = GradeHorario;
    // Exposição para teste em node (PASSO 4) sem window.
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = GradeHorario;
    }
})(typeof window !== 'undefined' ? window : globalThis);
