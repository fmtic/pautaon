// static/js/periodos/certificado.js
(function() {
    'use strict';

    // Preenche data de emissão nos certificados
    document.querySelectorAll('.cert-data-emissao').forEach(el => {
        el.textContent = new Date().toLocaleDateString('pt-BR', {
            day: '2-digit', month: 'long', year: 'numeric'
        });
    });

    // Função global para imprimir certificado individual
    window.imprimirCertificado = function(alunoId) {
        // Oculta tudo, mostra só o certificado do aluno e imprime
        document.querySelectorAll('.cert-page').forEach(el => el.style.display = 'none');
        document.querySelector('.no-cert-print').style.display = 'none';

        const cert = document.getElementById('cert-' + alunoId);
        if (cert) {
            cert.style.display = 'block';
            window.print();
            // Restaura após impressão
            setTimeout(() => {
                cert.style.display = 'none';
                document.querySelector('.no-cert-print').style.display = '';
            }, 1000);
        }
    };
})();