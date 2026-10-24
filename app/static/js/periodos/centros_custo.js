// static/js/periodos/centros_custo.js
(function() {
  "use strict";
  const modal = document.getElementById("modalCentrosCusto");
  if (!modal) return;
  const lista = document.getElementById("cc_lista");
  const input = document.getElementById("cc_novo_nome");
  const btnCriar = document.getElementById("cc_btn_criar");
  const CSRF = document.querySelector("#periodoForm input[name=\"csrf_token\"]")?.value || "";

  function ensureContainer() {
    let msg = document.getElementById("cc_validation_msg");
    if (msg) return msg.parentNode;
    const p = document.querySelector("p.fst-italic");
    const container = document.createElement("div");
    container.className = "border rounded p-3 bg-light";
    const msg2 = document.createElement("div");
    msg2.id = "cc_validation_msg";
    msg2.className = "text-danger small mt-1";
    msg2.style.display = "none";
    msg2.textContent = "Selecione ao menos um Centro de Custo.";
    container.appendChild(msg2);
    if (p && p.parentNode) {
      p.parentNode.replaceChild(container, p);
    } else {
      const form = document.getElementById("periodoForm");
      if (form) form.appendChild(container);
    }
    return container;
  }

  function findCheckbox(value) {
    return Array.from(document.querySelectorAll(".centro-custo-check")).find(cb => cb.value === value) || null;
  }

  function adicionarCheckbox(nome, id, checked) {
    const container = ensureContainer();
    const msg = document.getElementById("cc_validation_msg");
    if (findCheckbox(nome)) return;
    const div = document.createElement("div");
    div.className = "form-check";
    const input = document.createElement("input");
    input.className = "form-check-input centro-custo-check";
    input.type = "checkbox";
    input.name = "centro_custo";
    input.value = nome;
    input.id = "cc_" + id;
    input.checked = !!checked;
    const label = document.createElement("label");
    label.className = "form-check-label";
    label.htmlFor = input.id;
    label.textContent = nome;
    div.appendChild(input);
    div.appendChild(label);
    container.insertBefore(div, msg);
  }

  function atualizarCheckbox(oldName, newName) {
    const cb = findCheckbox(oldName);
    if (!cb) return;
    cb.value = newName;
    const label = document.querySelector("label[for=\"" + cb.id + "\"]");
    if (label) label.textContent = newName;
  }

  function removerCheckbox(nome) {
    const cb = findCheckbox(nome);
    if (cb) {
      const wrap = cb.closest(".form-check");
      if (wrap) wrap.remove();
    }
  }

  async function carregar() {
    lista.innerHTML = "";
    try {
      const resp = await fetch("/centros-custo");
      const ativos = await resp.json();
      const resp2 = await fetch("/centros-custo/inativos");
      const inativos = await resp2.json();
      [...ativos, ...inativos].forEach(c => {
        const item = document.createElement("div");
        item.className = "list-group-item d-flex justify-content-between align-items-center";
        const label = document.createElement("span");
        label.textContent = c.nome + (c.ativo ? "" : " (inativo)");
        item.appendChild(label);
        const btns = document.createElement("div");
        if (c.ativo) {
          const be = document.createElement("button");
          be.className = "btn btn-sm btn-outline-primary me-1";
          be.textContent = "Editar";
          be.onclick = async () => {
            const novo = prompt("Novo nome:", c.nome);
            if (!novo || novo.trim() === "" || novo.trim() === c.nome) return;
            const novoNome = novo.trim();
            const r = await fetch("/centros-custo/" + c.id + "/editar", {
              method:"POST",
              headers:{"Content-Type":"application/json","X-CSRFToken":CSRF},
              body: JSON.stringify({nome: novoNome})
            });
            let d = {};
            try { d = await r.json(); } catch(e) { d = {}; }
            if (d.success) {
              atualizarCheckbox(c.nome, d.nome || novoNome);
              carregar();
            } else {
              alert(d.message || "Erro");
            }
          };
          btns.appendChild(be);
          const bi = document.createElement("button");
          bi.className = "btn btn-sm btn-outline-secondary";
          bi.textContent = "Inativar";
          bi.onclick = async () => {
            const r = await fetch("/centros-custo/" + c.id + "/inativar", {
              method:"POST",
              headers:{"X-CSRFToken":CSRF}
            });
            let d = {};
            try { d = await r.json(); } catch(e) { d = {}; }
            if (d.success) {
              removerCheckbox(c.nome);
              carregar();
            } else {
              alert(d.message || "Erro");
            }
          };
          btns.appendChild(bi);
        } else {
          const br = document.createElement("button");
          br.className = "btn btn-sm btn-outline-success";
          br.textContent = "Reativar";
          br.onclick = async () => {
            const r = await fetch("/centros-custo/" + c.id + "/reativar", {
              method:"POST",
              headers:{"X-CSRFToken":CSRF}
            });
            let d = {};
            try { d = await r.json(); } catch(e) { d = {}; }
            if (d.success) {
              adicionarCheckbox(d.nome || c.nome, d.id || c.id, false);
              carregar();
            } else {
              alert(d.message || "Erro");
            }
          };
          btns.appendChild(br);
        }
        item.appendChild(btns);
        lista.appendChild(item);
      });
    } catch (err) {
      console.error("[centros-custo] carregar", err);
    }
  }

  if (btnCriar) {
    btnCriar.addEventListener("click", async () => {
      const nome = input.value.trim();
      if (!nome) return;
      btnCriar.disabled = true;
      try {
        const r = await fetch("/centros-custo/novo", {
          method:"POST",
          headers:{"Content-Type":"application/json","X-CSRFToken":CSRF},
          body: JSON.stringify({nome})
        });
        let d = {};
        try { d = await r.json(); } catch(e) { d = {}; }
        if (d.success) {
          input.value = "";
          adicionarCheckbox(d.nome || nome, d.id, true);
          carregar();
        } else {
          alert(d.message || "Erro");
        }
      } catch (err) {
        console.error("[centros-custo] criar", err);
        alert("Falha de rede. Tente novamente.");
      } finally {
        btnCriar.disabled = false;
      }
    });
  }
  modal.addEventListener("show.bs.modal", carregar);
})();
