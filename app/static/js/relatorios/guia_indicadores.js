/** Guia de Indicadores — busca local, expansão e âncoras. */
(function () {
  "use strict";

  var raiz = document.getElementById("conteudo-impressao");
  if (!raiz || !raiz.classList.contains("guia-indicadores")) {
    return;
  }

  var campo = document.getElementById("buscaIndicador");
  var contador = document.getElementById("contadorBusca");
  var semResultados = document.getElementById("semResultados");
  var itens = Array.prototype.slice.call(raiz.querySelectorAll(".guia-item"));
  var categorias = Array.prototype.slice.call(raiz.querySelectorAll(".guia-categoria"));
  var EXPANDIR = "expandir";
  var RECOLHER = "recolher";

  function normalizar(texto) {
    return String(texto || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase();
  }

  function definirAberto(codigo, aberto) {
    var painel = raiz.querySelector("#detalhes-" + codigo);
    var botao = raiz.querySelector('[data-guia-toggle="' + codigo + '"]');
    if (!painel) {
      return;
    }
    painel.classList.toggle("show", aberto);
    if (botao) {
      botao.setAttribute("aria-expanded", aberto ? "true" : "false");
      botao.textContent = aberto ? "Recolher" : "Detalhes";
    }
  }

  function abrirAncora() {
    var hash = decodeURIComponent(String(window.location.hash || "").replace(/^#/, ""));
    if (!hash) {
      return;
    }
    var alvo = document.getElementById(hash);
    if (!alvo || !raiz.contains(alvo)) {
      return;
    }
    var codigo = alvo.getAttribute("data-codigo") || hash;
    definirAberto(codigo, true);
    alvo.classList.remove("is-oculto");
    var categoria = alvo.closest(".guia-categoria");
    if (categoria) {
      categoria.classList.remove("is-oculta");
    }
    requestAnimationFrame(function () {
      alvo.scrollIntoView({ block: "start" });
    });
  }

  function filtrar() {
    var termo = normalizar(campo ? campo.value : "");
    var visiveis = 0;
    itens.forEach(function (item) {
      var texto = normalizar(item.getAttribute("data-pesquisa"));
      var encontrado = !termo || texto.indexOf(termo) !== -1;
      item.classList.toggle("is-oculto", !encontrado);
      if (encontrado) {
        visiveis += 1;
      }
    });
    categorias.forEach(function (categoria) {
      var filhos = Array.prototype.slice.call(categoria.querySelectorAll(".guia-item"));
      var algumVisivel = filhos.some(function (filho) {
        return !filho.classList.contains("is-oculto");
      });
      categoria.classList.toggle("is-oculta", !algumVisivel);
    });
    if (contador) {
      contador.textContent = visiveis + (visiveis === 1 ? " indicador" : " indicadores");
    }
    if (semResultados) {
      semResultados.classList.toggle("d-none", visiveis !== 0);
    }
  }

  if (campo) {
    campo.addEventListener("input", filtrar);
  }

  raiz.addEventListener("click", function (evento) {
    var alvo = evento.target.closest("[data-guia-toggle]");
    if (alvo && raiz.contains(alvo)) {
      var codigo = alvo.getAttribute("data-guia-toggle");
      var painel = raiz.querySelector("#detalhes-" + codigo);
      definirAberto(codigo, !(painel && painel.classList.contains("show")));
      return;
    }

    var acao = evento.target.closest("[data-guia-acao]");
    if (acao && raiz.contains(acao)) {
      var acaoPedida = acao.getAttribute("data-guia-acao");
      if (acaoPedida !== EXPANDIR && acaoPedida !== RECOLHER) {
        return;
      }
      var abrir = acaoPedida === EXPANDIR;
      itens.forEach(function (item) {
        definirAberto(item.getAttribute("data-codigo"), abrir);
      });
      definirAberto("glossario", true);
      return;
    }

    var ancora = evento.target.closest("[data-guia-ancora]");
    if (ancora && raiz.contains(ancora)) {
      var destino = document.getElementById(ancora.getAttribute("data-guia-ancora"));
      if (destino) {
        definirAberto(ancora.getAttribute("data-guia-ancora"), true);
      }
    }
  });

  /** Abertura pedida pela Central: ?imprimir=1 prepara tudo e imprime. */
  function imprimirSeSolicitado() {
    var params = new URLSearchParams(window.location.search);
    if (params.get("imprimir") !== "1") {
      return;
    }
    itens.forEach(function (item) {
      item.classList.remove("is-oculto");
      definirAberto(item.getAttribute("data-codigo"), true);
    });
    categorias.forEach(function (categoria) {
      categoria.classList.remove("is-oculta");
    });
    definirAberto("glossario", true);
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        window.print();
      });
    });
  }

  var iniciado = false;
  function iniciar() {
    if (iniciado) {
      return;
    }
    iniciado = true;
    abrirAncora();
    imprimirSeSolicitado();
  }

  window.addEventListener("hashchange", abrirAncora);
  document.addEventListener("DOMContentLoaded", iniciar);
  if (document.readyState !== "loading") {
    iniciar();
  }
})();
