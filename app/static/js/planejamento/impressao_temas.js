document.querySelectorAll('.data-emissao').forEach((element) => {
  element.textContent = new Date().toLocaleString('pt-BR');
});