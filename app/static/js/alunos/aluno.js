// static/js/alunos/aluno.js
// Lógica do formulário de aluno (novo e edição).
// Depende de window.AlunoUtils — carregue aluno_utils.js ANTES.

(function () {
  'use strict';

  const U = window.AlunoUtils || {};
  const $ = id => document.getElementById(id);
  const toggleHidden = (el, hidden) => el?.classList.toggle('d-none', hidden);

  // ============================================================
  // STEPPER
  // ============================================================
  const stepIds = [...document.querySelectorAll('.form-step')]
    .map(s => Number(s.id.replace('step-', '')))
    .filter(Number.isInteger)
    .sort((a, b) => a - b);
  const lastStepId = stepIds.at(-1) || 1;
  let currentStep = 1;

  function updateStepper() {
    for (let i = 1; i <= 6; i++) {
      const el = $(`step-indicator-${i}`);
      if (!el) continue;
      if (!stepIds.includes(i)) { el.classList.add('d-none'); continue; }

      el.classList.remove('d-none');
      if (i < currentStep) {
        el.classList.add('completed'); el.classList.remove('active');
        el.innerHTML = '<i class="bi bi-check"></i>';
      } else if (i === currentStep) {
        el.classList.add('active'); el.classList.remove('completed');
        el.textContent = i;
      } else {
        el.classList.remove('active', 'completed');
        el.textContent = i;
      }
    }
    toggleHidden($('prevBtn'), currentStep === 1);
    const isLast = currentStep === lastStepId;
    toggleHidden($('nextBtn'), isLast);
    toggleHidden($('submitBtn'), !isLast);
  }

  function validarEtapaAtual() {
    const step = $(`step-${currentStep}`);
    if (!step) return true;

    // 1) CPFs preenchidos precisam ser válidos
    let primeiro = null;
    if (typeof U.validarCampoCPF === 'function') {
      step.querySelectorAll('.validate-cpf').forEach(input => {
        if (!U.validarCampoCPF(input) && !primeiro) primeiro = input;
      });
    }
    if (primeiro) { primeiro.focus(); return false; }

    // 2) Campos [required] visíveis e vazios
    const visivel = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    const obrigatorio = Array.from(step.querySelectorAll('[required]'))
      .find(el => !el.disabled && visivel(el) && !el.checkValidity());
    if (obrigatorio) {
      obrigatorio.reportValidity?.();
      obrigatorio.focus();
      return false;
    }

    return true;
  }

  function irPara(n) {
    const el = $(`step-${n}`);
    if (!el) return;
    $(`step-${currentStep}`)?.classList.remove('active');
    currentStep = n;
    el.classList.add('active');
    updateStepper();
    window.scrollTo(0, 0);
  }

  function goToStep(n) {
    if (n === currentStep || !stepIds.includes(n)) return;
    if (n > currentStep && !validarEtapaAtual()) return;
    irPara(n);
  }

  function nextStep(delta) {
    if (delta > 0 && !validarEtapaAtual()) return;
    const alvo = stepIds[stepIds.indexOf(currentStep) + delta];
    if (alvo) irPara(alvo);
  }

  // ============================================================
  // PREVIEW / UPLOAD
  // ============================================================
  function previewImage(input) {
    if (!input.files?.[0]) return;
    const preview = $('img-preview');
    const icon = $('placeholder-icon');
    const reader = new FileReader();
    reader.onload = e => {
      preview.src = e.target.result;
      preview.classList.remove('d-none');
      icon?.classList.add('d-none');
    };
    reader.readAsDataURL(input.files[0]);
  }

  function updateFileName(id, input) {
    const label = $(`name_${id}`);
    const file = input.files?.[0];
    if (!file || !label) return;
    if (file.size > 2 * 1024 * 1024) {
      alert('Arquivo muito grande! Máximo 2MB.');
      input.value = '';
      label.textContent = 'Clique para selecionar';
      return;
    }
    label.textContent = file.name;
    label.classList.remove('text-muted');
    label.classList.add('text-primary', 'fw-bold');
  }

  // ============================================================
  // TOGGLES CONDICIONAIS
  // ============================================================
  function toggleLaudoUpload(checkbox) {
    toggleHidden($('laudo_upload_container'), !checkbox.checked);
    toggleHidden($('tipo_deficiencia_container'), !checkbox.checked);
    const select = $('tipo_deficiencia');
    if (select) {
      select.disabled = !checkbox.checked;
      if (!checkbox.checked) select.value = '';
    }
  }

  function toggleMedicacao(select) {
    toggleHidden($('medicacao_nome_div'), select.value !== 'Sim');
  }

  function toggleBeneficioSocial(select) {
    toggleHidden($('beneficio_social_div'), select.value !== 'Sim');
  }

  function toggleAcompanhanteAulas(checkbox) {
    const div = $('acompanhante_aulas_div');
    if (!div) return;
    toggleHidden(div, !checkbox.checked);
    if (!checkbox.checked) {
      const sel = document.querySelector('select[name="acompanhante_aulas"]');
      const outroDiv = $('acompanhante_aulas_outro_div');
      const outroInput = $('acompanhante_aulas_outro');
      if (sel) sel.value = '';
      toggleHidden(outroDiv, true);
      if (outroInput) { outroInput.value = ''; outroInput.required = false; }
    }
  }

  function toggleOutroAcompanhante(select) {
    const div = $('acompanhante_aulas_outro_div');
    const campo = $('acompanhante_aulas_outro');
    if (!div || !campo) return;
    const isOutro = select.value === 'Outro';
    toggleHidden(div, !isOutro);
    campo.required = isOutro;
    if (isOutro) campo.focus();
    else campo.value = '';
  }

  // ============================================================
  // RESPONSÁVEL
  // ============================================================
  function syncResponsavel() {
    const tipo = $('responsavel_tipo')?.value;
    const nome = $('responsavel_nome');
    const cpf = $('responsavel_cpf');
    if (!nome) return;

    const copiar = (nomeId, cpfId) => {
      nome.value = $(nomeId)?.value || '';
      if (cpf) {
        cpf.value = $(cpfId)?.value || '';
        U.validarCampoCPF?.(cpf);
      }
      nome.readOnly = true;
      if (cpf) cpf.readOnly = true;
    };

    if (tipo === 'Mãe') return copiar('nome_mae', 'cpf_mae');
    if (tipo === 'Pai') return copiar('nome_pai', 'cpf_pai');

    nome.readOnly = false;
    if (cpf) { cpf.readOnly = false; U.validarCampoCPF?.(cpf); }
  }

  // ============================================================
  // RENDA PER CAPITA
  // ============================================================
  function updateRendaPerCapita() {
    const renda = parseFloat(document.querySelector('[name="renda_familiar"]')?.value);
    const pessoas = parseInt(document.querySelector('[name="pessoas_residencia"]')?.value, 10);
    const out = $('renda_per_capita');
    if (!out) return;
    out.value = Number.isFinite(renda) && pessoas > 0
      ? new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2 }).format(renda / pessoas)
      : '';
  }

  // ============================================================
  // BENEFÍCIOS SOCIAIS
  // ============================================================
  function adicionarBeneficioSocial() {
    const input = $('beneficio_social_input');
    const tags = $('beneficio_social_tags');
    if (!input || !tags) return;
    const nome = input.value.trim();
    if (!nome) return;

    const jaExiste = [...tags.querySelectorAll('[data-beneficio]')]
      .some(t => t.dataset.beneficio.toLowerCase() === nome.toLowerCase());
    if (jaExiste) { input.value = ''; return; }

    const esc = U.escapeHtml(nome);
    const tag = document.createElement('span');
    tag.className = 'badge bg-primary-subtle text-primary-emphasis d-inline-flex align-items-center gap-1';
    tag.dataset.beneficio = nome;
    tag.innerHTML = `${esc}
      <button type="button" class="btn-close btn-close-sm"
        aria-label="Remover ${esc}"
        onclick="window.removerBeneficioSocial(this)"></button>
      <input type="hidden" name="beneficio_social_nome" value="${esc}">`;
    tags.appendChild(tag);
    input.value = '';
  }

  function removerBeneficioSocial(btn) {
    btn.closest('[data-beneficio]')?.remove();
  }

  // ============================================================
  // IDADE
  // ============================================================
  function calcularIdade() {
    const input = $('data_nascimento');
    const out = $('idade');
    if (!out) return;

    const limpar = () => {
      out.value = '';
      out.style.backgroundColor = '';
      out.style.borderColor = '';
    };

    if (!input?.value) return limpar();
    const nasc = new Date(input.value);
    if (isNaN(nasc)) return limpar();

    const hoje = new Date();
    let idade = hoje.getFullYear() - nasc.getFullYear();
    const m = hoje.getMonth() - nasc.getMonth();
    if (m < 0 || (m === 0 && hoje.getDate() < nasc.getDate())) idade--;

    out.value = `${idade} anos`;

    const [bg, border] =
      idade < 14 ? ['#ffcccc', '#f5c2c7'] :
        idade < 18 ? ['#fff3cd', '#ffecb5'] :
          ['#cfe2ff', '#b6d4fe'];
    out.style.setProperty('background-color', bg, 'important');
    out.style.setProperty('border-color', border, 'important');
  }

  // ============================================================
  // SITUAÇÃO ESCOLAR
  // ============================================================
  function toggleSituacaoEscolar() {
    const v = id => $(id)?.value;
    toggleHidden($('status-outro'), v('status_escolar') !== 'Outros');
    toggleHidden($('periodo-superior'), v('escolaridade') !== 'Ensino superior');
    toggleHidden($('escolaridade-outro'), v('escolaridade') !== 'Outros');
    toggleHidden($('bolsista-div'), v('tipo_instituicao') !== 'Privada');
    toggleHidden($('instituicao-outro'), v('tipo_instituicao') !== 'Outro');
    toggleHidden($('turno-outro'), v('turno_escolar') !== 'Outros');
  }

  // ============================================================
  // AUTOCOMPLETE DE INSTITUIÇÕES
  // ============================================================
  function initAutocompleteInstituicao() {
    const input = $('nome_instituicao');
    const lista = $('sugestoes-instituicao');
    if (!input || !lista) return;

    input.addEventListener('input', async () => {
      if (input.value.trim().length < 2) return lista.classList.add('d-none');
      try {
        const res = await fetch(`/alunos/instituicoes?q=${encodeURIComponent(input.value)}`);
        if (!res.ok) throw new Error();
        const nomes = await res.json();
        lista.replaceChildren();
        nomes.forEach(nome => {
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'list-group-item list-group-item-action';
          b.textContent = nome;
          b.addEventListener('click', () => { input.value = nome; lista.classList.add('d-none'); });
          lista.appendChild(b);
        });
        lista.classList.toggle('d-none', !nomes.length);
      } catch {
        lista.classList.add('d-none');
      }
    });
  }

  // ============================================================
  // SUBMIT — bloqueia se houver CPF inválido
  // ============================================================
  function bloquearSubmitSeCPFInvalido(form) {
    form.addEventListener('submit', e => {
      if (typeof U.validarCampoCPF !== 'function') return;
      let primeiro = null;
      form.querySelectorAll('.validate-cpf').forEach(input => {
        if (!U.validarCampoCPF(input) && !primeiro) primeiro = input;
      });
      if (!primeiro) return;

      e.preventDefault();
      e.stopPropagation();
      const stepEl = primeiro.closest('.form-step');
      if (stepEl) goToStep(Number(stepEl.id.replace('step-', '')));
      primeiro.focus();
    });
  }

  // ============================================================
  // EXPORTS — somente o que é chamado pelo HTML
  // ============================================================
  Object.assign(window, {
    goToStep, nextStep,
    previewImage, updateFileName,
    toggleLaudoUpload, toggleMedicacao, toggleBeneficioSocial,
    toggleAcompanhanteAulas,
    toggleOutroAcompanhante,
    adicionarBeneficioSocial, removerBeneficioSocial,
    calcularIdade, toggleSituacaoEscolar,
  });

  // ============================================================
  // INIT
  // ============================================================
  document.addEventListener('DOMContentLoaded', () => {
    // 1) Máscaras, CPF, CEP, IBGE
    U.init?.();

    // 2) Stepper
    updateStepper();

    // 3) Responsável
    const respTipo = $('responsavel_tipo');
    respTipo?.addEventListener('change', syncResponsavel);
    ['nome_mae', 'cpf_mae', 'nome_pai', 'cpf_pai'].forEach(id => {
      $(id)?.addEventListener('input', () => {
        if (['Mãe', 'Pai'].includes(respTipo?.value)) syncResponsavel();
      });
    });

    // 4) Acompanhante — o select não tem id/onchange no HTML; liga via listener
    const selAcomp = document.querySelector('select[name="acompanhante_aulas"]');
    selAcomp?.addEventListener('change', () => toggleOutroAcompanhante(selAcomp));

    // Restaura estado (ex.: form volta com erro do backend já marcado)
    const chkAcomp = $('vai_acompanhado_aulas');
    if (chkAcomp?.checked) {
      toggleAcompanhanteAulas(chkAcomp);
      if (selAcomp?.value) toggleOutroAcompanhante(selAcomp);
    }

    // 5) Toggles — estado inicial
    const beneficioSel = document.querySelector('select[name="beneficio_social_status"]');
    if (beneficioSel) toggleBeneficioSocial(beneficioSel);
    $('beneficio_social_input')?.addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); adicionarBeneficioSocial(); }
    });

    const medicacaoSel = document.querySelector('select[name="saude_medicacao"]');
    if (medicacaoSel) toggleMedicacao(medicacaoSel);

    const laudoChk = $('saude_laudo');
    if (laudoChk) toggleLaudoUpload(laudoChk);

    // 6) Renda
    document.querySelector('[name="renda_familiar"]')?.addEventListener('input', updateRendaPerCapita);
    document.querySelector('[name="pessoas_residencia"]')?.addEventListener('input', updateRendaPerCapita);
    updateRendaPerCapita();

    // 7) Idade
    $('data_nascimento')?.addEventListener('change', calcularIdade);
    calcularIdade();

    // 8) Situação escolar
    toggleSituacaoEscolar();

    // 9) Autocomplete
    initAutocompleteInstituicao();

    // 10) Submit
    const form = $('multiStepForm');
    if (form) bloquearSubmitSeCPFInvalido(form);
  });
})();