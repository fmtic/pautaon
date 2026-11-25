/**
 * AJ29 — nome padrão do arquivo PDF nos relatórios impressos.
 *
 * Só mexe no `document.title` durante a impressão: o Chrome/Edge usam esse
 * título como nome sugerido no diálogo de salvamento do PDF (botão Imprimir
 * ou Ctrl+P). Nada de tela, rota, consulta, cálculo, permissão ou banco.
 *
 * Contrato:
 *   - lê `data-pdf-nome` de `#conteudo-impressao` (ou do `<body>`);
 *   - sem atributo => não faz nada;
 *   - `{data}` => data local do navegador no formato AAAA-MM-DD;
 *   - sanitiza: sem acentos, só [A-Za-z0-9._-], hífens colapsados/aparados,
 *     no máximo 100 caracteres;
 *   - guarda/restaura o título original em beforeprint/afterprint.
 *
 * Este módulo NÃO substitui `prepararImpressao()` nem remove listeners de
 * outras páginas: apenas acrescenta os seus (addEventListener).
 */
(function (root) {
    'use strict';

    var TOKEN_DATA = '{data}';
    var LIMITE = 100;

    /** Data local do navegador, sem fuso/UTC (AAAA-MM-DD). */
    function dataLocal() {
        var hoje = new Date();
        var ano = hoje.getFullYear();
        var mes = String(hoje.getMonth() + 1).padStart(2, '0');
        var dia = String(hoje.getDate()).padStart(2, '0');
        return ano + '-' + mes + '-' + dia;
    }

    /** Nome seguro para arquivo. Puro: não depende de DOM. */
    function sanitizar(texto) {
        return String(texto == null ? '' : texto)
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^A-Za-z0-9._-]+/g, '-')
            .replace(/-{2,}/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, LIMITE)
            .replace(/-+$/g, '');
    }

    /** Aplica o token {data} e sanitiza. Puro, aceita uma data injetada. */
    function nomePdf(bruto, data) {
        var valor = bruto == null ? '' : String(bruto);
        var dia = data == null ? dataLocal() : String(data);
        return sanitizar(valor.split(TOKEN_DATA).join(dia));
    }

    function alvoDoNome(doc) {
        if (!doc) {
            return null;
        }
        var conteudo = doc.getElementById ? doc.getElementById('conteudo-impressao') : null;
        if (conteudo && conteudo.getAttribute && conteudo.hasAttribute('data-pdf-nome')) {
            return conteudo;
        }
        return doc.body || null;
    }

    function brutoDoNome(doc) {
        var alvo = alvoDoNome(doc);
        if (!alvo || !alvo.getAttribute) {
            return null;
        }
        return alvo.getAttribute('data-pdf-nome');
    }

    var tituloOriginal = null;

    function antesDeImprimir(doc) {
        var bruto = brutoDoNome(doc);
        if (bruto == null || bruto === '') {
            return null;
        }
        var nome = nomePdf(bruto);
        if (!nome) {
            return null;
        }
        if (tituloOriginal === null) {
            tituloOriginal = doc.title;
        }
        doc.title = nome;
        return nome;
    }

    function depoisDeImprimir(doc) {
        if (tituloOriginal === null) {
            return false;
        }
        doc.title = tituloOriginal;
        tituloOriginal = null;
        return true;
    }

    var api = {
        sanitizar: sanitizar,
        nomePdf: nomePdf,
        dataLocal: dataLocal,
        brutoDoNome: brutoDoNome,
        antesDeImprimir: antesDeImprimir,
        depoisDeImprimir: depoisDeImprimir
    };

    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    }
    root.impressaoPdf = api;

    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
        window.addEventListener('beforeprint', function () {
            antesDeImprimir(document);
        });
        window.addEventListener('afterprint', function () {
            depoisDeImprimir(document);
        });
    }
})(typeof globalThis !== 'undefined' ? globalThis : this);
