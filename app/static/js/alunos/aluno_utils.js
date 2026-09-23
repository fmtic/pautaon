// static/js/alunos/aluno_utils.js
// Utilitários + integrações externas (ViaCEP, IBGE, webcam, data de emissão).
// Sem lógica de formulário (stepper/toggles) — isso fica em aluno.js.
// Carregue ANTES de aluno.js.

(function () {
  'use strict';

  // ============================================================
  // FORMATAÇÃO
  // ============================================================
  function formatarDataHora(data = new Date()) {
    return data.toLocaleString('pt-BR');
  }

  function mascaraCPF(valor) {
    return String(valor || '')
      .replace(/\D/g, '').slice(0, 11)
      .replace(/^(\d{3})(\d)/, '$1.$2')
      .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
      .replace(/^(\d{3})\.(\d{3})\.(\d{3})(\d)/, '$1.$2.$3-$4');
  }

  function mascaraCEP(valor) {
    return String(valor || '')
      .replace(/\D/g, '').slice(0, 8)
      .replace(/(\d{5})(\d)/, '$1-$2');
  }

  function mascaraPhone(valor) {
    const d = String(valor || '').replace(/\D/g, '').slice(0, 11);
    if (d.length > 10) return d.replace(/^(\d{2})(\d{5})(\d{4})$/, '($1) $2-$3');
    if (d.length > 5)  return d.replace(/^(\d{2})(\d{4})(\d{0,4})$/, '($1) $2-$3');
    if (d.length > 2)  return d.replace(/^(\d{2})(\d{0,5})$/, '($1) $2');
    return d;
  }

  function escapeHtml(value) {
    const el = document.createElement('span');
    el.textContent = value;
    return el.innerHTML;
  }

  // ============================================================
  // DOM — Data de emissão (histórico)
  // ============================================================
  function preencherDataEmissao(id = 'dataEmissao') {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = 'Emissão: ' + formatarDataHora();
  }

  // ============================================================
  // CPF
  // ============================================================
  function validarCPF(valor) {
    if (typeof valor !== 'string') return false;
    const cpf = valor.replace(/\D/g, '');
    if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;

    const calc = base => {
      const soma = [...base].reduce((acc, n, i) => acc + (+n) * (base.length + 1 - i), 0);
      const r = (soma * 10) % 11;
      return r === 10 ? 0 : r;
    };
    const d1 = calc(cpf.slice(0, 9));
    const d2 = calc(cpf.slice(0, 9) + d1);
    return cpf === cpf.slice(0, 9) + d1 + d2;
  }

  function validarCampoCPF(input) {
    if (!input) return true;
    const digits = input.value.replace(/\D/g, '');

    if (!digits) {
      input.classList.remove('is-invalid', 'is-valid');
      input.setCustomValidity('');
      return true;
    }

    const ok = validarCPF(input.value);
    input.classList.toggle('is-valid', ok);
    input.classList.toggle('is-invalid', !ok);
    input.setCustomValidity(ok ? '' : 'CPF inválido');
    return ok;
  }

  // ============================================================
  // CEP
  // ============================================================
  function buscarEndereco(cep) {
    const rua = document.getElementById('rua');
    if (rua) rua.placeholder = 'Buscando...';

    return fetch(`https://viacep.com.br/ws/${cep}/json/`)
      .then(r => r.json())
      .then(d => {
        if (d.erro) { alert('CEP não encontrado.'); return; }
        const set = (id, v) => {
          const el = document.getElementById(id);
          if (el) el.value = v || '';
        };
        set('rua', d.logradouro);
        set('bairro', d.bairro);
        set('cidade', d.localidade);
        set('uf', d.uf);
      })
      .catch(() => console.error('Erro ao buscar CEP'))
      .finally(() => { if (rua) rua.placeholder = ''; });
  }

  // ============================================================
  // IBGE
  // ============================================================
  async function carregarUFs() {
    const ufSelect = document.getElementById('natural_uf');
    if (!ufSelect) return;

    try {
      const res = await fetch(
        'https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome'
      );
      const ufs = await res.json();
      ufs.forEach(uf => ufSelect.appendChild(new Option(uf.nome, uf.sigla)));

      const salva = ufSelect.getAttribute('data-selected');
      if (salva) {
        ufSelect.value = salva;
        ufSelect.dispatchEvent(new Event('change', { bubbles: true }));
      }
    } catch (e) {
      console.error('Erro ao carregar UFs:', e);
    }
  }

  async function carregarCidades(ufSigla) {
    const cidadeSelect = document.getElementById('natural_cidade');
    if (!cidadeSelect || !ufSigla) return;

    cidadeSelect.innerHTML = '<option value="">Carregando...</option>';
    try {
      const res = await fetch(
        `https://servicodados.ibge.gov.br/api/v1/localidades/estados/${ufSigla}/municipios?orderBy=nome`
      );
      const cidades = await res.json();
      cidadeSelect.innerHTML = '<option value="">Selecione a Cidade</option>';
      cidades.forEach(c => cidadeSelect.appendChild(new Option(c.nome, c.nome)));

      const salva = cidadeSelect.getAttribute('data-selected');
      if (salva) cidadeSelect.value = salva;
    } catch (e) {
      console.error('Erro ao carregar cidades:', e);
    }
  }

  // ============================================================
  // WEBCAM
  // ============================================================
  let stream = null;
  let modal = null;

  async function abrirWebcam() {
    const video = document.getElementById('webcamVideo');
    const el = document.getElementById('webcamModal');

    if (!video || !el) {
      alert('A janela da câmera não está disponível nesta página.');
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      alert('Este navegador não permite acessar a câmera.');
      return;
    }
    if (typeof bootstrap === 'undefined' || !bootstrap.Modal) {
      alert('Não foi possível abrir a janela da câmera.');
      return;
    }

    if (!modal) modal = new bootstrap.Modal(el, { backdrop: 'static' });

    try {
      fecharWebcam();
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }
      });
      video.srcObject = stream;
      modal.show();
    } catch (err) {
      console.error(err);
      alert('Não foi possível acessar a câmera.');
    }
  }

  function fecharWebcam() {
    const video = document.getElementById('webcamVideo');
    stream?.getTracks().forEach(t => t.stop());
    stream = null;
    if (video) video.srcObject = null;
    modal?.hide();
  }

  function capturarFoto() {
    const video = document.getElementById('webcamVideo');
    const canvas = document.getElementById('webcamCanvas');

    if (!video || !canvas) {
      alert('Não foi possível localizar a câmera para capturar a foto.');
      return;
    }
    if (!stream || video.readyState < 2) {
      alert('A câmera ainda não está pronta para capturar a foto.');
      return;
    }

    const ctx = canvas.getContext('2d');
    ctx.save();
    ctx.scale(-1, 1);
    ctx.drawImage(video, -canvas.width, 0, canvas.width, canvas.height);
    ctx.restore();

    canvas.toBlob(blob => {
      if (!blob) {
        alert('Não foi possível gerar a foto da webcam.');
        return;
      }

      const file = new File([blob], 'foto_webcam.jpg', { type: 'image/jpeg' });
      const dt = new DataTransfer();
      dt.items.add(file);

      const input = document.getElementById('inputFotoManual');
      if (input) {
        input.files = dt.files;
        input.dispatchEvent(new Event('change'));
      }
      fecharWebcam();
    }, 'image/jpeg', 0.92);
  }

  // ============================================================
  // INIT — liga máscaras, CPF, CEP, IBGE, data de emissão
  // ============================================================
  function init() {
    // Máscaras
    document.querySelectorAll('.mask-cpf').forEach(el => {
      el.value = mascaraCPF(el.value);
      el.addEventListener('input', () => {
        const digitosAntes = el.value.slice(0, el.selectionStart).replace(/\D/g, '').length;
        el.value = mascaraCPF(el.value);
        let pos = 0, cont = 0;
        while (pos < el.value.length && cont < digitosAntes) {
          if (/\d/.test(el.value[pos])) cont++;
          pos++;
        }
        el.setSelectionRange(pos, pos);
      });
    });

    document.querySelectorAll('.mask-cep').forEach(el => {
      el.value = mascaraCEP(el.value);
      el.addEventListener('input', () => { el.value = mascaraCEP(el.value); });
      el.addEventListener('blur', () => {
        const cep = el.value.replace(/\D/g, '');
        if (cep.length === 8) buscarEndereco(cep);
      });
    });

    document.querySelectorAll('.mask-phone').forEach(el => {
      el.value = mascaraPhone(el.value);
      el.addEventListener('input', () => { el.value = mascaraPhone(el.value); });
    });

    // CPF
    document.querySelectorAll('.validate-cpf').forEach(input => {
      if (input.value.trim()) validarCampoCPF(input);
      input.addEventListener('input', () => {
        const d = input.value.replace(/\D/g, '');
        if (d.length === 11 || input.classList.contains('is-invalid')) {
          validarCampoCPF(input);
        } else if (!d) {
          input.classList.remove('is-invalid', 'is-valid');
          input.setCustomValidity('');
        }
      });
      input.addEventListener('blur', () => validarCampoCPF(input));
    });

    // IBGE
    const uf = document.getElementById('natural_uf');
    if (uf) {
      carregarUFs();
      uf.addEventListener('change', e => carregarCidades(e.target.value));
    }

    // Data de emissão (página de histórico)
    preencherDataEmissao();
  }

  // ============================================================
  // EXPORTS
  // ============================================================
  window.AlunoUtils = {
    // formatação
    formatarDataHora, preencherDataEmissao,
    mascaraCPF, mascaraCEP, mascaraPhone, escapeHtml,
    // validação
    validarCPF, validarCampoCPF,
    // integrações externas
    buscarEndereco, carregarUFs, carregarCidades,
    abrirWebcam, fecharWebcam, capturarFoto,
    // ciclo de vida
    init,
  };

  // Aliases globais — exigidos pelos handlers inline do template
  window.abrirWebcam  = abrirWebcam;
  window.fecharWebcam = fecharWebcam;
  window.capturarFoto = capturarFoto;
})();