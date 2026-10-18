// static/js/planejamento/calendario_bloqueados_print.js
(function () {
  "use strict";

  // ── Data/hora de emissão ──
  const agora = new Date().toLocaleString("pt-BR");
  const dataEmissaoEl = document.getElementById("data-emissao");
  const footerDateTimeEl = document.getElementById("footer-datetime");
  if (dataEmissaoEl) dataEmissaoEl.textContent = "Emissão: " + agora;
  if (footerDateTimeEl) footerDateTimeEl.textContent = "Data/Hora: " + agora;

  // ── Dados injetados pelo template ──
  // Formato: { "YYYY-MM-DD": { cor, icone, tipo, desc } }
  const diasBloqueados = window.diasBloqueados || {};

  // ── Destaque do dia atual ──
  const hoje = new Date().toISOString().slice(0, 10);

  // ── Preenche cada grade mensal ──
  document.querySelectorAll(".cal-days").forEach((container) => {
    const year = parseInt(container.dataset.year, 10);
    const month = parseInt(container.dataset.month, 10); // 1-based

    const firstDay = new Date(year, month - 1, 1).getDay(); // 0=domingo
    const daysInMonth = new Date(year, month, 0).getDate();

    // Células vazias antes do dia 1
    for (let i = 0; i < firstDay; i++) {
      const blank = document.createElement("div");
      blank.className = "cal-day empty";
      container.appendChild(blank);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const wday = new Date(year, month - 1, d).getDay();
      const isWeekend = wday === 0 || wday === 6;
      const ds = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;

      const cell = document.createElement("div");
      cell.className =
        "cal-day" +
        (isWeekend ? " weekend" : "") +
        (ds === hoje ? " today" : "");

      const numEl = document.createElement("div");
      numEl.className = "cal-day-num";
      numEl.textContent = d;
      cell.appendChild(numEl);

      const info = diasBloqueados[ds];
      if (info) {
        const badge = document.createElement("div");
        badge.className = "cal-day-badge";
        badge.style.background = info.cor;
        badge.textContent = info.icone;
        badge.title = info.desc || info.tipo;
        cell.appendChild(badge);
      }

      container.appendChild(cell);
    }
  });

  // Nome do arquivo .pdf
  document.title =
    'dias_sem_aula_{{ periodo.nome_exibicao | replace(" ", "_") }}';
})();
