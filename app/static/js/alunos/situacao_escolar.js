window.toggleSituacaoEscolar = function () {
  const escolaridade = document.getElementById('escolaridade')?.value;
  const tipo = document.getElementById('tipo_instituicao')?.value;
  const turno = document.getElementById('turno_escolar')?.value;
  const status = document.getElementById('status_escolar')?.value;
  document.getElementById('status-outro')?.classList.toggle('d-none', status !== 'Outros');
  document.getElementById('periodo-superior')?.classList.toggle('d-none', escolaridade !== 'Ensino superior');
  document.getElementById('escolaridade-outro')?.classList.toggle('d-none', escolaridade !== 'Outros');
  document.getElementById('bolsista-div')?.classList.toggle('d-none', tipo !== 'Privada');
  document.getElementById('instituicao-outro')?.classList.toggle('d-none', tipo !== 'Outro');
  document.getElementById('turno-outro')?.classList.toggle('d-none', turno !== 'Outros');
};
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('nome_instituicao');
  const lista = document.getElementById('sugestoes-instituicao');
  input?.addEventListener('input', async () => {
    if (!lista) return;
    if (input.value.trim().length < 2) return lista.classList.add('d-none');

    try {
      const response = await fetch(`/alunos/instituicoes?q=${encodeURIComponent(input.value)}`);
      if (!response.ok) throw new Error('Falha ao buscar instituições');
      const nomes = await response.json();

      lista.replaceChildren();
      nomes.forEach(nome => {
        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'list-group-item list-group-item-action';
        botao.textContent = nome;
        botao.addEventListener('click', () => {
          input.value = nome;
          lista.classList.add('d-none');
        });
        lista.appendChild(botao);
      });
      lista.classList.toggle('d-none', !nomes.length);
    } catch {
      lista.classList.add('d-none');
    }
  });
  window.toggleSituacaoEscolar();

});
