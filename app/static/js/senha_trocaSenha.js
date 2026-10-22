// 1. Visibilidade de senha na tela de Login
document.addEventListener('DOMContentLoaded', () => {
  const togglePassword = document.getElementById('togglePassword');
  const passwordInput = document.getElementById('password');
  const toggleIcon = document.getElementById('toggleIcon');

  // Garante que os três elementos existem antes de registrar o clique
  if (!togglePassword || !passwordInput || !toggleIcon) return;

  togglePassword.addEventListener('click', (e) => {
    e.preventDefault(); // Impede envios acidentais do formulário

    if (passwordInput.type === 'password') {
      passwordInput.type = 'text';
      toggleIcon.className = 'bi bi-eye-slash'; // Define diretamente a classe do olho cortado
    } else {
      passwordInput.type = 'password';
      toggleIcon.className = 'bi bi-eye'; // Voltas para o olho normal
    }
  });
});

  // 2. Alternar visibilidade para botões genéricos com classe .toggle-password (Bootstrap Icons)
  document.querySelectorAll('.toggle-password').forEach((button) => {
    const password = document.getElementById(button.dataset.target);
    const icon = button.querySelector('i');

    if (!password || !icon) return;

    button.addEventListener('click', () => {
      const showing = password.type === 'password';
      password.type = showing ? 'text' : 'password';
      icon.classList.toggle('bi-eye', !showing);
      icon.classList.toggle('bi-eye-slash', showing);
      button.setAttribute('aria-label', showing ? 'Ocultar senha' : 'Exibir senha');
      button.setAttribute('aria-pressed', String(showing));
    });
  });

  // 3. Validação de nova palavra-passe (apenas executa se os campos existirem na página)
  (function () {
    const campo = document.getElementById('novaSenha');
    const confirma = document.getElementById('confirmaSenha');
    const btn = document.getElementById('btnSalvar');
    const matchMsg = document.getElementById('matchMsg');

    // Se os campos de alteração de palavra-passe não existirem no DOM atual, ignora a execução
    if (!campo || !confirma || !btn) return;

    const checks = {
      'req-len': s => s.length >= 8,
      'req-upper': s => /[A-Z]/.test(s),
      'req-lower': s => /[a-z]/.test(s),
      'req-num': s => /\d/.test(s),
      'req-spec': s => /[!@#$%^&*()\-_=+\[\]{};:'",.<>?/\\|`~]/.test(s),
    };

    function atualizar() {
      const s = campo.value;
      let ok = true;

      for (const [id, fn] of Object.entries(checks)) {
        const li = document.getElementById(id);
        if (!li) continue;

        const pass = fn(s);
        li.innerHTML = pass
          ? `<i class="bi bi-check-circle-fill text-success me-1"></i>${li.textContent.trim()}`
          : `<i class="bi bi-x-circle-fill text-danger me-1"></i>${li.textContent.trim()}`;
        if (!pass) ok = false;
      }

      const match = confirma.value && s === confirma.value;
      if (confirma.value && matchMsg) {
        matchMsg.textContent = match ? '✔ Senhas coincidem' : '✘ Senhas não coincidem';
        matchMsg.className = match ? 'form-text text-success' : 'form-text text-danger';
      } else if (matchMsg) {
        matchMsg.textContent = '';
      }

      btn.disabled = !(ok && match);
    }

    campo.addEventListener('input', atualizar);
    confirma.addEventListener('input', atualizar);
  })
();