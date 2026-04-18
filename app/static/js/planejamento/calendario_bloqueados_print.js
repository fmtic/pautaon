// static/js/planejamento/calendario_bloqueados_print.js
(function() {
    'use strict';

    // Injeta data/hora de emissão
    const agora = new Date().toLocaleString('pt-BR');
    const dataEmissaoEl = document.getElementById('data-emissao');
    const footerDateTimeEl = document.getElementById('footer-datetime');
    if (dataEmissaoEl) dataEmissaoEl.textContent = 'Emissão: ' + agora;
    if (footerDateTimeEl) footerDateTimeEl.textContent = 'Data/Hora: ' + agora;

    // Dados de dias bloqueados (serão injetados pelo template via variável global)
    // O template original colocava um objeto "diasBloqueados" diretamente no script.
    // Como agora está em arquivo externo, precisamos que o template defina
    // window.diasBloqueados antes de carregar este script.
    // Exemplo no template:
    // <script>window.diasBloqueados = {{ dias_json | tojson }};</script>

    const diasBloqueados = window.diasBloqueados || {};

    // Data de hoje para destacar
    const hoje = new Date().toISOString().slice(0, 10);

    // Preenche cada grade mensal
    document.querySelectorAll('.month-cells').forEach(container => {
        const year = parseInt(container.dataset.year);
        const month = parseInt(container.dataset.month); // 1-based

        const firstDay = new Date(year, month - 1, 1).getDay(); // 0=domingo
        const daysInMonth = new Date(year, month, 0).getDate();

        // Células vazias antes do dia 1
        for (let i = 0; i < firstDay; i++) {
            const blank = document.createElement('div');
            blank.className = 'day-cell empty';
            container.appendChild(blank);
        }

        for (let d = 1; d <= daysInMonth; d++) {
            const cell = document.createElement('div');
            const wday = new Date(year, month - 1, d).getDay();
            const isWeekend = (wday === 0 || wday === 6);
            const ds = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

            cell.className = 'day-cell' + (isWeekend ? ' weekend' : '') + (ds === hoje ? ' today' : '');

            const numEl = document.createElement('div');
            numEl.className = 'day-num';
            numEl.textContent = d;
            cell.appendChild(numEl);

            if (diasBloqueados[ds]) {
                const b = diasBloqueados[ds];
                const badge = document.createElement('div');
                badge.className = 'day-badge';
                badge.style.background = b.cor;
                badge.textContent = b.icone;
                badge.title = b.desc || b.tipo;
                cell.appendChild(badge);
            }

            container.appendChild(cell);
        }
    });
})();