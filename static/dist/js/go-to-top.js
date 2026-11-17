(function () {
  'use strict';

  var button = document.querySelector('.t-go-to-top');
  if (!button) {
    return;
  }

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function update() {
    // Solo con scroll real: una pagina corta no necesita el boton. El margen
    // de 40px evita parpadeos donde el scroll maximo es casi cero.
    var scrollable = document.documentElement.scrollHeight > window.innerHeight + 40;
    var awayFromTop = window.scrollY > 200;
    button.classList.toggle('visible', scrollable && awayFromTop);

    // Solo en el dashboard (body.layout-fluid): ahi el footer lleva las redes
    // sociales en la esquina inferior derecha y el boton las taparia. El home
    // comparte el mismo footer pero ahi no estorban, asi que no se mueve.
    // La subida es fija y corta (offset en CSS), no calculada sobre el alto del
    // footer, que lo elevaba demasiado.
    var atBottom =
      document.body.classList.contains('layout-fluid') &&
      window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2;
    button.classList.toggle('at-bottom', atBottom);
  }

  window.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update);
  update();

  button.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
  });
})();
