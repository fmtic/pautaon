// Informa os dias em que não haverá aula, seja por feriado, reunião de pais,
// atividade pedagógica ou interna, manutenção, etc.

(function () {
  "use strict";

  // Obtém a configuração injetada pelo template
  const config = window.calendarioConfig || {};
  const READONLY = config.readonly === true;
  const PERIODO_ID = config.periodoId;
  const PERIODO_INICIO = config.dataInicio;
  const PERIODO_FIM = config.dataFim;
  const DIAS_INICIAIS = config.dias || [];
  const TURMAS = config.turmas || [];
  const EXCECOES_INICIAIS = config.excecoes || {};

  const TIPOS = {
    FERIADO: { label: "Feriado", cor: "#dc3545", icone: "F" },
    ATIVIDADE_PEDAGOGICA: {
      label: "At. Pedagógica",
      cor: "#0d6efd",
      icone: "A",
    },
    REUNIAO_PAIS: { label: "Reunião de Pais", cor: "#6f42c1", icone: "R" },
    ATIVIDADE_INTERNA: { label: "At. Interna", cor: "#fd7e14", icone: "I" },
    MANUTENCAO: { label: "Manutenção", cor: "#6c757d", icone: "M" },
  };

  const MESES_PT = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
  ];
  const DIAS_SEM = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"];

  // Estado local
  let diasData = {};
  let tipoAtivo = "FERIADO";
  let filtroTipo = null;
  let diaFoco = null;
  let diasExcecoes = { ...EXCECOES_INICIAIS };
  let dirty = false; // há alterações não salvas?

  // Elementos DOM
  const calGrade = document.getElementById("calGrade");
  const diaLabel = document.getElementById("diaLabel");
  const diaWeekday = document.getElementById("diaWeekday");
  const diaTipoSel = document.getElementById("diaTipoSel");
  const diaDescInput = document.getElementById("diaDescInput");
  const btnConfirmar = document.getElementById("btnConfirmarDia");
  const btnRemover = document.getElementById("btnRemoverDia");
  const btnSalvar = document.getElementById("btnSalvarCal");
  const btnLimpar = document.getElementById("btnLimparSel");
  const btnLimparFiltro = document.getElementById("btnLimparFiltro");
  const filtroAtivo = document.getElementById("filtroAtivo");
  const filtroAtivoLabel = document.getElementById("filtroAtivoLabel");
  const turmasExcecao = document.getElementById("turmasExcecao");
  const turmasExcecaoList = document.getElementById("turmasExcecaoList");
  const turmasExcecaoStatus = document.getElementById("turmasExcecaoStatus");
  const calStatus = document.getElementById("calStatus");
  const listaMarcadas = document.getElementById("listaMarcadas");
  const qtdMarcadas = document.getElementById("qtdMarcadas");
  const listaVazia = document.getElementById("listaVazia");
  const modalDiaEl = document.getElementById("modalDia");
  const avisoNaoSalvo = document.getElementById("avisoNaoSalvo");
  const btnSalvarAgora = document.getElementById("btnSalvarAgora");
  const csrfToken =
    document.querySelector('meta[name="csrf-token"]')?.content || "";

  // Instancia o modal apenas se ele existir (modo readonly não renderiza)
  const modalDia =
    modalDiaEl && window.bootstrap?.Modal
      ? new window.bootstrap.Modal(modalDiaEl)
      : null;

  // ── Aviso de alterações não salvas ──
  // Atualiza o estado e o banner. Ponto único para evitar esquecer chamadas.
  function avisarAlteracao(alterado = true) {
    if (READONLY) return;
    dirty = alterado;
    if (avisoNaoSalvo) {
      avisoNaoSalvo.classList.toggle("d-none", !dirty);
    }
  }

  // ── Filtro por tipo (sidebar) ──
  function aplicarFiltro(tipo) {
    filtroTipo = tipo || null;

    document.querySelectorAll(".tipo-btn").forEach((b) => {
      const ativo = !READONLY && b.dataset.tipo === filtroTipo;
      b.classList.toggle("ativo", ativo);
      if (!READONLY) {
        b.setAttribute("aria-pressed", ativo ? "true" : "false");
      }
    });

    if (btnLimparFiltro) {
      btnLimparFiltro.classList.toggle("d-none", !filtroTipo);
    }
    if (filtroAtivo && filtroAtivoLabel) {
      filtroAtivo.classList.toggle("d-none", !filtroTipo);
      if (filtroTipo) {
        const tipoInfo = TIPOS[filtroTipo];
        filtroAtivoLabel.textContent = tipoInfo ? tipoInfo.label : filtroTipo;
      }
    }

    renderListaMarcadas();
  }

  function alternarFiltro(tipo) {
    aplicarFiltro(filtroTipo === tipo ? null : tipo);
  }

  // ── Inicialização dos dados ──
  // Dias já persistidos no backend
  DIAS_INICIAIS.forEach((d) => {
    diasData[d.data] = { tipo: d.tipo, descricao: d.descricao };
  });

  // Pré-marca feriados nacionais que ainda não têm registro manual.
  // Em modo readonly não faz merge: o calendário só exibe o que está salvo.
  const FERIADOS_NACIONAIS = config.feriadosNacionais || {};
  let feriadosAdicionados = 0;
  if (!READONLY) {
    Object.entries(FERIADOS_NACIONAIS).forEach(([ds, nome]) => {
      if (ds >= PERIODO_INICIO && ds <= PERIODO_FIM && !diasData[ds]) {
        diasData[ds] = {
          tipo: "FERIADO",
          descricao: nome,
          automatico: true,
        };
        feriadosAdicionados += 1;
      }
    });
  }
  if (feriadosAdicionados > 0) {
    // Os feriados pré-marcados só persistem após Salvar.
    avisarAlteracao(true);
  }

  // ── Seletor de tipo ──
  document.querySelectorAll(".tipo-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (READONLY) return;
      alternarFiltro(btn.dataset.tipo);
    });
  });

  // ── Renderização do calendário ──
  function renderCalendar() {
    if (!calGrade) return;
    calGrade.innerHTML = "";
    const [anoI, mesI] = PERIODO_INICIO.split("-").map(Number);
    const [anoF, mesF] = PERIODO_FIM.split("-").map(Number);
    let ano = anoI,
      mes = mesI;
    while (ano < anoF || (ano === anoF && mes <= mesF)) {
      calGrade.appendChild(buildMonth(ano, mes));
      mes++;
      if (mes > 12) {
        mes = 1;
        ano++;
      }
    }
  }

  function shouldShowTurmasExcecao(ds) {
    return (
      !!TURMAS.length &&
      (!!diasData[ds] || (diasExcecoes[ds] && diasExcecoes[ds].length))
    );
  }

  function renderTurmasExcecao(ds) {
    if (!turmasExcecao || !turmasExcecaoList) {
      return;
    }
    const selected = new Set((diasExcecoes[ds] || []).map(Number));
    turmasExcecaoList.innerHTML = "";

    if (!TURMAS.length) {
      turmasExcecaoList.innerHTML =
        '<div class="col-12 text-muted small">Nenhuma turma disponível para exceção neste período.</div>';
      turmasExcecao.classList.toggle("d-none", true);
      return;
    }

    TURMAS.forEach((turma) => {
      const isChecked = selected.has(Number(turma.id));
      const item = document.createElement("div");
      item.className = "col-12 col-md-6 col-lg-4";
      item.innerHTML = `
        <div class="form-check">
          <input class="form-check-input" type="checkbox" value="${turma.id}" id="turma-excecao-${turma.id}" ${isChecked ? "checked" : ""}>
          <label class="form-check-label" for="turma-excecao-${turma.id}">${turma.nome}</label>
        </div>
      `;
      turmasExcecaoList.appendChild(item);
      const checkbox = item.querySelector('input[type="checkbox"]');
      checkbox?.addEventListener("change", updateTurmasExcecaoStatus);
    });

    turmasExcecao.classList.toggle("d-none", !shouldShowTurmasExcecao(ds));
    if (turmasExcecaoStatus) {
      turmasExcecaoStatus.textContent = selected.size;
    }
  }

  function getSelectedTurmas() {
    if (!turmasExcecaoList) return [];
    const checked = [];
    turmasExcecaoList
      .querySelectorAll('input[type="checkbox"]:checked')
      .forEach((input) => {
        const turmaId = Number(input.value);
        if (!Number.isNaN(turmaId)) {
          checked.push(turmaId);
        }
      });
    return checked;
  }

  function updateTurmasExcecaoStatus() {
    if (!turmasExcecaoStatus) {
      return;
    }
    turmasExcecaoStatus.textContent = getSelectedTurmas().length;
  }

  function buildMonth(year, month) {
    const container = document.createElement("div");
    container.className = "cal-month";

    const title = document.createElement("div");
    title.className = "cal-month-title";
    title.textContent = `${MESES_PT[month - 1]} / ${year}`;
    container.appendChild(title);

    const header = document.createElement("div");
    header.className = "cal-week-header";
    DIAS_SEM.forEach((d) => {
      const s = document.createElement("span");
      s.textContent = d;
      header.appendChild(s);
    });
    container.appendChild(header);

    const grid = document.createElement("div");
    grid.className = "cal-days";

    const firstDay = new Date(year, month - 1, 1).getDay();
    const daysInMonth = new Date(year, month, 0).getDate();

    for (let i = 0; i < firstDay; i++) {
      const b = document.createElement("div");
      b.className = "cal-day empty";
      grid.appendChild(b);
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const ds = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const wday = new Date(year, month - 1, d).getDay();
      const cell = document.createElement("div");
      cell.className = `cal-day${wday === 0 || wday === 6 ? " weekend" : ""}`;
      cell.dataset.date = ds;
      cell.setAttribute("role", "button");
      cell.setAttribute("tabindex", "0");

      const num = document.createElement("div");
      num.className = "cal-day-num";
      num.textContent = d;
      cell.appendChild(num);

      if (diasData[ds]) paintCell(cell, ds);

      if (!READONLY) {
        cell.addEventListener("click", () => onDiaClick(ds, cell));
        cell.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            onDiaClick(ds, cell);
          }
        });
      }
      grid.appendChild(cell);
    }
    container.appendChild(grid);
    return container;
  }

  function paintCell(cell, ds) {
    if (!cell) return;
    const info = diasData[ds];
    if (!info) return;
    const tipo = TIPOS[info.tipo] || { cor: "#6c757d", icone: "?" };
    cell.style.setProperty("--tipo-cor", tipo.cor);
    cell.classList.add("selecionado");
    cell.querySelectorAll(".cal-day-badge").forEach((b) => b.remove());
    const badge = document.createElement("div");
    badge.className = "cal-day-badge";
    badge.style.background = tipo.cor;
    badge.textContent = tipo.icone;
    badge.title = info.automatico
      ? `${info.descricao || tipo.label} (feriado nacional sugerido)`
      : info.descricao || tipo.label;
    cell.appendChild(badge);
  }

  function clearCell(cell) {
    if (!cell) return;
    cell.classList.remove("selecionado");
    cell.style.removeProperty("--tipo-cor");
    cell.querySelectorAll(".cal-day-badge").forEach((b) => b.remove());
  }

  function onDiaClick(ds, cell) {
    diaFoco = ds;
    const [ano, mes, dia] = ds.split("-").map(Number);
    const dataLocal = new Date(ano, mes - 1, dia);

    if (diaLabel) {
      diaLabel.textContent = dataLocal.toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      });
    }
    if (diaWeekday) {
      diaWeekday.textContent = DIAS_SEM[dataLocal.getDay()];
    }
    if (diaTipoSel) {
      diaTipoSel.value = diasData[ds]?.tipo || tipoAtivo;
    }
    if (diaDescInput) {
      diaDescInput.value = diasData[ds]?.descricao || "";
    }
    renderTurmasExcecao(ds);

    if (cell) {
      cell.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    if (modalDia) {
      modalDia.show();
    }
  }

  // ── Sidebar: lista de datas marcadas ──
  function renderListaMarcadas() {
    if (!listaMarcadas) return;

    const todas = Object.entries(diasData).sort(([a], [b]) =>
      a.localeCompare(b),
    );
    const entradas = filtroTipo
      ? todas.filter(([, info]) => info.tipo === filtroTipo)
      : todas;

    if (qtdMarcadas) {
      qtdMarcadas.textContent = filtroTipo
        ? `${entradas.length} de ${todas.length}`
        : String(todas.length);
    }
    if (listaVazia) {
      listaVazia.classList.toggle("d-none", entradas.length > 0);
      listaVazia.textContent = filtroTipo
        ? "Nenhuma data marcada com este tipo."
        : "Nenhuma data marcada ainda.";
    }

    listaMarcadas.innerHTML = "";

    entradas.forEach(([ds, info]) => {
      const tipo = TIPOS[info.tipo] || {
        label: info.tipo,
        cor: "#6c757d",
        icone: "?",
      };
      const [a, m, d] = ds.split("-");
      const item = document.createElement("button");
      item.type = "button";
      item.className =
        "list-group-item list-group-item-action d-flex justify-content-between align-items-start gap-2 text-start";

      const conteudo = document.createElement("span");
      conteudo.innerHTML = `
        <span class="fw-semibold">${d}/${m}/${a}</span>
        <span class="text-muted">— ${tipo.label}</span>
        ${info.descricao ? `<br><small class="text-muted">${info.descricao}${info.automatico ? ' <span class="badge bg-light text-secondary border" title="Sugerido automaticamente">auto</span>' : ""}</small>` : ""}
      `;

      const badge = document.createElement("span");
      badge.className = "badge rounded-pill";
      badge.style.background = tipo.cor;
      badge.textContent = tipo.icone;

      item.appendChild(conteudo);
      item.appendChild(badge);

      if (!READONLY) {
        item.addEventListener("click", () => {
          const cell = calGrade?.querySelector(`[data-date="${ds}"]`);
          onDiaClick(ds, cell);
        });
      } else {
        item.classList.add("pe-none");
      }

      listaMarcadas.appendChild(item);
    });
  }

  // ── Mensagem flutuante ──
  function showFloatingMessage(message, type = "success") {
    const container = document.getElementById("alertContainer");
    if (!container) {
      if (calStatus) {
        calStatus.textContent = message;
        setTimeout(() => {
          if (calStatus) calStatus.textContent = "";
        }, 3000);
      }
      return;
    }
    const alertDiv = document.createElement("div");
    alertDiv.className = `alert alert-${type} alert-dismissible fade show small py-2 px-3 shadow`;
    alertDiv.role = "alert";
    alertDiv.innerHTML = `
      ${message}
      <button type="button" class="btn-close btn-sm" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    container.appendChild(alertDiv);
    setTimeout(() => {
      alertDiv.classList.remove("show");
      setTimeout(() => alertDiv.remove(), 300);
    }, 4000);
  }

  // ── Eventos dos botões ──
  btnConfirmar?.addEventListener("click", () => {
    if (!diaFoco) return;
    diasData[diaFoco] = {
      tipo: diaTipoSel?.value || tipoAtivo,
      descricao: (diaDescInput?.value || "").trim(),
    };
    const selectedTurmas = getSelectedTurmas();
    if (selectedTurmas.length) {
      diasExcecoes[diaFoco] = selectedTurmas;
    } else {
      delete diasExcecoes[diaFoco];
    }
    const cell = calGrade?.querySelector(`[data-date="${diaFoco}"]`);
    paintCell(cell, diaFoco);
    renderListaMarcadas();
    avisarAlteracao(true);
    modalDia?.hide();
    showFloatingMessage(
      "Marcação adicionada. Clique em <strong>Salvar</strong> para gravar.",
      "warning",
    );
  });

  btnRemover?.addEventListener("click", () => {
    if (!diaFoco) return;
    delete diasData[diaFoco];
    delete diasExcecoes[diaFoco];
    const cell = calGrade?.querySelector(`[data-date="${diaFoco}"]`);
    clearCell(cell);
    renderListaMarcadas();
    avisarAlteracao(true);
    modalDia?.hide();
  });

  btnLimpar?.addEventListener("click", () => {
    if (!confirm("Limpar todos os dias marcados?")) return;
    diasData = {};
    diasExcecoes = {};
    calGrade?.querySelectorAll(".cal-day").forEach(clearCell);
    renderListaMarcadas();
    avisarAlteracao(true);
    modalDia?.hide();
  });

  btnLimparFiltro?.addEventListener("click", () => {
    aplicarFiltro(null);
  });

  btnSalvar?.addEventListener("click", async () => {
    const dias = Object.entries(diasData).map(([data, v]) => ({
      data,
      tipo: v.tipo,
      descricao: v.descricao || "",
    }));
    showFloatingMessage("Salvando...", "info");
    try {
      const res = await fetch("/planejamento/calendario/salvar", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          periodo_id: PERIODO_ID,
          dias,
          excecoes: diasExcecoes,
        }),
      });
      if (!res.ok) {
        showFloatingMessage("Erro ao salvar.", "danger");
        return;
      }
      const data = await res.json();
      if (data.success) {
        avisarAlteracao(false); // nada pendente após salvar com sucesso
        showFloatingMessage("✔ Salvo com sucesso!", "success");
      } else {
        showFloatingMessage(`Erro: ${data.message}`, "danger");
      }
    } catch (e) {
      showFloatingMessage("Falha de conexão.", "danger");
    }
  });

  // Botão "Salvar agora" dentro do banner de aviso
  btnSalvarAgora?.addEventListener("click", () => {
    btnSalvar?.click();
  });

  // Proteção ao sair com alterações pendentes
  window.addEventListener("beforeunload", (ev) => {
    if (!dirty || READONLY) return;
    ev.preventDefault();
    ev.returnValue = "";
  });

  // ── Inicialização ──
  renderCalendar();
  renderListaMarcadas();
})();
