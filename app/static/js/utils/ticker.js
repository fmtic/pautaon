// app/static/js/utils/ticker.js

document.addEventListener("DOMContentLoaded", function () {
    const tickerElement = document.getElementById('ticker-text');
    if (!tickerElement) return;

    function atualizarTickerTopbar() {
        fetch('/api/ticker/json') // Ajuste a URL caso utilize prefixo no Blueprint (ex: /rss/api/ticker/json)
            .then(response => response.json())
            .then(data => {
                if (data.texto) {
                    const icon = document.createElement('i');
                    icon.classList.add('bi', 'bi-megaphone-fill', 'me-1');
                    tickerElement.replaceChildren(icon, document.createTextNode(` ${data.texto}`));
                }
            })
            .catch(error => console.error('Erro ao atualizar o ticker:', error));
    }

    // Executa ao carregar e atualiza a cada 60 segundos
    atualizarTickerTopbar();
    setInterval(atualizarTickerTopbar, 60000);
});