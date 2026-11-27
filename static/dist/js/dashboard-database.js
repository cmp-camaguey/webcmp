/*
 * Respaldo y restauracion de la base desde el panel (change 040).
 *
 * El panel no ejecuta nada: pide un respaldo o una restauracion escribiendo
 * una peticion que recoge una unidad systemd, y lee el estado y el manifiesto
 * que deja el ejecutor root. Todo lo que viene del servidor se pinta con
 * `textContent`, nunca con `innerHTML`: el manifiesto lo escribe otro usuario.
 *
 * Sin bundler y sin dependencias: JS vanilla, como el resto del proyecto.
 */
(function () {
  'use strict';

  var POLL_BUSY_MS = 3000; // una operacion en curso cambia en segundos
  var POLL_IDLE_MS = 30000; // en reposo alcanza para ver el respaldo del dia

  var root = document.getElementById('database-backup');
  if (!root) {
    return;
  }

  var dataUrl = root.getAttribute('data-data-url');
  var backupUrl = root.getAttribute('data-backup-url');
  var restoreUrl = root.getAttribute('data-restore-url');
  var confirmation = root.getAttribute('data-confirmation');
  var csrfToken = root.getAttribute('data-csrf-token');

  var statusBox = document.getElementById('db-status');
  var pendingBox = document.getElementById('db-pending');
  var body = document.getElementById('db-backups-body');
  var keepLabel = document.getElementById('db-keep');
  var backupButton = document.getElementById('db-backup-button');

  var modalEl = document.getElementById('db-restore-modal');
  var restoreFile = document.getElementById('db-restore-file');
  var confirmWord = document.getElementById('db-confirm-word');
  var confirmInput = document.getElementById('db-confirm-input');
  var confirmButton = document.getElementById('db-confirm-button');
  var confirmError = document.getElementById('db-confirm-error');

  var modal = null;
  var timer = null;
  var busy = false;
  var selectedFile = null;
  var restoreRequested = false;

  function getModal() {
    if (modal || !modalEl) {
      return modal;
    }
    var Bootstrap = (window.tabler && window.tabler.bootstrap) || window.bootstrap;
    if (!Bootstrap || !Bootstrap.Modal) {
      return null;
    }
    modal = Bootstrap.Modal.getOrCreateInstance(modalEl);
    return modal;
  }

  var KIND_LABELS = {
    scheduled: 'Programado',
    manual: 'Manual',
    'pre-restore': 'Seguridad',
    'pre-migrate': 'Previo a migrar',
    unknown: 'Otro'
  };

  function setText(node, text) {
    if (node) {
      node.textContent = text || '';
    }
  }

  function humanSize(bytes) {
    if (typeof bytes !== 'number' || bytes < 0) {
      return '—';
    }
    var units = ['B', 'KB', 'MB', 'GB'];
    var value = bytes;
    var index = 0;
    while (value >= 1024 && index < units.length - 1) {
      value = value / 1024;
      index += 1;
    }
    return (index === 0 ? String(value) : value.toFixed(1)) + ' ' + units[index];
  }

  function humanDate(iso) {
    if (!iso) {
      return '—';
    }
    var date = new Date(iso);
    if (isNaN(date.getTime())) {
      return iso;
    }
    return date.toLocaleString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }

  function showStatus(status) {
    if (!statusBox) {
      return;
    }
    if (!status) {
      statusBox.classList.add('d-none');
      return;
    }
    statusBox.className = 'alert alert-' + status.tone;
    statusBox.textContent = '';
    var icon = document.createElement('i');
    icon.className = 'icon ti ti-' + status.icon + ' me-1';
    icon.setAttribute('aria-hidden', 'true');
    statusBox.appendChild(icon);
    statusBox.appendChild(document.createTextNode(status.text));
    statusBox.classList.remove('d-none');
  }

  function showPending(data) {
    if (!pendingBox) {
      return;
    }
    var messages = [];
    if (data.pending_backup) {
      messages.push(data.pending_backup.text);
    }
    if (data.pending_restore) {
      messages.push(data.pending_restore.text);
    }
    if (!messages.length) {
      pendingBox.classList.add('d-none');
      pendingBox.textContent = '';
      return;
    }
    pendingBox.textContent = '';
    var icon = document.createElement('i');
    icon.className = 'icon ti ti-plug-off me-1';
    icon.setAttribute('aria-hidden', 'true');
    pendingBox.appendChild(icon);
    pendingBox.appendChild(document.createTextNode(messages.join(' ')));
    pendingBox.classList.remove('d-none');
  }

  function initTooltips() {
    var Bootstrap = (window.tabler && window.tabler.bootstrap) || window.bootstrap;
    if (!Bootstrap || !Bootstrap.Tooltip) {
      return;
    }
    root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      try {
        var instance = Bootstrap.Tooltip.getInstance(el);
        if (instance) {
          instance.dispose();
        }
      } catch (e) {
        // sin instancia previa
      }
      try {
        new Bootstrap.Tooltip(el);
      } catch (e2) {
        // el botón sigue funcionando sin tooltip
      }
    });
  }

  function renderTable(manifest) {
    if (!body) {
      return;
    }
    body.textContent = '';
    var backups = (manifest && manifest.backups) || [];
    setText(keepLabel, manifest && manifest.keep != null ? String(manifest.keep) : '—');

    if (!backups.length) {
      var empty = document.createElement('tr');
      var cell = document.createElement('td');
      cell.colSpan = 5;
      cell.className = 'text-secondary text-center py-4';
      cell.textContent = 'Todavía no hay respaldos registrados.';
      empty.appendChild(cell);
      body.appendChild(empty);
      return;
    }

    backups.forEach(function (item) {
      var row = document.createElement('tr');

      var name = document.createElement('td');
      name.className = 'font-monospace text-break';
      name.textContent = item.name;
      row.appendChild(name);

      var date = document.createElement('td');
      date.className = 'text-secondary';
      date.textContent = humanDate(item.created_at);
      row.appendChild(date);

      var size = document.createElement('td');
      size.className = 'text-secondary';
      size.textContent = humanSize(item.size);
      row.appendChild(size);

      var kind = document.createElement('td');
      var badge = document.createElement('span');
      badge.className = 'badge bg-azure-lt';
      badge.textContent = KIND_LABELS[item.kind] || 'Otro';
      kind.appendChild(badge);
      row.appendChild(kind);

      var action = document.createElement('td');
      action.className = 'text-end';
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-icon bg-red-lt btn-sm';
      button.disabled = busy;
      button.setAttribute('data-bs-toggle', 'tooltip');
      button.setAttribute('data-bs-placement', 'bottom');
      button.setAttribute('aria-label', 'Restaurar');
      button.setAttribute('data-bs-original-title', 'Restaurar');
      var icon = document.createElement('i');
      icon.className = 'icon ti ti-database-import';
      icon.setAttribute('aria-hidden', 'true');
      button.appendChild(icon);
      button.addEventListener('click', function () {
        openRestore(item.name);
      });
      action.appendChild(button);
      row.appendChild(action);

      body.appendChild(row);
    });

    initTooltips();
  }

  function applyData(data) {
    busy = !!(data.status && data.status.state === 'running');
    showStatus(data.status);
    showPending(data);
    renderTable(data.manifest);
    if (backupButton) {
      backupButton.disabled = busy || data.can_request === false;
      backupButton.title = data.can_request === false
        ? 'El servidor no acepta peticiones de respaldo.'
        : '';
    }
  }

  function poll(delay) {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(fetchData, delay);
  }

  function fetchData() {
    fetch(dataUrl, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('HTTP ' + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        // Si ya volvio el sitio, el estado real manda.
        if (data.status && data.status.state !== 'running') {
          restoreRequested = false;
        }
        applyData(data);
        poll(busy || restoreRequested ? POLL_BUSY_MS : POLL_IDLE_MS);
      })
      .catch(function () {
        // Durante una restauracion el sitio se reinicia y el fetch falla. Se
        // sigue reintentando en vez de dejar el panel mintiendo "al dia".
        if (restoreRequested && statusBox) {
          statusBox.className = 'alert alert-info';
          statusBox.textContent = 'Restaurando… el sitio se reinicia y vuelve solo.';
          statusBox.classList.remove('d-none');
        }
        poll(POLL_BUSY_MS);
      });
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
        Accept: 'application/json'
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload || {})
    }).then(function (response) {
      return response
        .json()
        .catch(function () {
          return {};
        })
        .then(function (data) {
          return { ok: response.ok, status: response.status, data: data };
        });
    });
  }

  function requestBackup() {
    if (busy || !backupButton) {
      return;
    }
    backupButton.disabled = true;
    postJson(backupUrl, {})
      .then(function (result) {
        if (!result.ok) {
          showToast(result.data.reason || 'No se pudo pedir el respaldo.', 'danger', 6000);
          backupButton.disabled = false;
          return;
        }
        showToast('Respaldo solicitado. El estado se actualiza solo.', 'success', 5000);
        poll(1000);
      })
      .catch(function () {
        showToast('No se pudo contactar al servidor.', 'danger', 6000);
        backupButton.disabled = false;
      });
  }

  function openRestore(name) {
    if (busy) {
      return;
    }
    selectedFile = name;
    setText(restoreFile, name);
    setText(confirmWord, confirmation);
    if (confirmInput) {
      confirmInput.value = '';
    }
    if (confirmButton) {
      confirmButton.disabled = true;
    }
    if (confirmError) {
      confirmError.textContent = '';
      confirmError.classList.add('d-none');
    }
    var m = getModal();
    if (m) {
      m.show();
    }
  }

  function requestRestore() {
    if (!selectedFile || !confirmInput || !confirmButton) {
      return;
    }
    if (confirmInput.value.trim() !== confirmation) {
      return;
    }
    confirmButton.disabled = true;
    postJson(restoreUrl, { filename: selectedFile, confirm: confirmation })
      .then(function (result) {
        if (!result.ok) {
          if (confirmError) {
            confirmError.textContent = result.data.reason || 'No se pudo pedir la restauración.';
            confirmError.classList.remove('d-none');
          }
          confirmButton.disabled = false;
          return;
        }
        restoreRequested = true;
        var m = getModal();
        if (m) {
          m.hide();
        }
        showToast('Restauración solicitada. El sitio se reinicia.', 'warning', 8000);
        poll(1000);
      })
      .catch(function () {
        if (confirmError) {
          confirmError.textContent = 'No se pudo contactar al servidor.';
          confirmError.classList.remove('d-none');
        }
        confirmButton.disabled = false;
      });
  }

  if (backupButton) {
    backupButton.addEventListener('click', requestBackup);
  }
  if (confirmInput) {
    confirmInput.addEventListener('input', function () {
      if (confirmButton) {
        confirmButton.disabled = confirmInput.value.trim() !== confirmation;
      }
    });
  }
  if (confirmButton) {
    confirmButton.addEventListener('click', requestRestore);
  }

  fetchData();
})();
