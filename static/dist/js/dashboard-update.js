/*
 * Actualizacion del servidor en el navbar del dashboard
 * (change 025-update-web-deploy).
 *
 * Consulta `dashboard:update_status` y pinta el aviso. El boton NO despliega:
 * escribe una peticion que recoge una unidad systemd en el servidor. Por eso
 * aqui solo hay fetch y texto.
 *
 * Vive en el layout del dashboard, no en una pagina: el navbar se renderiza en
 * todas, asi que el aviso aparece donde este el admin. Si el nodo no existe
 * (usuario que no es superusuario), este archivo no hace absolutamente nada.
 *
 * Sin bundler y sin dependencias: JS vanilla, como el resto del proyecto.
 */
(function () {
  'use strict';

  var POLL_IDLE_MS = 60000; // el estado cambia como mucho una vez por release
  var POLL_BUSY_MS = 2000; // mientras el servidor esta desplegando

  var root = document.getElementById('update-navbar');
  if (!root) {
    return;
  }

  var icon = document.getElementById('update-navbar-icon');
  var spinner = document.getElementById('update-navbar-spinner');
  var badge = document.getElementById('update-navbar-badge');
  var title = document.getElementById('update-navbar-title');
  var version = document.getElementById('update-navbar-version');
  var text = document.getElementById('update-navbar-text');
  var detail = document.getElementById('update-navbar-detail');
  var button = document.getElementById('update-navbar-button');
  var logButton = document.getElementById('update-navbar-log');
  var commitsBox = document.getElementById('update-navbar-commits');
  var progressBox = document.getElementById('update-navbar-progress');
  var progressBar = document.getElementById('update-navbar-progress-bar');
  var progressStep = document.getElementById('update-navbar-progress-step');

  var statusUrl = root.getAttribute('data-status-url');
  var requestUrl = root.getAttribute('data-request-url');
  var logUrl = root.getAttribute('data-log-url');
  var csrfToken = root.getAttribute('data-csrf-token');

  var logModal = document.getElementById('update-log-modal');
  var logNote = document.getElementById('update-log-note');
  var logPre = document.getElementById('update-log-pre');
  var attemptLabel = document.getElementById('update-log-attempt');
  var syncLine = document.getElementById('update-navbar-sync');
  var syncText = document.getElementById('update-navbar-sync-text');
  var confirmModalEl = document.getElementById('update-confirm-modal');
  var confirmTarget = document.getElementById('update-confirm-target');
  var confirmDeploy = document.getElementById('update-confirm-deploy');

  var timer = null;
  // Ultimo estado pintado. El modal de confirmacion arma su texto con el, asi
  // que no puede leerlo de un DOM que ya cambio.
  var current = null;
  var confirmModal = null;

  function schedule(delay) {
    window.clearTimeout(timer);
    timer = window.setTimeout(load, delay);
  }

  function clearCommits() {
    while (commitsBox.firstChild) {
      commitsBox.removeChild(commitsBox.firstChild);
    }
    commitsBox.classList.add('d-none');
  }

  function paintCommits(state) {
    // Un template viejo en cache (o una pagina que no incluye la lista) deja
    // `commitsBox` en null. Sin esta guarda, `clearCommits` lanzaria
    // `TypeError` y se llevaria por delante TODO el render del aviso, no solo
    // la lista: el admin perderia el aviso de actualizacion entero.
    if (!commitsBox) {
      return;
    }

    clearCommits();

    var payload = state.commits;
    if (!payload || !payload.commits || !payload.commits.length) {
      // Sin mensajes se cae a los SHA que ya pinta `render`, y si tampoco hay
      // eso, a nada. Un fallo de la API no se anuncia: el aviso de
      // actualizacion sigue siendo cierto.
      return;
    }

    payload.commits.forEach(function (entry) {
      var item = document.createElement('li');
      item.className = 'px-3 py-1';

      var row = document.createElement('div');
      row.className = 'd-flex align-items-start gap-2';

      var sha = document.createElement('span');
      sha.className = 'text-secondary small font-monospace flex-shrink-0';
      sha.textContent = entry.sha || '·······';

      // `textContent` y no `innerHTML`: el mensaje viene de un commit, o sea de
      // cualquiera que pueda pushear a main. Un `<img onerror>` ahi dentro se
      // ejecutaria en el panel del administrador.
      var subject = document.createElement('span');
      subject.className = 'text-truncate small flex-grow-1';
      // Sin `min-width: 0` un flex item no baja de su ancho de contenido y
      // `text-truncate` no recorta nada: el mensaje largo desborda el menu.
      subject.style.minWidth = '0';
      subject.textContent = entry.subject || '(sin mensaje)';
      subject.title = entry.subject || '';

      row.appendChild(sha);
      row.appendChild(subject);
      item.appendChild(row);
      commitsBox.appendChild(item);
    });

    if (payload.truncated) {
      var rest = payload.total - payload.commits.length;
      var more = document.createElement('li');
      more.className = 'px-3 py-1 text-secondary small';
      more.textContent = 'y ' + rest + ' commit' + (rest === 1 ? '' : 's') + ' más';
      commitsBox.appendChild(more);
    }

    commitsBox.classList.remove('d-none');
  }

  // Barra de progreso del despliegue en curso.
  //
  // `percent` viene calculado del servidor a partir de una clave de paso
  // validada; acá no se interpreta nada del archivo de progreso. Cuando no hay
  // numero (preparación, rollback) la barra es indeterminada: una barra quieta
  // en 0% mientras el ejecutor trabaja es una mentira peor que ninguna barra.
  function paintProgress(progress) {
    if (!progressBar) {
      return;
    }

    var percent =
      progress && typeof progress.percent === 'number'
        ? Math.max(0, Math.min(100, progress.percent))
        : null;
    var indeterminate = percent === null;

    progressBar.classList.toggle('progress-bar-indeterminate', indeterminate);
    // Indeterminada: SIN ancho. Tabler dibuja el barrido con los pseudoelementos
    // dentro de la pista; con `width: 100%` la barra queda llena y se lee como
    // "terminado". Verificado en el navegador, no es teoria.
    progressBar.style.width = indeterminate ? '' : percent + '%';

    if (indeterminate) {
      progressBar.removeAttribute('aria-valuenow');
      progressBar.setAttribute('aria-valuetext', 'En curso');
    } else {
      progressBar.setAttribute('aria-valuenow', String(percent));
      progressBar.removeAttribute('aria-valuetext');
    }

    if (progressStep) {
      progressStep.textContent = (progress && progress.message) || 'Desplegando…';
    }
  }

  function setDetail(text) {
    detail.textContent = text || '';
    // Un `div` vacio con `mt-2` deja un hueco: sin detalle, que no ocupe sitio.
    detail.classList.toggle('d-none', !text);
  }

  function paint(options) {
    // `badge` es la senal: un punto sobre el icono del navbar. El resto del
    // texto vive dentro del desplegable, que solo se ve si el admin lo abre.
    //
    // El punto lleva color pleno (`update-dot-<color>`), no el light variant
    // `-lt`: ese mezcla un 10% del color y sobre el navbar claro dejaba un
    // rosa palido de 8px que no se distinguia.
    badge.className =
      'update-dot position-absolute top-0 start-100 translate-middle' +
      (options.badge ? ' update-dot-' + options.badge : '');
    badge.classList.toggle('d-none', !options.badge);

    icon.className = 'icon ' + (options.icon || 'ti ti-refresh');
    // El spinner sustituye al icono durante el despliegue. Se aplica despues de
    // reescribir `className` porque esa asignacion borra cualquier `d-none`
    // anterior. Sin el nodo (template viejo en cache) queda el `ti-loader`, que
    // es lo que habia antes de este cambio.
    var spinning = Boolean(options.spinner) && Boolean(spinner);
    icon.classList.toggle('d-none', spinning);
    if (spinner) {
      spinner.classList.toggle('d-none', !spinning);
    }
    title.textContent = options.title || 'Actualizaciones';
    text.textContent = options.message || '';
    setDetail(options.detail);

    // Chip de version, siempre con textContent. Sin texto no se deja un
    // hueco vacio: el nodo se esconde.
    if (version) {
      version.textContent = options.versionText || '';
      version.classList.toggle('d-none', !options.versionText);
    }

    // Con barra, el texto "Desplegando…" sobra: la barra ocupa su lugar, no se
    // suma al lado. Si el template en cache no trae el bloque de progreso, el
    // texto se queda: esconderlo sin barra dejaria el desplegable vacio.
    var showProgress = Boolean(options.progress) && Boolean(progressBox);
    if (progressBox) {
      progressBox.classList.toggle('d-none', !showProgress);
    }
    text.classList.toggle('d-none', showProgress);
    if (showProgress) {
      paintProgress(options.progress);
    }

    button.classList.toggle('d-none', !options.action);
    button.disabled = !options.action || Boolean(options.busy);
    // El label por defecto, o el que arma `render` con la version exacta del
    // tag. El tag ya trae su `v`: aca no se compone ningun formato.
    button.textContent = options.buttonLabel || 'Actualizar ahora';

    // El log solo cuando el archivo corresponde a lo que se ve. Con una
    // actualizacion pendiente el log es del intento anterior —otro commit— y
    // mostrarlo hace creer que el despliegue que falta ya corrio. En exito,
    // fallo y despliegue en curso si sirve.
    if (logButton) {
      logButton.classList.toggle('d-none', Boolean(options.hideLog));
    }
  }

  // Version que muestra el chip: la que se esta instalando (tag exacto del
  // commit remoto) mientras hay actualizacion o despliegue, y la que sirve el
  // servidor en el resto de los estados. Sin tag exacto se cae al SHA corto:
  // nunca un numero inventado.
  function chipVersion(state) {
    if (state.state === 'available' || state.state === 'running') {
      return state.version || state.deployed_version || state.deployed_short || '';
    }
    return state.deployed_version || state.deployed_short || '';
  }

  // Tiempo relativo y no una fecha: el navegador del admin puede estar en otro
  // huso, y "hace 2 h" se lee igual en cualquiera. Un ISO invalido no inventa
  // nada: devuelve vacio.
  function hace(iso) {
    if (!iso) {
      return '';
    }
    var fecha = new Date(iso);
    if (isNaN(fecha.getTime())) {
      return '';
    }
    var minutos = Math.floor((Date.now() - fecha.getTime()) / 60000);
    if (minutos < 1) {
      return 'hace un momento';
    }
    if (minutos < 60) {
      return 'hace ' + minutos + ' min';
    }
    var horas = Math.floor(minutos / 60);
    if (horas < 24) {
      return 'hace ' + horas + ' h';
    }
    var dias = Math.floor(horas / 24);
    return 'hace ' + dias + (dias === 1 ? ' día' : ' días');
  }

  // El ultimo intento es contexto, nunca el titulo del desplegable: el archivo
  // de estado conserva el ultimo `ok` o `failed` hasta el intento siguiente, y
  // usarlo de titulo anunciaria como presente algo que ya paso.
  //
  // Sin version a proposito: el chip ya la muestra, y repetirla aca es el mismo
  // ruido que "Ahora se esta sirviendo vX" que se saco del estado completado.
  function ultimoIntento(run) {
    if (!run || !run.status) {
      return '';
    }
    if (run.status === 'failed') {
      // El servidor no esta en el commit que fallo: se actualizo por otra via.
      // Decir "el commit anterior sigue sirviendo" seria falso.
      return 'El último intento falló; el detalle está en «Ver log del despliegue».';
    }
    if (run.status === 'ok') {
      var cuando = hace(run.finished_at || run.started_at);
      return 'Último despliegue' + (cuando ? ': ' + cuando : '') + '.';
    }
    return '';
  }

  // Que intento es el log que muestra el modal. El archivo del log es del
  // ultimo intento, no necesariamente del commit pendiente: sin esto el lector
  // cree que esta viendo el despliegue que todavia no corrio.
  function paintAttempt(state) {
    if (!attemptLabel) {
      return;
    }
    var run = state.last_run || {};
    var partes = [];
    // La version solo cuando el intento es del commit que se esta sirviendo:
    // para otro commit la version no se puede deducir del tag actual.
    if (run.sha && run.sha === state.deployed && state.deployed_version) {
      partes.push(state.deployed_version);
    }
    if (run.sha) {
      partes.push(run.sha.slice(0, 7));
    }
    var cuando = hace(run.finished_at || run.started_at);
    if (cuando) {
      partes.push(cuando);
    }
    attemptLabel.textContent = partes.length ? partes.join(' · ') : 'sin intento registrado';
  }

  // El sync de artefactos root escribe su ultima corrida BUENA en otro archivo:
  // cuando falla no deja estado de fallo, se queda el anterior. La unica senal
  // honesta es que no completa una corrida desde hace demasiado, y eso es lo
  // que se muestra. Sin archivo, el sync no esta instalado y no se dice nada.
  function paintSync(sync) {
    if (!syncLine || !syncText) {
      return;
    }
    if (!sync || !sync.installed_at) {
      syncLine.classList.add('d-none');
      return;
    }
    var cuando = hace(sync.installed_at);
    var estancado = Boolean(sync.stale);
    syncText.textContent = estancado
      ? 'El sync de artefactos no completa una corrida' + (cuando ? ' desde ' + cuando : '') + '.'
      : 'Artefactos root: ' +
        (sync.sha_short || 'sin SHA') +
        (cuando ? ' · ' + cuando : '');
    // Rojo solo cuando hay algo que mirar: un sync al dia no es una alarma.
    syncLine.classList.toggle('text-red', estancado);
    syncLine.classList.toggle('text-secondary', !estancado);
    syncLine.classList.remove('d-none');
  }

  // Texto del objetivo para la confirmacion. La version del tag si la hay; sin
  // tag exacto, el SHA, que es lo unico cierto.
  function targetLabel(state) {
    if (!state) {
      return 'el último commit de main';
    }
    if (state.version) {
      return state.version + (state.latest_short ? ' (' + state.latest_short + ')' : '');
    }
    return state.latest_short || 'el último commit de main';
  }

  // Ningun clic del navbar despliega: abre la confirmacion. Sin el nodo del
  // modal (template viejo en cache) se usa un confirm nativo, que tambien
  // impide el disparo accidental; lo que no se hace nunca es pedir el deploy
  // sin preguntar.
  function openConfirm() {
    if (!confirmModalEl) {
      if (window.confirm('¿Desplegar ' + targetLabel(current) + ' en producción?')) {
        requestUpdate();
      }
      return;
    }
    if (confirmTarget) {
      confirmTarget.textContent = targetLabel(current);
    }
    if (!confirmModal) {
      confirmModal = new window.bootstrap.Modal(confirmModalEl);
    }
    confirmModal.show();
  }

  function render(state) {
    // Antes de cualquier pintado: si el estado dejo de ser `available`, la
    // lista vieja tiene que desaparecer, no quedarse pegada al desplegable.
    paintCommits(state);
    // La barra del modal dice de que intento es el log que se va a leer.
    paintAttempt(state);
    // El sync de artefactos root vive fuera de `state.state`: puede estar
    // parado mientras el servidor esta al dia.
    paintSync(state.sync);

    current = state;

    var run = state.last_run || {};
    var chip = chipVersion(state);

    if (state.state === 'running') {
      paint({
        badge: 'blue',
        icon: 'ti ti-loader',
        spinner: true,
        title: 'Desplegando',
        message: run.message || 'Desplegando…',
        // Sin detalle: la accion en curso va debajo de la barra, y decir "se
        // esta reiniciando" durante un `pip install` seria falso.
        progress: state.progress || null,
        busy: true,
        versionText: chip,
      });
      return;
    }

    if (state.state === 'available') {
      // `available` no es una alarma: es una accion pendiente. El punto azul lo
      // separa del rojo de `failed`, que si es un problema.
      var target = state.version;
      paint({
        badge: 'blue',
        icon: 'ti ti-download',
        title: 'Actualización disponible',
        // Solo el rango de SHA: la version vive en el chip y en el boton, y
        // repetirla aca era el mismo ruido que el detalle de "Instala vX (sha)".
        message: state.deployed_short + ' → ' + state.latest_short,
        // Sin tag exacto el chip muestra el SHA y el boton dice "Actualizar
        // ahora": ahi si hace falta decir que instala, porque nada mas lo dice.
        detail: target ? '' : 'Instala el último commit de main en este servidor.',
        action: true,
        buttonLabel: target ? 'Actualizar a ' + target : null,
        // El log del intento anterior es de otro commit: no se ofrece.
        hideLog: true,
        versionText: chip,
      });
      return;
    }

    if (state.state === 'failed') {
      // El backend solo responde `failed` cuando el intento fallido fue contra
      // el commit que sigue pendiente: ahi el boton sirve para reintentar, que
      // es lo que hace falta despues de arreglar la causa. Un fallo viejo sobre
      // un commit que ya quedo atras no llega por aca: es contexto de
      // `up_to_date`, y ofrecer el boton ahi mandaria a desplegar lo que ya se
      // esta sirviendo.
      paint({
        badge: 'red',
        icon: 'ti ti-alert-triangle',
        title: 'El despliegue falló',
        message: run.message || 'El despliegue falló.',
        // El mensaje del backend ya manda al log; repetirlo aca era decirlo dos
        // veces en dos renglones seguidos.
        detail: 'El commit anterior sigue sirviendo; puedes reintentar.',
        action: true,
        // El reintento vuelve a desplegar el mismo commit pendiente: con tag
        // exacto el boton nombra la version, igual que en `available`.
        buttonLabel: state.version ? 'Actualizar a ' + state.version : null,
        versionText: chip,
      });
      return;
    }

    // `up_to_date` y `unknown` no se anuncian con un punto: un navbar que grita
    // "todo al día" en cada carga es ruido, y "no se pudo comprobar" sin
    // contexto solo asusta. El texto queda dentro del desplegable, para quien
    // lo abra a preguntar.
    if (state.state === 'up_to_date') {
      paint({
        icon: 'ti ti-check',
        // La version va en el chip, que esta al lado: entre parentesis aca era
        // la misma version dos veces en el mismo renglon.
        message: 'El servidor está al día.',
        // El estado manda; el ultimo intento va aca, como contexto, y no como
        // titulo. Sin intento previo no hay nada que contar.
        detail: ultimoIntento(run),
        versionText: chip,
      });
      return;
    }

    paint({
      icon: state.check_error ? 'ti ti-cloud-off' : 'ti ti-help-circle',
      title: state.check_error ? 'Sin conexión con el repositorio' : 'Sin datos del despliegue',
      message: state.check_error || state.reason || 'No se pudo comprobar si hay actualizaciones.',
      // Sin detalle propio: la simulacion de desarrollo es configuracion
      // interna y no tiene por que aparecer en el desplegable.
      detail: state.check_error ? 'El aviso vuelve solo cuando el repositorio responda.' : '',
      versionText: chip,
    });
  }

  // El log lo trae el backend al abrir el modal y, mientras el despliegue
  // esta en curso, en cada ciclo de polling de estado (2 s). Leerlo en cada
  // ciclo SIN modal abierto seria cargar el panel con un renglon de pip otra
  // vez, por eso las condiciones son modal abierto + `running`, mas una
  // ultima lectura al terminar. textContent y no innerHTML: el contenido lo
  // escribe root en el servidor, y aun asi no hay motivo para interpretarlo
  // como markup.
  var logOpen = false;
  var logInFlight = false;
  var logWasRunning = false;

  function nearBottom() {
    // El lector esta "cerca del final" si le quedan menos de 2rem hasta el
    // fondo. Quien se quedo leyendo una parte antigua del log no pierde su
    // lugar cuando llega una linea nueva.
    return logPre.scrollHeight - logPre.scrollTop - logPre.clientHeight < 32;
  }

  // El script de deploy escribe secuencias ANSI de color (␛[1;34m==>␛[0m)
  // que en un <pre> se ven como basura. Se quitan antes de pintar; se acepta
  // tanto ESC real (U+001B) como el glifo ␛ (U+241B) que deja el copiado.
  var ANSI_COLOR = /\u001b\[[0-9;]*m|\u241b\[[0-9;]*m/g;

  // El color de cada linea lo decide el CSS del modal
  // (`update-console-<tipo>`), con variantes para tema claro y oscuro. Aca no
  // se eligen clases de color: `text-white` sobre el tema claro del sitio
  // dejaba el log ilegible.

  function setLogNote(text) {
    if (!logNote) {
      return;
    }
    logNote.textContent = text || '';
    logNote.classList.toggle('d-none', !text);
  }

  function logLineKind(text) {
    if (/^==>/.test(text)) {
      return 'section';
    }
    if (/\b(OK|Desplegado|responde 200)\b/i.test(text)) {
      return 'ok';
    }
    if (/\b(ERROR|FATAL|Traceback|fallido|fallo|abortado)\b/i.test(text)) {
      return 'error';
    }
    if (/^\s*[·•]/.test(text)) {
      return 'item';
    }
    if (/\d{4}-\d{2}-\d{2}T.*autodeploy:/.test(text)) {
      return 'journal';
    }
    return 'plain';
  }

  function paintLog(payload) {
    if (!logPre) {
      return;
    }
    if (!payload.available) {
      logPre.textContent = '';
      setLogNote(
        'Todavía no hay log: lo genera el primer despliegue que corra con este commit.'
      );
      return;
    }
    // El header ya dice «Log del último despliegue»: el body solo avisa cuando
    // hay algo que el header no cuenta, como que el inicio se recortó.
    setLogNote(payload.truncated ? 'Cola del log: el inicio se recortó por tamaño.' : '');

    // Antes de reemplazar se decide si hay que scrollear: si el lector no esta
    // al final, se conserva su posicion.
    var keep = nearBottom();
    var contenido = payload.log ? String(payload.log) : '(sin salida)';
    var lineas = contenido.replace(ANSI_COLOR, '').split('\n');
    var fragmento = document.createDocumentFragment();

    lineas.forEach(function (raw, index) {
      var fila = document.createElement('div');
      fila.className = 'update-console-line update-console-' + logLineKind(raw);

      // Gutter del terminal: columna propia y separador vertical, no margenes
      // dentro de un `<pre>`. `aria-hidden` porque el numero es decorativo.
      var numero = document.createElement('span');
      numero.className = 'update-console-line-no';
      numero.setAttribute('aria-hidden', 'true');
      numero.textContent = String(index + 1);

      var texto = document.createElement('span');
      texto.className = 'update-console-text';
      // El log NO se filtra: tiene rutas absolutas del servidor y lo escriben
      // personas con acceso push. Solo text nodes, nunca innerHTML.
      texto.textContent = raw;

      fila.appendChild(numero);
      fila.appendChild(texto);
      fragmento.appendChild(fila);
    });

    while (logPre.firstChild) {
      logPre.removeChild(logPre.firstChild);
    }
    logPre.appendChild(fragmento);

    // El resultado esta al final: un deploy que aborta imprime la causa en las
    // ultimas lineas, y abrir por arriba obligaria a scrollear hasta el fondo.
    if (keep) {
      logPre.scrollTop = logPre.scrollHeight;
    }
  }

  function loadLog(quiet) {
    if (!logUrl || !logPre) {
      return;
    }
    // Una lectura en vuelo no se superpone: la del ciclo siguiente la pisa
    // cuando responda. Sin esto, un servidor lento acumularia peticiones.
    if (logInFlight) {
      return;
    }
    logInFlight = true;
    if (!quiet) {
      setLogNote('Cargando…');
    }
    window
      .fetch(logUrl, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('status ' + response.status);
        }
        return response.json();
      })
      .then(paintLog)
      .catch(function () {
        setLogNote('No se pudo leer el log del servidor.');
      })
      .then(function () {
        logInFlight = false;
      });
  }

  if (logModal) {
    logModal.addEventListener('show.bs.modal', function () {
      logOpen = true;
      loadLog();
    });
    logModal.addEventListener('hidden.bs.modal', function () {
      logOpen = false;
    });
  }

  function load() {
    window
      .fetch(statusUrl, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('status ' + response.status);
        }
        return response.json();
      })
      .then(function (state) {
        render(state);
        // Log en vivo: con el modal abierto, en cada ciclo que el despliegue
        // sigue `running` se relée el log (el polling ya va a 2 s). Al salir
        // de `running` (`logWasRunning`) hay una ultima lectura, que es la
        // que trae el resultado final.
        var running = state.state === 'running';
        if (logOpen && (running || logWasRunning)) {
          loadLog(true);
        }
        logWasRunning = running;
        schedule(running ? POLL_BUSY_MS : POLL_IDLE_MS);
      })
      .catch(function () {
        // Un fallo de red no rompe el dashboard: se reintenta en el proximo ciclo.
        schedule(POLL_IDLE_MS);
      });
  }

  function requestUpdate() {
    button.disabled = true;
    window
      .fetch(requestUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' },
      })
      .then(function (response) {
        return response.json().then(function (body) {
          return { ok: response.ok, body: body };
        });
      })
      .then(function (result) {
        if (!result.ok) {
          setDetail(result.body.reason || 'No se pudo pedir la actualización.');
          button.disabled = false;
          schedule(POLL_IDLE_MS);
          return;
        }
        // Aceptada: systemd tarda en arrancar la unidad, asi que se consulta en
        // el ritmo rapido hasta que el estado pase a `running`.
        setDetail('Petición enviada. Esperando al servidor…');
        schedule(POLL_BUSY_MS);
      })
      .catch(function () {
        setDetail('No se pudo contactar al servidor.');
        button.disabled = false;
        schedule(POLL_IDLE_MS);
      });
  }

  if (button) {
    // El boton, incluido el de reintento de `failed`, abre la confirmacion.
    button.addEventListener('click', openConfirm);
  }

  if (confirmDeploy) {
    confirmDeploy.addEventListener('click', function () {
      if (confirmModal) {
        confirmModal.hide();
      }
      requestUpdate();
    });
  }

  load();
})();
