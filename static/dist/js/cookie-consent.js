/**
 * Cookie Consent — banner y gestión de consentimiento.
 *
 * Categorías:
 * - necessary: siempre activo (sesión, CSRF, seguridad). No se puede desactivar.
 * - analytics: RUM (pageviews, web vitals, errores JS). Requiere consentimiento.
 * - functional: futuras funcionalidades (preferencias, mapas, etc.). Requiere consentimiento.
 *
 * Almacenamiento: cookie `cookie_consent` (1 año) + localStorage como respaldo.
 * Formato: JSON { necessary: true, analytics: boolean, functional: boolean, timestamp: ISO }
 */
;(function () {
  'use strict'

  var CONSENT_COOKIE = 'cookie_consent'
  var CONSENT_TTL_DAYS = 365
  var STORAGE_KEY = 'cookie_consent'

  function nowISO() {
    return new Date().toISOString()
  }

  function defaultConsent() {
    return {
      necessary: true,
      analytics: false,
      functional: false,
      timestamp: nowISO()
    }
  }

  function parseConsent(value) {
    try {
      var parsed = JSON.parse(value)
      if (parsed && typeof parsed === 'object' && parsed.necessary === true) {
        return {
          necessary: true,
          analytics: !!parsed.analytics,
          functional: !!parsed.functional,
          timestamp: parsed.timestamp || nowISO()
        }
      }
    } catch (e) {
      /* ignorar */
    }
    return null
  }

  function readConsent() {
    try {
      var stored = window.localStorage.getItem(STORAGE_KEY)
      if (stored) {
        var parsed = parseConsent(stored)
        if (parsed) return parsed
      }
    } catch (e) {
      /* ignorar */
    }
    var cookie = document.cookie.split('; ').find(function (c) {
      return c.startsWith(CONSENT_COOKIE + '=')
    })
    if (cookie) {
      var value = decodeURIComponent(cookie.split('=')[1])
      return parseConsent(value)
    }
    return null
  }

  function writeConsent(consent) {
    var value = JSON.stringify(consent)
    var expires = new Date(Date.now() + CONSENT_TTL_DAYS * 86400000).toUTCString()
    document.cookie = CONSENT_COOKIE + '=' + encodeURIComponent(value) + '; expires=' + expires + '; path=/; SameSite=Lax'
    try {
      window.localStorage.setItem(STORAGE_KEY, value)
    } catch (e) {
      /* ignorar */
    }
  }

  function hasConsent(category) {
    var consent = readConsent()
    if (!consent) return false
    return !!consent[category]
  }

  function showBanner() {
    if (document.getElementById('cookieConsentBanner')) return
    if (readConsent()) return

    var banner = document.createElement('div')
    banner.id = 'cookieConsentBanner'
    banner.className = 'cookie-consent-banner'
    banner.setAttribute('role', 'dialog')
    banner.setAttribute('aria-live', 'polite')
    banner.setAttribute('aria-label', 'Consentimiento de cookies')
    banner.innerHTML =
      '<div class="cookie-consent-content">' +
      '  <div class="cookie-consent-text">' +
      '    <h3 class="h6 mb-1">Usamos cookies</h3>' +
      '    <p class="mb-0 small">Este sitio usa cookies técnicas necesarias y, con tu consentimiento, cookies de analítica para medir el rendimiento (RUM). Puedes aceptar, rechazar o configurar.</p>' +
      '  </div>' +
      '  <div class="cookie-consent-actions">' +
      '    <button type="button" class="btn btn-primary btn-sm" data-action="accept-all">Aceptar todo</button>' +
      '    <button type="button" class="btn btn-secondary btn-sm" data-action="reject-all">Rechazar analítica</button>' +
      '    <button type="button" class="btn btn-outline-secondary btn-sm" data-action="configure">Configurar</button>' +
      '  </div>' +
      '</div>' +
      '<div class="cookie-consent-modal d-none" id="cookieConsentModal" role="dialog" aria-modal="true" aria-labelledby="cookieConsentModalLabel">' +
      '  <div class="cookie-consent-modal-content">' +
      '    <div class="cookie-consent-modal-header">' +
      '      <h4 id="cookieConsentModalLabel" class="mb-0">Configurar cookies</h4>' +
      '      <button type="button" class="btn-close" data-action="close-modal" aria-label="Cerrar"></button>' +
      '    </div>' +
      '    <div class="cookie-consent-modal-body">' +
      '      <div class="cookie-consent-category">' +
      '        <div class="d-flex justify-content-between align-items-center mb-2">' +
      '          <div>' +
      '            <strong>Necesarias</strong>' +
      '            <div class="small text-secondary">Requeridas para que el sitio funcione (sesión, seguridad, CSRF). No se pueden desactivar.</div>' +
      '          </div>' +
      '          <input type="checkbox" disabled checked>' +
      '        </div>' +
      '      </div>' +
      '      <div class="cookie-consent-category">' +
      '        <div class="d-flex justify-content-between align-items-center mb-2">' +
      '          <div>' +
      '            <strong>Analítica / Rendimiento</strong>' +
      '            <div class="small text-secondary">Medición anónima de rendimiento (RUM): tiempos de carga, interacción, errores JS. No identifica a la persona.</div>' +
      '          </div>' +
      '          <input type="checkbox" id="consentAnalytics" data-category="analytics">' +
      '        </div>' +
      '      </div>' +
      '      <div class="cookie-consent-category">' +
      '        <div class="d-flex justify-content-between align-items-center mb-2">' +
      '          <div>' +
      '            <strong>Funcionales</strong>' +
      '            <div class="small text-secondary">Preferencias de usuario, mapas, contenidos incrustados (futuro).</div>' +
      '          </div>' +
      '          <input type="checkbox" id="consentFunctional" data-category="functional">' +
      '        </div>' +
      '      </div>' +
      '    </div>' +
      '    <div class="cookie-consent-modal-footer">' +
      '      <button type="button" class="btn btn-secondary" data-action="close-modal">Cancelar</button>' +
      '      <button type="button" class="btn btn-primary" data-action="save-config">Guardar selección</button>' +
      '    </div>' +
      '  </div>' +
      '</div>'

    document.body.appendChild(banner)
    document.body.classList.add('cookie-consent-open')

    banner.querySelector('[data-action="accept-all"]').addEventListener('click', function () {
      acceptAll()
    })
    banner.querySelector('[data-action="reject-all"]').addEventListener('click', function () {
      rejectAll()
    })
    banner.querySelector('[data-action="configure"]').addEventListener('click', function () {
      openModal()
    })
    banner.querySelector('[data-action="close-modal"]').addEventListener('click', function () {
      closeModal()
    })
    banner.querySelector('[data-action="save-config"]').addEventListener('click', function () {
      saveConfig()
    })
    banner.querySelector('#consentAnalytics').addEventListener('change', function () {
      updateModalState()
    })
    banner.querySelector('#consentFunctional').addEventListener('change', function () {
      updateModalState()
    })

    updateModalState()
  }

  function openModal() {
    var modal = document.getElementById('cookieConsentModal')
    var consent = readConsent() || defaultConsent()
    document.getElementById('consentAnalytics').checked = consent.analytics
    document.getElementById('consentFunctional').checked = consent.functional
    modal.classList.remove('d-none')
    document.body.classList.add('modal-open')
  }

  function closeModal() {
    var modal = document.getElementById('cookieConsentModal')
    modal.classList.add('d-none')
    document.body.classList.remove('modal-open')
  }

  function updateModalState() {
    var saveBtn = document.querySelector('[data-action="save-config"]')
    var analytics = document.getElementById('consentAnalytics').checked
    var functional = document.getElementById('consentFunctional').checked
    saveBtn.disabled = !(analytics || functional)
  }

  function saveConfig() {
    var consent = {
      necessary: true,
      analytics: document.getElementById('consentAnalytics').checked,
      functional: document.getElementById('consentFunctional').checked,
      timestamp: nowISO()
    }
    writeConsent(consent)
    closeModal()
    hideBanner()
    applyConsent(consent, 'custom')
  }

  function acceptAll() {
    var consent = {
      necessary: true,
      analytics: true,
      functional: true,
      timestamp: nowISO()
    }
    writeConsent(consent)
    hideBanner()
    applyConsent(consent, 'accept_all')
  }

  function rejectAll() {
    var consent = {
      necessary: true,
      analytics: false,
      functional: false,
      timestamp: nowISO()
    }
    writeConsent(consent)
    hideBanner()
    applyConsent(consent, 'reject_analytics')
  }

  function hideBanner() {
    var banner = document.getElementById('cookieConsentBanner')
    if (banner) {
      banner.remove()
      document.body.classList.remove('cookie-consent-open')
    }
  }

  function sendConsentToServer(choice, analytics, functional) {
    var url = '/cookies/consentimiento/'
    var body = JSON.stringify({ choice: choice, analytics: analytics, functional: functional })
    try {
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body,
        credentials: 'same-origin'
      }).then(function (resp) {
        if (!resp.ok) {
          console.warn('Cookie consent server record failed:', resp.status)
        }
      }).catch(function () {
        /* silencioso: el consentimiento local ya está guardado */
      })
    } catch (e) {
      /* silencioso */
    }
  }

  function applyConsent(consent, choice) {
    window.dispatchEvent(new CustomEvent('cookieConsentChange', { detail: consent }))
    if (consent.analytics && window.rumBeacon && typeof window.rumBeacon.init === 'function') {
      window.rumBeacon.init()
    }
    // Enviar al servidor para auditoría (no bloquea la UX)
    sendConsentToServer(choice, consent.analytics, consent.functional)
  }

  function init() {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', showBanner)
    } else {
      showBanner()
    }

    window.cookieConsent = {
      read: readConsent,
      write: writeConsent,
      has: hasConsent,
      showBanner: showBanner,
      acceptAll: acceptAll,
      rejectAll: rejectAll
    }
  }

  init()
})()