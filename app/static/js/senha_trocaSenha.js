document.addEventListener('DOMContentLoaded', () => {
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


// Validação de nova senha
(function () {
    const campo = document.getElementById('novaSenha');
    const confirma = document.getElementById('confirmaSenha');
    const btn = document.getElementById('btnSalvar');
    const matchMsg = document.getElementById('matchMsg');

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
        const pass = fn(s);
        li.innerHTML = pass
          ? `<i class="bi bi-check-circle-fill text-success me-1"></i>${li.textContent.trim()}`
          : `<i class="bi bi-x-circle-fill text-danger me-1"></i>${li.textContent.trim()}`;
        if (!pass) ok = false;
      }

      const match = confirma.value && s === confirma.value;
      if (confirma.value) {
        matchMsg.textContent = match ? '✔ Senhas coincidem' : '✘ Senhas não coincidem';
        matchMsg.className = match ? 'form-text text-success' : 'form-text text-danger';
      } else {
        matchMsg.textContent = '';
      }

      btn.disabled = !(ok && match);
    }

    campo.addEventListener('input', atualizar);
    confirma.addEventListener('input', atualizar);
  })();
});