/*
 * Evita registros duplicados por doble clic (CU04/CU05).
 * Uso: agregar el atributo data-evitar-doble-envio a la etiqueta <form>.
 * Al enviar, el boton se deshabilita y un segundo envio se ignora.
 */
(function () {
    document.addEventListener('submit', function (event) {
        var form = event.target;
        if (!form.matches('form[data-evitar-doble-envio]')) return;

        if (form.dataset.enviando === 'true') {
            event.preventDefault();
            return;
        }
        form.dataset.enviando = 'true';

        var boton = form.querySelector('button[type="submit"]');
        if (boton) {
            boton.dataset.textoOriginal = boton.innerHTML;
            boton.disabled = true;
            boton.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Guardando...';
        }
    });

    /* Si el usuario regresa con el boton "Atras" del navegador, se reactiva el formulario */
    window.addEventListener('pageshow', function () {
        document.querySelectorAll('form[data-evitar-doble-envio]').forEach(function (form) {
            form.dataset.enviando = 'false';
            var boton = form.querySelector('button[type="submit"]');
            if (boton && boton.dataset.textoOriginal) {
                boton.disabled = false;
                boton.innerHTML = boton.dataset.textoOriginal;
            }
        });
    });
})();