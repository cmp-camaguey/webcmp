/*
 * Respaldo, restauración, descarga y subida de BD desde el panel (040/041).
 * El panel no ejecuta nada privilegiado: escribe peticiones y lee estado/manifest.
 * Todo lo que viene del servidor se pinta con textContent, nunca innerHTML.
 */
(function () {
  'use strict';

  var POLL_BUSY_MS = 3000;
  var POLL_IDLE_MS = 30000;

  var root = document.getElementById('database-backup');
  if (!root) return;

  var dataUrl = root.getAttribute('data-data-url');
  var backupUrl = root.getAttribute('data-backup-url');
  var restoreUrl = root.getAttribute('data-restore-url');
  var downloadRequestUrl = root.getAttribute('data-download-request-url');
  var uploadUrl = root.getAttribute('data-upload-url');
  var confirmation = root.getAttribute('data-confirmation');
  var downloadConfirmation = root.getAttribute('data-download-confirmation');
  var uploadMaxSize = parseInt(root.getAttribute('data-upload-max-size') || '0', 10);
  var csrfToken = root.getAttribute('data-csrf-token');

  var statusBox = document.getElementById('db-status');
  var pendingBox = document.getElementById('db-pending');
  var downloadBox = document.getElementById('db-download');
  var body = document.getElementById('db-backups-body');
  var keepLabel = document.getElementById('db-keep');
  var backupButton = document.getElementById('db-backup-button');
  var uploadButton = document.getElementById('db-upload-button');

  var restoreModalEl = document.getElementById('db-restore-modal');
  var restoreFile = document.getElementById('db-restore-file');
  var confirmWord = document.getElementById('db-confirm-word');
  var confirmInput = document.getElementById('db-confirm-input');
  var confirmButton = document.getElementById('db-confirm-button');
  var confirmError = document.getElementById('db-confirm-error');

  var downloadModalEl = document.getElementById('db-download-modal');
  var downloadFileLabel = document.getElementById('db-download-file');
  var downloadConfirmWord = document.getElementById('db-download-confirm-word');
  var downloadConfirmInput = document.getElementById('db-download-confirm-input');
  var downloadConfirmButton = document.getElementById('db-download-confirm-button');
  var downloadError = document.getElementById('db-download-error');

  var uploadModalEl = document.getElementById('db-upload-modal');
  var uploadFileInput = document.getElementById('db-upload-file');
  var uploadConfirmWord = document.getElementById('db-upload-confirm-word');
  var uploadConfirmInput = document.getElementById('db-upload-confirm-input');
  var uploadConfirmButton = document.getElementById('db-upload-confirm-button');
  var uploadError = document.getElementById('db-upload-error');

  var modals = {};
  var timer = null;
  var busy = false;
  var selectedFile = null;
  var selectedDownload = null;
  var restoreRequested = false;

  var KIND_LABELS = {
    scheduled: 'Programado',
    manual: 'Manual',
    'pre-restore': 'Seguridad',
    'pre-migrate': 'Previo a migrar',
    uploaded: 'Subido',
    unknown: 'Otro'
  };

  function getBootstrap() {
    return (window.tabler && window.tabler.bootstrap) || window.bootstrap;
  }

  function getModal(el) {
    if (!el) return null;
    if (modals[el.id]) return modals[el.id];
    var B = getBootstrap();
    if (!B || !B.Modal) return null;
    modals[el.id] = B.Modal.getOrCreateInstance(el);
    return modals[el.id];
  }

  function setText(node, text) { if (node) node.textContent = text || ''; }

  function humanSize(bytes) {
    if (typeof bytes !== 'number' || bytes < 0) return '—';
    var units = ['B', 'KB', 'MB', 'GB'];
    var value = bytes;
    var i = 0;
    while (value >= 1024 && i < units.length - 1) { value /= 1024; i += 1; }
    return (i === 0 ? String(value) : value.toFixed(1)) + ' ' + units[i];
  }

  function humanDate(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  function initTooltips() {
    var B = getBootstrap();
    if (!B || !B.Tooltip) return;
    root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
      try { var inst = B.Tooltip.getInstance(el); if (inst) inst.dispose(); } catch (e) {}
      try { new B.Tooltip(el); } catch (e2) {}
    });
  }

  function showStatus(status) {
    if (!statusBox) return;
    // El último estado exitoso ya se ve en la tabla; solo mostramos estados
    // que requieren atención (running/failed/stale/expired).
    if (!status || status.tone === 'success') {
      statusBox.classList.add('d-none');
      statusBox.textContent = '';
      return;
    }
    statusBox.className = 'alert alert-' + status.tone;
    statusBox.textContent = '';
    var icon = document.createElement('i');
    icon.className = 'icon ti ti-' + (status.icon || 'info-circle') + ' me-1';
    icon.setAttribute('aria-hidden', 'true');
    statusBox.appendChild(icon);
    statusBox.appendChild(document.createTextNode(status.text || ''));
    statusBox.classList.remove('d-none');
  }

  function showDownload(download) {
    if (!downloadBox) return;
    if (!download || download.state !== 'ok' || !download.url) {
      downloadBox.classList.add('d-none');
      downloadBox.textContent = '';
      return;
    }
    downloadBox.className = 'alert alert-success';
    downloadBox.textContent = '';
    var icon = document.createElement('i');
    icon.className = 'icon ti ti-download me-1';
    icon.setAttribute('aria-hidden', 'true');
    downloadBox.appendChild(icon);
    downloadBox.appendChild(document.createTextNode('Descarga lista: '));
    var a = document.createElement('a');
    a.href = download.url;
    a.className = 'alert-link';
    a.textContent = download.download_name || download.file || 'descargar';
    downloadBox.appendChild(a);
    downloadBox.appendChild(document.createTextNode('. El enlace vence pronto y es de un solo uso.'));
    downloadBox.classList.remove('d-none');
  }

  function showPending(data) {
    if (!pendingBox) return;
    var messages = [];
    ['pending_backup', 'pending_restore', 'pending_download'].forEach(function (k) {
      if (data[k]) messages.push(data[k].text);
    });
    if (!messages.length) { pendingBox.classList.add('d-none'); pendingBox.textContent = ''; return; }
    pendingBox.textContent = '';
    var icon = document.createElement('i');
    icon.className = 'icon ti ti-plug-off me-1';
    icon.setAttribute('aria-hidden', 'true');
    pendingBox.appendChild(icon);
    pendingBox.appendChild(document.createTextNode(messages.join(' ')));
    pendingBox.classList.remove('d-none');
  }

  function renderTable(manifest) {
    if (!body) return;
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
      var group = document.createElement('div');
      group.className = 'btn-list justify-content-end';

      var dlBtn = makeIconButton('btn-icon bg-azure-lt btn-sm', 'ti-download', 'Descargar');
      dlBtn.disabled = busy;
      dlBtn.addEventListener('click', function () { openDownload(item.name); });
      group.appendChild(dlBtn);

      var rsBtn = makeIconButton('btn-icon bg-red-lt btn-sm', 'ti-database-import', 'Restaurar');
      rsBtn.disabled = busy;
      rsBtn.addEventListener('click', function () { openRestore(item.name); });
      group.appendChild(rsBtn);

      action.appendChild(group);
      row.appendChild(action);
      body.appendChild(row);
    });
    initTooltips();
  }

  function makeIconButton(cls, iconCls, label) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn ' + cls;
    b.setAttribute('data-bs-toggle', 'tooltip');
    b.setAttribute('data-bs-placement', 'bottom');
    b.setAttribute('aria-label', label);
    b.setAttribute('data-bs-original-title', label);
    var i = document.createElement('i');
    i.className = 'icon ti ' + iconCls;
    i.setAttribute('aria-hidden', 'true');
    b.appendChild(i);
    return b;
  }

  function applyData(data) {
    busy = !!(data.status && data.status.state === 'running');
    showStatus(data.status);
    showPending(data);
    showDownload(data.download);
    renderTable(data.manifest);
    if (backupButton) {
      backupButton.disabled = busy || data.can_request === false;
      backupButton.title = data.can_request === false ? 'El servidor no acepta peticiones de respaldo.' : '';
    }
    if (uploadButton) uploadButton.disabled = busy;
  }

  function poll(delay) { if (timer) clearTimeout(timer); timer = setTimeout(fetchData, delay); }

  function fetchData() {
    fetch(dataUrl, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) {
        if (data.status && data.status.state !== 'running') restoreRequested = false;
        applyData(data);
        poll(busy || restoreRequested ? POLL_BUSY_MS : POLL_IDLE_MS);
      })
      .catch(function () {
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
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken, Accept: 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload || {})
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  function requestBackup() {
    if (busy || !backupButton) return;
    backupButton.disabled = true;
    postJson(backupUrl, {})
      .then(function (res) {
        if (!res.ok) { showToast(res.data.reason || 'No se pudo pedir el respaldo.', 'danger', 6000); backupButton.disabled = false; return; }
        showToast('Respaldo solicitado. El estado se actualiza solo.', 'success', 5000);
        poll(1000);
      })
      .catch(function () { showToast('No se pudo contactar al servidor.', 'danger', 6000); backupButton.disabled = false; });
  }

  function openConfirmModal(el, file, word, fileLabel, wordLabel, input, button, error) {
    setText(fileLabel, file);
    setText(wordLabel, word);
    if (input) input.value = '';
    if (button) button.disabled = true;
    if (error) { error.textContent = ''; error.classList.add('d-none'); }
    var m = getModal(el);
    if (m) m.show();
  }

  function openRestore(name) {
    if (busy) return;
    selectedFile = name;
    openConfirmModal(restoreModalEl, name, confirmation, restoreFile, confirmWord, confirmInput, confirmButton, confirmError);
  }

  function openDownload(name) {
    if (busy) return;
    selectedDownload = name;
    openConfirmModal(downloadModalEl, name, downloadConfirmation, downloadFileLabel, downloadConfirmWord, downloadConfirmInput, downloadConfirmButton, downloadError);
  }

  function openUpload() {
    if (busy) return;
    setText(uploadConfirmWord, confirmation);
    if (uploadFileInput) uploadFileInput.value = '';
    if (uploadConfirmInput) uploadConfirmInput.value = '';
    if (uploadConfirmButton) uploadConfirmButton.disabled = true;
    if (uploadError) { uploadError.textContent = ''; uploadError.classList.add('d-none'); }
    var m = getModal(uploadModalEl);
    if (m) m.show();
  }

  function requestRestore() {
    if (!selectedFile || !confirmInput || confirmInput.value.trim() !== confirmation) return;
    if (confirmButton) confirmButton.disabled = true;
    postJson(restoreUrl, { filename: selectedFile, confirm: confirmation })
      .then(function (res) {
        if (!res.ok) {
          if (confirmError) { confirmError.textContent = res.data.reason || 'No se pudo pedir la restauración.'; confirmError.classList.remove('d-none'); }
          if (confirmButton) confirmButton.disabled = false;
          return;
        }
        restoreRequested = true;
        var m = getModal(restoreModalEl); if (m) m.hide();
        showToast('Restauración solicitada. El sitio se reinicia.', 'warning', 8000);
        poll(1000);
      })
      .catch(function () {
        if (confirmError) { confirmError.textContent = 'No se pudo contactar al servidor.'; confirmError.classList.remove('d-none'); }
        if (confirmButton) confirmButton.disabled = false;
      });
  }

  function requestDownload() {
    if (!selectedDownload || !downloadConfirmInput || downloadConfirmInput.value.trim() !== downloadConfirmation) return;
    if (downloadConfirmButton) downloadConfirmButton.disabled = true;
    postJson(downloadRequestUrl, { filename: selectedDownload, confirm: downloadConfirmation })
      .then(function (res) {
        if (!res.ok) {
          if (downloadError) { downloadError.textContent = res.data.reason || 'No se pudo preparar la descarga.'; downloadError.classList.remove('d-none'); }
          if (downloadConfirmButton) downloadConfirmButton.disabled = false;
          return;
        }
        var m = getModal(downloadModalEl); if (m) m.hide();
        showToast('Descarga solicitada. El enlace aparecerá cuando esté listo.', 'success', 6000);
        poll(1000);
      })
      .catch(function () {
        if (downloadError) { downloadError.textContent = 'No se pudo contactar al servidor.'; downloadError.classList.remove('d-none'); }
        if (downloadConfirmButton) downloadConfirmButton.disabled = false;
      });
  }

  function requestUpload() {
    if (!uploadFileInput || !uploadConfirmInput) return;
    var file = uploadFileInput.files && uploadFileInput.files[0];
    if (!file) { if (uploadError) { uploadError.textContent = 'Seleccione un archivo .dump.'; uploadError.classList.remove('d-none'); } return; }
    if (uploadConfirmInput.value.trim() !== confirmation) return;
    if (uploadMaxSize && file.size > uploadMaxSize) {
      if (uploadError) { uploadError.textContent = 'El archivo excede el tamaño máximo.'; uploadError.classList.remove('d-none'); }
      return;
    }
    if (uploadConfirmButton) uploadConfirmButton.disabled = true;
    var fd = new FormData();
    fd.append('file', file);
    fd.append('confirm', confirmation);
    fetch(uploadUrl, { method: 'POST', headers: { 'X-CSRFToken': csrfToken, Accept: 'application/json' }, credentials: 'same-origin', body: fd })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          if (uploadError) { uploadError.textContent = res.data.reason || 'No se pudo subir el respaldo.'; uploadError.classList.remove('d-none'); }
          if (uploadConfirmButton) uploadConfirmButton.disabled = false;
          return;
        }
        restoreRequested = true;
        var m = getModal(uploadModalEl); if (m) m.hide();
        showToast('Respaldo subido. La restauración se inició.', 'warning', 8000);
        poll(1000);
      })
      .catch(function () {
        if (uploadError) { uploadError.textContent = 'No se pudo contactar al servidor.'; uploadError.classList.remove('d-none'); }
        if (uploadConfirmButton) uploadConfirmButton.disabled = false;
      });
  }

  function wireConfirm(input, button, word) {
    if (!input || !button) return;
    input.addEventListener('input', function () { button.disabled = input.value.trim() !== word; });
  }

  if (backupButton) backupButton.addEventListener('click', requestBackup);
  if (uploadButton) uploadButton.addEventListener('click', openUpload);
  wireConfirm(confirmInput, confirmButton, confirmation);
  wireConfirm(downloadConfirmInput, downloadConfirmButton, downloadConfirmation);
  wireConfirm(uploadConfirmInput, uploadConfirmButton, confirmation);
  if (confirmButton) confirmButton.addEventListener('click', requestRestore);
  if (downloadConfirmButton) downloadConfirmButton.addEventListener('click', requestDownload);
  if (uploadConfirmButton) uploadConfirmButton.addEventListener('click', requestUpload);

  fetchData();
})();
